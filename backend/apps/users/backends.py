"""Authentication with email unique per company, not globally.

Django assumes the sign-in field identifies a person across the whole system.
Not here: the same address may belong to two companies, so authentication has to
resolve which one first.

That is why this backend exists, rather than a check to silence.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

User = get_user_model()

#: Cuántas cuentas con el mismo correo se prueban sin que se nombre la empresa.
MAX_CANDIDATES = 10


class CompanyRequired(Exception):
    """El correo y la contraseña valen en más de una empresa: falta decir cuál.

    Solo sale de `authenticate` cuando quien llama lo pide
    (`distinguish_missing_company=True`), que es la pantalla de entrada: ahí se
    convierte en una respuesta propia para que pida el identificador fiscal. El
    resto ---el formulario del admin de Django, cualquier otro--- sigue recibiendo
    `None`, que es lo que espera.
    """


class TenantEmailBackend(ModelBackend):
    """Authenticate by email, scoped to a company when it is known.

    Inherits from `ModelBackend` to keep the permission resolution the Django
    admin relies on, but **replaces** its authentication. It matters that this is
    the only configured backend: were `ModelBackend` left behind as a fallback,
    every security rejection made here -- email ambiguous across companies,
    company deactivated -- would land on it and be accepted, because it only
    looks at the address and `is_active`. Isolation at sign-in would cease to
    exist. Covered by the tests in `test_identity.py`.

    - Given `tenant_id`, the lookup is scoped to that company.
    - Without it, the password is tried against every active account with that
      address, and the one that accepts it signs in.
    - If it fits several, it is rejected. That is deliberate: picking one would
      be guessing, and the right answer is for the caller to name the company.
    """

    def authenticate(
        self,
        request,
        email=None,
        password=None,
        tenant_id=None,
        distinguish_missing_company=False,
        **kwargs,
    ):
        # Django's own login form always calls this with `username=`, whatever
        # USERNAME_FIELD is named, so the alias is not optional: without it the
        # admin site cannot sign anybody in.
        if email is None:
            email = kwargs.get("username") or kwargs.get(User.USERNAME_FIELD)
        if not email or password is None:
            return None

        # Quien es de una empresa desactivada no entra, así que tampoco cuenta
        # como candidato. Contarlo dejaba fuera a otra cuenta con el mismo
        # correo ---la de la instalación, sobre todo, que no tiene identificador
        # fiscal con el que desempatar---.
        lookup = Q(email__iexact=email.strip(), is_active=True) & (
            Q(tenant__isnull=True) | Q(tenant__is_active=True)
        )
        if tenant_id is not None:
            lookup &= Q(tenant_id=tenant_id)

        candidates = list(
            User.objects.filter(lookup).select_related("tenant")[: MAX_CANDIDATES + 1]
        )

        if len(candidates) > MAX_CANDIDATES:
            # Probar la contraseña contra cada una sería una petición que cuesta
            # lo que el atacante quiera: el alta de empresas es libre y cada
            # cuenta añade un hash. Con tantas, la empresa la tiene que decir.
            User().set_password(password)
            if distinguish_missing_company:
                raise CompanyRequired
            return None

        # La contraseña se prueba contra **todas** las candidatas, y con eso se
        # decide. Antes, con dos o más, se rechazaba sin mirarla: quien tenía el
        # mismo correo en una empresa y en la instalación no entraba nunca, por
        # buena que fuera su contraseña.
        #
        # Un hash por candidata, también por las que no tienen contraseña de aquí
        # (las federadas), y uno si no hay ninguna: así el tiempo de respuesta no
        # dice si el correo existe ni si es de una cuenta federada.
        accepted = []
        for user in candidates:
            # A federated account has no usable password here: its identity is
            # governed by the provider.
            if not user.has_usable_password():
                User().set_password(password)
                continue
            if user.check_password(password) and self.user_can_authenticate(user):
                accepted.append(user)
        if not candidates:
            User().set_password(password)

        if len(accepted) == 1:
            return accepted[0]
        if len(accepted) > 1 and distinguish_missing_company:
            # La contraseña vale en más de una empresa: elegir una sería adivinar.
            raise CompanyRequired
        return None

    def user_can_authenticate(self, user) -> bool:
        """Neither the person nor their company may be deactivated."""
        if not user.is_active:
            return False
        if user.tenant_id is not None and not user.tenant.is_active:
            return False
        return True

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
