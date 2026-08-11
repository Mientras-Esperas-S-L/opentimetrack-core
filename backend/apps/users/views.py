"""Identity and organisation endpoints."""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.models import set_current_tenant
from apps.common.permissions import (
    IsAdmin,
    IsAuthenticatedInTenant,
    IsManagerOrAdmin,
    ReadForAllWriteForAdmin,
)
from apps.users.models import Department
from apps.users.passwords import resolve_token, send_account_email
from apps.users.serializers import (
    DepartmentSerializer,
    PasswordResetRequestSerializer,
    PasswordSetSerializer,
    SignInSerializer,
    SignUpSerializer,
    TenantSerializer,
    UserSerializer,
    UserWriteSerializer,
    issue_tokens,
)

User = get_user_model()
logger = logging.getLogger(__name__)


@extend_schema(tags=["auth"])
class SignUpView(APIView):
    """Registers a company and its first administrator."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "login"

    @extend_schema(request=SignUpSerializer, responses={201: None}, auth=[])
    def post(self, request):
        serializer = SignUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = serializer.save()

        user = created["user"]
        set_current_tenant(user.tenant_id)

        return Response(
            {
                **issue_tokens(user),
                "user": UserSerializer(user).data,
                "tenant": TenantSerializer(created["company"]).data,
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["auth"])
class SignInView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "login"

    @extend_schema(request=SignInSerializer, responses={200: None}, auth=[])
    def post(self, request):
        serializer = SignInSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        set_current_tenant(user.tenant_id)

        return Response(
            {
                **issue_tokens(user),
                "user": UserSerializer(user).data,
                "tenant": TenantSerializer(user.tenant).data,
            }
        )


@extend_schema(tags=["auth"])
class SignOutView(APIView):
    """Invalidates the refresh token, so signing out actually signs out."""

    permission_classes = [IsAuthenticatedInTenant]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        token = request.data.get("refresh")
        if token:
            try:
                RefreshToken(token).blacklist()
            except TokenError as exc:
                # An expired or already blacklisted token means the session is
                # gone, which is what was asked for. Worth a log line rather than
                # silence: a burst of these can mean a client stuck in a loop.
                logger.info("Sign-out with an unusable refresh token: %s", exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["auth"])
class MeView(APIView):
    permission_classes = [IsAuthenticatedInTenant]

    @extend_schema(responses={200: UserSerializer})
    def get(self, request):
        return Response(
            {
                "user": UserSerializer(request.user).data,
                "tenant": TenantSerializer(request.user.tenant).data,
            }
        )


@extend_schema(tags=["people"])
class UserViewSet(viewsets.ModelViewSet):
    """People in the company.

    Managers may read; only administrators create, change or deactivate.
    """

    # Declared only so the schema generator can infer the model without running
    # get_queryset, which needs an authenticated caller. Never used at runtime.
    queryset = User.objects.none()
    serializer_class = UserSerializer
    permission_classes = [IsManagerOrAdmin]
    filterset_fields = ["role", "department", "is_active"]
    search_fields = ["first_name", "last_name", "email", "employee_id"]
    ordering_fields = ["last_name", "date_joined"]

    def get_queryset(self):
        # Users are not a TenantOwnedModel -- sign-in has to find them before the
        # company is known -- so the scoping is explicit here.
        return User.objects.filter(tenant=self.request.user.tenant).select_related("department")

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return UserWriteSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsAdmin()]
        return super().get_permissions()

    def perform_destroy(self, instance):
        """Deactivate rather than delete: their clock events must survive."""
        instance.is_active = False
        instance.save(update_fields=["is_active"])


@extend_schema(tags=["organisation"])
class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.none()
    serializer_class = DepartmentSerializer
    permission_classes = [ReadForAllWriteForAdmin]
    filterset_fields = ["is_active"]
    search_fields = ["name"]

    def get_queryset(self):
        return Department.objects.all()

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


@extend_schema(tags=["auth"])
class PasswordResetRequestView(APIView):
    """Asks for a link to set a new password.

    Always answers 204, whether the address exists or not. Telling them apart
    would turn this into a way of finding out who works where.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "login"

    @extend_schema(request=PasswordResetRequestSerializer, responses={204: None}, auth=[])
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()

        # One link per account: the same address may belong to several
        # companies, and each message names its own.
        for user in User.objects.filter(email__iexact=email, is_active=True):
            if user.is_federated:
                # Their credentials belong to the identity provider; a link from
                # here would set a password that can never be used.
                logger.info("Recovery requested for a federated account: %s", user.email)
                continue
            send_account_email(user, base_url=settings.FRONTEND_URL)

        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["auth"])
class PasswordSetView(APIView):
    """Sets the password from the link, and signs the person in."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "login"

    @extend_schema(request=PasswordSetSerializer, responses={200: None}, auth=[])
    def post(self, request):
        serializer = PasswordSetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = resolve_token(serializer.validated_data["uid"], serializer.validated_data["token"])
        if user is None:
            raise DRFValidationError(
                {"detail": _("The link is not valid or has already been used.")}
            )

        user.set_password(serializer.validated_data["password"])
        user.save(update_fields=["password"])
        set_current_tenant(user.tenant_id)

        # Straight in, so nobody has to type the password they just chose.
        return Response(
            {
                **issue_tokens(user),
                "user": UserSerializer(user).data,
                "tenant": TenantSerializer(user.tenant).data if user.tenant else None,
            }
        )
