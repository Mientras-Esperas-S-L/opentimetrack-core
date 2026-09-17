"""Signing in through the company's identity provider.

The other half of `assertions.py`: there, the managing application's server acts for
somebody with no browser in the middle; here, the person's own browser goes to the
provider and comes back. Both lean on the same `SsoProvider` row, which is the point of
having only one.

Three decisions worth knowing before reading the code:

- **Which provider is asked is decided by the email domain**, not by the person picking
  a button. Somebody typing their work address should not have to know which of their
  employer's identity systems is theirs.
- **The subject anchors the identity, the address only finds it the first time.** An
  address changes -- a surname, a marriage, a corporate rename -- and matching by it
  every time is how two people end up sharing one record.
- **Nothing here decides what somebody may do.** The provider proves who they are;
  what they can see and resolve is this system's business, and stays where it is.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import urllib.error
import urllib.parse
import urllib.request

import jwt
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

from apps.common.exceptions import BusinessRuleError
from apps.tenants.identity import SsoDomain, SsoProvider

logger = logging.getLogger(__name__)

#: Only asymmetric signatures. Letting the provider pick could mean `HS256` with the
#: client secret as the key, or `none`, which are the two classic ways to forge one.
ID_TOKEN_ALGORITHMS = ["RS256", "RS384", "RS512", "ES256", "ES384"]

#: The authorize→callback transient. Short: it is one redirect long.
STATE_TTL_SECONDS = 600
#: The discovery document, which changes about never.
DISCOVERY_TTL_SECONDS = 3600
LEEWAY_SECONDS = 60
HTTP_TIMEOUT = 5

_STATE_PREFIX = "sso:state:"
_DISCOVERY_PREFIX = "sso:discovery:"


def _refuse(code: str, message, **details):
    raise BusinessRuleError(code=code, message=message, details=details)


# ------------------------------------------------------------------- the network


def _checked(url: str) -> str:
    """Only http(s). A `file:` or `ftp:` url in a provider row would otherwise make
    this read the disk of the server, which is the point of the warning."""
    if not url.lower().startswith(("https://", "http://")):
        _refuse("provider_url_invalid", _("The provider's address is not an http(s) url."))
    return url


def _get_json(url: str) -> dict:
    # `_checked` ya limita el esquema a http(s), que es lo que la regla pide.
    request = urllib.request.Request(_checked(url), headers={"Accept": "application/json"})  # noqa: S310
    # El esquema ya lo limita `_checked`, que es justo lo que la regla pide comprobar.
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as answer:  # noqa: S310
        return json.loads(answer.read())


def _post_form(url: str, data: dict) -> tuple[int, dict]:
    body = urllib.parse.urlencode(data).encode()
    request = urllib.request.Request(  # noqa: S310 — el esquema lo limita `_checked`
        _checked(url),
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as answer:  # noqa: S310
            return answer.status, json.loads(answer.read())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except ValueError:
            return exc.code, {}


def discovery(provider: SsoProvider) -> dict:
    """What the provider says about itself: its endpoints and its keys."""
    key = f"{_DISCOVERY_PREFIX}{provider.pk}"
    known = cache.get(key)
    if known:
        return known
    try:
        document = _get_json(provider.well_known_url)
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        logger.warning("sso: discovery failed for %s: %s", provider.issuer, exc)
        _refuse("provider_unreachable", _("Could not reach the identity provider."))
    if document.get("issuer") != provider.issuer:
        # An issuer that does not match what was configured is either a
        # misconfiguration or somebody else's document. Both end the flow here.
        _refuse(
            "issuer_mismatch",
            _("The provider describes itself with a different issuer."),
            expected=provider.issuer,
            found=document.get("issuer", ""),
        )
    cache.set(key, document, DISCOVERY_TTL_SECONDS)
    return document


# --------------------------------------------------------------- who signs in where


def provider_for_email(email: str, company=None) -> SsoProvider | None:
    """The provider that owns that address's domain, if any."""
    domain = (email or "").rsplit("@", 1)[-1].strip().lower()
    if not domain or "@" not in (email or ""):
        return None
    # Sin filtrar por empresa a propósito: **esta consulta es la que averigua cuál
    # es**. Quien llega escribiendo su correo todavía no tiene empresa en contexto, y
    # el aislamiento no se pierde: de aquí sale el proveedor, y del proveedor la
    # empresa a la que pertenece todo lo demás.
    rows = SsoDomain.objects_all_tenants.filter(domain=domain).select_related("provider")
    if company is not None:
        rows = rows.filter(tenant=company)
    row = rows.first()
    if row is None or not row.provider.can_sign_people_in:
        return None
    return row.provider


# ------------------------------------------------------------------ the flow


