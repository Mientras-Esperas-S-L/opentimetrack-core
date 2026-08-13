"""Identity and organisation endpoints."""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.common.exceptions import BusinessRuleError
from apps.common.models import set_current_tenant
from apps.common.permissions import (
    IsAdmin,
    IsAuthenticatedInTenant,
    IsManagerOrAdmin,
    ReadForAllWriteForAdmin,
)
from apps.common.scope import people_queryset
from apps.users.models import Department, Role, Workplace
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
    WorkplaceSerializer,
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
        if not serializer.is_valid():
            # A burst of these is the shape of an attack, and without them the
            # trail says nothing about attempts that never got in. The company
            # comes from the address given, so a wrong one records nothing --
            # there is no company to scope the entry to.
            self._record_failed_attempt(request)
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

    def _record_failed_attempt(self, request):
        """A failed attempt goes to the application log, not the audit trail.

        It cannot go to the trail, and the reason is worth writing down.
        `ATOMIC_REQUESTS` is on, and DRF marks the transaction for rollback
        whenever it turns an exception into an error response. Every audit
        entry is written on commit, so **nothing recorded during a failing
        request survives** --- which is right for everything else (an entry
        describing something that rolled back would be a lie) and useless here,
        where the failure is the thing worth recording.

        The application log already goes to file and to the log collector, and
        a burst of these is the shape of an attack, which is an operational
        question rather than part of the working-time record.
        """
        email = (request.data.get("email") or "").strip().lower()
        logger.warning(
            "Failed sign-in for %s from %s",
            email or "(no address)",
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR"),
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


class MePreferencesSerializer(serializers.Serializer):
    """The handful of things a person may change about themselves.

    Deliberately tiny: everything that touches the record or the org --- role,
    department, contract, active --- is somebody else's to set. What is left is
    genuinely personal: the language they read in, and whether they want the
    reminders. Anything not here cannot be changed through this door.
    """

    locale = serializers.CharField(max_length=10, required=False, allow_blank=True)
    wants_punch_reminders = serializers.BooleanField(required=False)


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

    @extend_schema(request=MePreferencesSerializer, responses={200: UserSerializer})
    def patch(self, request):
        """A person changing their own preferences, and only those."""
        form = MePreferencesSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        for field, value in form.validated_data.items():
            setattr(request.user, field, value)
        request.user.save(update_fields=list(form.validated_data))
        return Response(UserSerializer(request.user).data)


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
    filterset_fields = ["role", "department", "is_active", "is_worker_representative"]
    search_fields = ["first_name", "last_name", "email", "employee_id"]
    ordering_fields = ["last_name", "date_joined"]

    def get_queryset(self):
        # Users are not a TenantOwnedModel -- sign-in has to find them before the
        # company is known -- so the scoping is explicit here, and it is by what
        # the caller answers for rather than by company.
        return people_queryset(self.request.user).select_related("department")

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return UserWriteSerializer
        return UserSerializer

    def get_permissions(self):
        # `invite` belongs here and not with the read actions: sending the link
        # hands somebody a way into the company's records.
        if self.action in {"create", "update", "partial_update", "destroy", "invite"}:
            return [IsAdmin()]
        return super().get_permissions()

    def _refuse_if_it_leaves_no_admin(self, person, *, new_role=None, deactivating=False):
        """Stops a company ending up with nobody able to administer it.

        A company in that state cannot add people, resolve requests, or undo
        whatever caused it: the only way out is somebody with database access.

        The realistic way in is **not** deactivation --- only an administrator can
        deactivate, so their own existence guarantees another one remains --- but
        **demotion**: the sole administrator changing their own role to employee.
        That is one dropdown away and answers 200 happily.

        `get_queryset`, not `User.objects`: people are not a TenantOwnedModel,
        because sign-in has to find them before the company is known, so the
        default manager spans every company. Counting with it would let another
        company's administrator stand in for this one's.
        """
        stays_admin = not deactivating and (new_role or person.role) == Role.ADMIN
        if stays_admin:
            return

        others = self.get_queryset().filter(role=Role.ADMIN, is_active=True).exclude(pk=person.pk)
        if person.role == Role.ADMIN and person.is_active and not others.exists():
            raise BusinessRuleError(
                code="last_administrator",
                message=_(
                    "This is the only active administrator. Appoint another one first, "
                    "or the company is left with nobody able to manage it."
                ),
            )

    def _invite(self, person) -> bool:
        """Sends the link to set a password, unless it would be useless.

        Federated accounts sign in through the identity provider, so a link from
        here would set a password nobody can use; and somebody deactivated
        cannot sign in at all, which would make the message a dead end.
        """
        if person.is_federated or not person.is_active:
            return False

        send_account_email(person, base_url=settings.FRONTEND_URL, invitation=True)
        record(
            action=AuditAction.INVITATION_SENT,
            actor=self.request.user,
            target=person,
            target_label=person.get_full_name() or person.email,
            request=self.request,
        )
        return True

    def perform_create(self, serializer):
        person = serializer.save()
        record(
            action=AuditAction.PERSON_CREATED,
            actor=self.request.user,
            target=person,
            target_label=person.get_full_name() or person.email,
            changes={"role": person.role},
            request=self.request,
        )

        # Without this the account exists and nobody can get into it: creating a
        # person and inviting them are the same act from the administrator's
        # side, so it is not left as a second button they have to remember.
        # Unless a password came in the payload, in which case somebody is
        # setting it deliberately and a link would only muddle things.
        if not serializer.validated_data.get("password"):
            self._invite(person)

    @extend_schema(request=None, responses={200: dict})
    @action(detail=True, methods=["post"])
    def invite(self, request, pk=None):
        """Sends the link again.

        Needed because the link expires, mail goes astray, and an account
        created before this existed never got one.
        """
        person = self.get_object()
        if not self._invite(person):
            raise BusinessRuleError(
                code="cannot_invite",
                message=(
                    _("This account signs in through your identity provider.")
                    if person.is_federated
                    else _("Reactivate the account before inviting them.")
                ),
            )
        return Response({"sent_to": person.email})

    def perform_update(self, serializer):
        before = serializer.instance.role
        was_active = serializer.instance.is_active
        new_role = serializer.validated_data.get("role")
        if new_role:
            self._refuse_if_it_leaves_no_admin(serializer.instance, new_role=new_role)
        person = serializer.save()

        # Giving somebody their access back is not an ordinary edit, and the
        # trail should not make it look like one: it is the reverse of
        # PERSON_DEACTIVATED and belongs next to it when somebody reads the
        # history of an account.
        if person.is_active and not was_active:
            record(
                action=AuditAction.PERSON_REACTIVATED,
                actor=self.request.user,
                target=person,
                target_label=person.get_full_name() or person.email,
                request=self.request,
            )
            return

        # A role change gets its own action. It is the one that decides who can
        # read other people's records, so it should be findable without
        # trawling through every ordinary edit.
        if new_role and new_role != before:
            record(
                action=AuditAction.ROLE_CHANGED,
                actor=self.request.user,
                target=person,
                target_label=person.get_full_name() or person.email,
                changes={"role": [before, new_role]},
                request=self.request,
            )
        else:
            record(
                action=AuditAction.PERSON_UPDATED,
                actor=self.request.user,
                target=person,
                target_label=person.get_full_name() or person.email,
                request=self.request,
            )

    def perform_destroy(self, instance):
        """Deactivate rather than delete: their clock events must survive."""
        # Found by deactivating the wrong account while testing the panel and
        # then being unable to sign back in. Undoing it needs somebody else with
        # the same privilege, and there may not be one.
        if instance.id == self.request.user.id:
            raise BusinessRuleError(
                code="cannot_deactivate_yourself",
                message=_("You cannot deactivate your own account."),
            )

        self._refuse_if_it_leaves_no_admin(instance, deactivating=True)

        instance.is_active = False
        instance.save(update_fields=["is_active"])
        record(
            action=AuditAction.PERSON_DEACTIVATED,
            actor=self.request.user,
            target=instance,
            target_label=instance.get_full_name() or instance.email,
            request=self.request,
        )


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


@extend_schema(tags=["organisation"])
class WorkplaceViewSet(viewsets.ModelViewSet):
    """Centros de trabajo. Anyone reads; an administrator writes.

    Read for anyone on purpose: a person is entitled to know which workplace
    their record is kept at, and which holiday calendar is being applied to
    them.
    """

    queryset = Workplace.objects.none()
    serializer_class = WorkplaceSerializer
    permission_classes = [ReadForAllWriteForAdmin]
    filterset_fields = ["is_active", "region"]
    search_fields = ["name", "municipality"]

    def get_queryset(self):
        return Workplace.objects.all()

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)

    def perform_destroy(self, instance):
        """Refused while anybody works there.

        `SET_NULL` would keep the people and lose the place, which for a
        department is a tidy answer and here is not: the workplace decides which
        local holidays apply and which zone the day is measured in, so people
        left without one would silently start being measured against the
        company's defaults.
        """
        working = instance.people.filter(is_active=True).count()
        if working:
            raise BusinessRuleError(
                code="workplace_in_use",
                message=_(
                    "%(count)s people work there. Move them first: without a workplace "
                    "they lose their local holidays and their time zone."
                )
                % {"count": working},
            )
        instance.delete()


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
