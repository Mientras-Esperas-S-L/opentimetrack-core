"""Exchanging a signed assertion for a session of the person it names (RFC 7523).

Why this exists rather than the browser flow: the managing application's server
has no browser in front of it when it clocks somebody in, or when it replays a
queue of punches taken in the field with no coverage. The flow it can use is the
one where it signs a short-lived JWT with its own key and this system verifies it
against the issuer's published keys.

The rules, and the reason for each:

- **The person is resolved by their external reference**, not by `oidc_sub`: a
  company may have two providers (its own and the application's), and the subject
  of one names nobody in the other.
- **Sixty seconds of life at most.** It travels server to server; it does not need
  to survive a user reading a screen.
- **`jti` is required and single-use.** Without it, anybody who captured one
  assertion could replay it until it expired.
- **The session carries the application's name**, so a punch made with it is
  recorded as `APPLICATION` and the inspection report says so.
"""

from __future__ import annotations

import logging

import jwt
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

from apps.common.exceptions import BusinessRuleError
from apps.tenants.identity import SsoProvider
from apps.tenants.sso import keys_url

logger = logging.getLogger(__name__)

#: Signature algorithms accepted. Asymmetric only: with a shared secret the
#: issuer's key would also be ours, and then "signed by them" means nothing.
ALGORITHMS = ["RS256", "RS384", "RS512", "ES256", "ES384"]

#: The longest an assertion may live. Server to server, this is plenty.
MAX_LIFETIME_SECONDS = 60

#: Clock tolerance. Two servers are never perfectly in step.
LEEWAY_SECONDS = 30

_JWKS_CACHE_SECONDS = 3600


def _refuse(code: str, message, **details):
    raise BusinessRuleError(code=code, message=message, details=details)


def _provider_for(assertion: str, company) -> SsoProvider:
    """The trusted provider that signed it, read from the unverified `iss`.

    Reading a claim before checking the signature is safe **only** to decide which
    key to check it with, which is exactly what this does: nothing else from the
    unverified token is used, and an unknown issuer never gets that far.
    """
    try:
        claims = jwt.decode(assertion, options={"verify_signature": False})
    except jwt.PyJWTError as exc:
        _refuse("assertion_malformed", _("The assertion is not a readable JWT."), detail=str(exc))

    issuer = claims.get("iss") or ""
    provider = SsoProvider.objects.filter(tenant=company, issuer=issuer, is_active=True).first()
    if provider is None:
        _refuse("issuer_not_trusted", _("This company does not trust that issuer."), iss=issuer)
    if not provider.may_act_for_people:
        _refuse(
            "issuer_may_not_act",
            _("That provider may sign people in, but not act for them."),
            iss=issuer,
        )
    return provider


def _verified_claims(assertion: str, provider: SsoProvider) -> dict:
    """The claims, once the signature and the envelope check out."""
    try:
        signing_key = jwt.PyJWKClient(
            keys_url(provider), cache_keys=True, lifespan=_JWKS_CACHE_SECONDS
        ).get_signing_key_from_jwt(assertion)
    except Exception as exc:  # red caída, JWKS inservible, kid desconocido: misma respuesta
        logger.warning("assertion: no key for %s: %s", provider.issuer, exc)
        _refuse("issuer_keys_unavailable", _("Could not obtain the issuer's signing keys."))

    try:
        claims = jwt.decode(
            assertion,
            signing_key.key,
            algorithms=ALGORITHMS,
            audience=provider.expected_audience,
            issuer=provider.issuer,
            leeway=LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "jti", "aud", "iss"]},
        )
    except jwt.ExpiredSignatureError:
        _refuse("assertion_expired", _("The assertion has expired."))
    except jwt.InvalidAudienceError:
        _refuse("assertion_wrong_audience", _("The assertion is not addressed to this system."))
    except jwt.MissingRequiredClaimError as exc:
        _refuse(
            "assertion_incomplete", _("The assertion is missing a required claim."), claim=str(exc)
        )
    except jwt.PyJWTError as exc:
        _refuse("assertion_invalid", _("The assertion did not pass verification."), detail=str(exc))

    if claims["exp"] - claims["iat"] > MAX_LIFETIME_SECONDS + LEEWAY_SECONDS:
        _refuse(
            "assertion_too_long",
            _("An assertion may live at most %(seconds)d seconds.")
            % {"seconds": MAX_LIFETIME_SECONDS},
        )

    # Single use. The window is the assertion's own life, so the note costs nothing
    # to keep and the replay it stops is the one that matters.
    key = f"assertion:{provider.pk}:{claims['jti']}"
    if not cache.add(key, "1", timeout=MAX_LIFETIME_SECONDS + LEEWAY_SECONDS):
        _refuse("assertion_replayed", _("That assertion was already used."), jti=claims["jti"])

    return claims


def person_from_assertion(assertion: str, company):
    """The person the assertion names, or a refusal that says why."""
    from apps.punches.delegated import resolve_employee

    provider = _provider_for(assertion, company)
    claims = _verified_claims(assertion, provider)

    reference = claims.get("employee_id") or claims.get("sub") or ""
    person = resolve_employee(str(reference), company)
    if person is None:
        _refuse(
            "employee_not_found",
            _("No active person matches the assertion's reference."),
            reference=str(reference),
        )
    return person, provider