def _pkce() -> tuple[str, str]:
    """Proof that whoever redeems the code is who asked for it.

    Not optional here even though this is a confidential client: the code travels
    through the browser, and PKCE is what stops a code stolen there from being useful.
    """
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    return verifier, challenge


def authorize_url(provider: SsoProvider, redirect_uri: str) -> str:
    """Where to send the browser, with the transient state kept here."""
    document = discovery(provider)
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(24)
    verifier, challenge = _pkce()

    cache.set(
        f"{_STATE_PREFIX}{state}",
        {
            "provider": provider.pk,
            "nonce": nonce,
            "verifier": verifier,
            "redirect_uri": redirect_uri,
        },
        STATE_TTL_SECONDS,
    )
    params = {
        "client_id": provider.client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": provider.scopes or "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return document["authorization_endpoint"] + "?" + urllib.parse.urlencode(params)


def take_state(state: str) -> dict:
    """The transient, once. Reusing a state is replaying a sign-in."""
    key = f"{_STATE_PREFIX}{state or ''}"
    kept = cache.get(key)
    if not kept:
        _refuse("state_unknown", _("That sign-in attempt expired or was already used."))
    cache.delete(key)
    return kept


def exchange_code(provider: SsoProvider, code: str, verifier: str, redirect_uri: str) -> dict:
    """The authorisation code for tokens, as a confidential client."""
    document = discovery(provider)
    status, payload = _post_form(
        document["token_endpoint"],
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": provider.client_id,
            "client_secret": provider.client_secret,
            "code_verifier": verifier,
        },
    )
    if status != 200 or "id_token" not in payload:
        logger.warning("sso: token exchange failed for %s: %s", provider.issuer, status)
        _refuse("token_exchange_failed", _("The provider did not return a valid token."))
    return payload


def validated_claims(provider: SsoProvider, id_token: str, nonce: str) -> dict:
    """The claims, once the signature and the envelope check out."""
    document = discovery(provider)
    try:
        key = jwt.PyJWKClient(
            document["jwks_uri"], cache_keys=True, lifespan=DISCOVERY_TTL_SECONDS
        ).get_signing_key_from_jwt(id_token)
    except Exception as exc:  # red, JWKS inservible, kid desconocido: misma respuesta
        logger.warning("sso: no key for %s: %s", provider.issuer, exc)
        _refuse("provider_keys_unavailable", _("Could not obtain the provider's signing keys."))

    try:
        claims = jwt.decode(
            id_token,
            key.key,
            algorithms=ID_TOKEN_ALGORITHMS,
            audience=provider.client_id,
            issuer=provider.issuer,
            leeway=LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as exc:
        _refuse(
            "invalid_id_token",
            _("The provider's token did not pass verification."),
            detail=str(exc),
        )

    if nonce and claims.get("nonce") != nonce:
        # Without this, a token obtained elsewhere could be replayed into this sign-in.
        _refuse("nonce_mismatch", _("The provider's answer does not match this sign-in attempt."))
    return claims


# ------------------------------------------------------------ who this person is


def resolve_person(provider: SsoProvider, claims: dict):
    """The person these claims name, creating them only if the company asked for that.

    By subject first, and by address **only when no subject matches yet**: that is the
    first sign-in of somebody who already worked here. From then on the subject is
    stored and the address stops mattering, which is what survives a change of surname.
    """
    from apps.users.models import Role, User

    company = provider.tenant
    subject = (claims.get("sub") or "").strip()
    email = (claims.get(provider.email_claim) or claims.get("email") or "").strip().lower()

    if not subject:
        _refuse("no_subject", _("The provider's token does not identify anybody."))

    person = User.objects.filter(tenant=company, oidc_sub=subject).first()
    if person is not None:
        return person, False

    if email:
        person = User.objects.filter(tenant=company, email__iexact=email).first()
        if person is not None:
            # Anchoring for good: from here on the subject is what identifies them.
            person.oidc_sub = subject
            person.oidc_issuer = provider.issuer
            person.save(update_fields=["oidc_sub", "oidc_issuer"])
            return person, False

    if not provider.auto_provision:
        _refuse(
            "person_not_here",
            _("Nobody here matches that account, and this provider does not create people."),
        )
    if not email:
        _refuse("no_email", _("The provider's token carries no address to create anybody with."))

    person = User(
        tenant=company,
        email=email,
        first_name=(claims.get("given_name") or "").strip(),
        last_name=(claims.get("family_name") or "").strip(),
        oidc_sub=subject,
        oidc_issuer=provider.issuer,
        role=Role.EMPLOYEE,
    )
    # No password at all, rather than one nobody knows: their credentials are the
    # provider's business, and `is_federated` already says so.
    person.set_unusable_password()
    person.save()
    return person, True
