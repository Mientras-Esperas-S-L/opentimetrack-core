"""The three doors of federated sign-in, and the one the provider knocks on.

`discover` answers «where do I sign in», `start` sends the browser to the provider and
`callback` brings it back with a session. `logout` is the other direction: the provider
telling us somebody's session must end.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.shortcuts import redirect
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.common.exceptions import BusinessRuleError
from apps.common.models import set_current_tenant
from apps.tenants import sso
from apps.tenants.identity import SsoProvider

logger = logging.getLogger(__name__)


def _redirect_uri(request) -> str:
    """Where the provider sends the browser back. Registered there, so it must match."""
    configured = getattr(settings, "SSO_REDIRECT_URI", "") or ""
    return configured or request.build_absolute_uri("/api/auth/sso/callback/")


class DiscoverSerializer(serializers.Serializer):
    email = serializers.EmailField()


class DiscoverAnswerSerializer(serializers.Serializer):
    sso = serializers.BooleanField(help_text="Whether that address signs in through a provider.")
    provider = serializers.CharField(required=False, help_text="Its display name, for the button.")
    slug = serializers.CharField(required=False)


@extend_schema(tags=["auth"])
class SsoDiscoverView(APIView):
    """Whether this address signs in here or at a provider."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "login"

    @extend_schema(
        summary="Where does this address sign in",
        description=(
            "Answers from the email domain, so nobody has to know which of their employer's "
            "identity systems is theirs. It says nothing about whether the address exists."
        ),
        request=DiscoverSerializer,
        responses={200: DiscoverAnswerSerializer},
        auth=[],
    )
    def post(self, request):
        form = DiscoverSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        provider = sso.provider_for_email(form.validated_data["email"])
        if provider is None:
            # Deliberately the same answer for «no provider» and «nobody with that
            # address»: otherwise this endpoint tells anyone who works here.
            return Response({"sso": False})
        return Response({"sso": True, "provider": provider.name, "slug": provider.slug})


@extend_schema(tags=["auth"])
class SsoStartView(APIView):
    """Sends the browser to the provider."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "login"

    @extend_schema(
        summary="Start signing in at the provider",
        parameters=[],
        responses={302: None},
        auth=[],
    )
    def get(self, request, slug: str):
        # Igual que en el descubrimiento: la empresa sale del proveedor, no al revés.
        provider = SsoProvider.objects_all_tenants.filter(slug=slug, is_active=True).first()
        if provider is None or not provider.can_sign_people_in:
            raise BusinessRuleError(
                code="provider_unknown",
                message="No such identity provider.",
                details={"slug": slug},
            )
        return redirect(sso.authorize_url(provider, _redirect_uri(request)))


class SessionAnswerSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    created = serializers.BooleanField(help_text="Whether this sign-in created the person.")


@extend_schema(tags=["auth"])
class SsoCallbackView(APIView):
    """Where the provider sends the browser back, with a code."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "login"

    @extend_schema(
        summary="Return from the provider",
        description=(
            "Exchanges the code, verifies the token, resolves the person and issues a session. "
            "The state is single use, so a replayed return is refused."
        ),
        responses={200: SessionAnswerSerializer},
        auth=[],
    )
    def get(self, request):
        from apps.users.serializers import issue_tokens

        error = request.query_params.get("error")
        if error:
            # The provider refused. Its own message is not ours to relay verbatim.
            logger.info("sso: provider refused the sign-in: %s", error)
            raise BusinessRuleError(
                code="provider_refused",
                message="The identity provider did not authorise the sign-in.",
                details={"error": error[:100]},
            )

        kept = sso.take_state(request.query_params.get("state", ""))
        provider = SsoProvider.objects_all_tenants.filter(
            pk=kept["provider"], is_active=True
        ).first()
        if provider is None:
            raise BusinessRuleError(code="provider_unknown", message="No such identity provider.")

        tokens = sso.exchange_code(
            provider, request.query_params.get("code", ""), kept["verifier"], kept["redirect_uri"]
        )
        claims = sso.validated_claims(provider, tokens["id_token"], kept["nonce"])

        set_current_tenant(provider.tenant_id)
        person, created = sso.resolve_person(provider, claims)
        if not person.is_active:
            raise BusinessRuleError(
                code="person_inactive", message="That account is not active here."
            )

        return Response({**issue_tokens(person), "created": created}, status=status.HTTP_200_OK)


class LogoutTokenSerializer(serializers.Serializer):
    logout_token = serializers.CharField()


@extend_schema(tags=["auth"])
class SsoBackChannelLogoutView(APIView):
    """The provider telling us to end somebody's session.

    Without this, changing a password at the provider because it was stolen leaves the
    session here alive for as long as its refresh lasts. Deactivating somebody is
    already covered from the other side; this covers the compromise.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(
        summary="End a session on the provider's word",
        description="OIDC Back-Channel Logout: a signed logout_token naming the subject.",
        request=LogoutTokenSerializer,
        responses={200: None},
        auth=[],
    )
    def post(self, request):
        import jwt

        form = LogoutTokenSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        token = form.validated_data["logout_token"]

        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
        except jwt.PyJWTError as exc:
            raise BusinessRuleError(
                code="logout_token_malformed", message="Unreadable logout token."
            ) from exc

        provider = SsoProvider.objects_all_tenants.filter(
            issuer=unverified.get("iss", ""), is_active=True
        ).first()
        if provider is None:
            raise BusinessRuleError(code="issuer_not_trusted", message="Unknown issuer.")

        claims = sso.validated_claims(provider, token, nonce="")
        if "sub" not in claims:
            raise BusinessRuleError(
                code="logout_token_incomplete", message="No subject to sign out."
            )

        set_current_tenant(provider.tenant_id)
        person, ended = _end_sessions_of(provider, claims["sub"])
        if ended:
            # Que las sesiones de alguien se acaben porque lo dice un proveedor es de
            # las cosas que hay que poder responder después: quién lo dijo, de quién y
            # cuántas. El `record()` va aquí, donde ocurre, y no en una función aparte.
            record(
                action=AuditAction.SESSIONS_ENDED,
                actor=None,
                actor_label=f"proveedor · {provider.name}",
                company=provider.tenant,
                target=person,
                target_type="user",
                target_label=(person.get_full_name() or person.email) if person else claims["sub"],
                changes={"issuer": provider.issuer, "sessions_ended": ended},
            )
        return Response({"sessions_ended": ended})


def _end_sessions_of(provider: SsoProvider, subject: str):
    """Blacklists every outstanding refresh token of that person.

    The access token still lives out its fifteen minutes: revoking those would mean
    checking a list on every request, which is the cost this design chose not to pay.
    Fifteen minutes is the window, and it is stated rather than hidden.
    """
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    from apps.users.models import User

    person = User.objects.filter(tenant=provider.tenant, oidc_sub=subject).first()
    if person is None:
        return None, 0
    ended = 0
    for outstanding in OutstandingToken.objects.filter(user=person):
        _row, created = BlacklistedToken.objects.get_or_create(token=outstanding)
        ended += 1 if created else 0
    return person, ended
