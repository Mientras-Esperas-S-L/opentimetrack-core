"""Identity and organisation endpoints."""

from __future__ import annotations

import logging

import django_filters
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
from apps.audit.trail import StructureTrail
from apps.common.clock import local_today
from apps.common.exceptions import BusinessRuleError
from apps.common.models import set_current_tenant
from apps.common.permissions import (
    IsAdmin,
    IsAuthenticatedInTenant,
    IsManagerOrAdmin,
    ReadForAllWriteForAdmin,
)
from apps.common.scope import people_queryset
from apps.reports.delivery import send_delivery_email
from apps.users.models import Department, Role, Workplace
from apps.users.passwords import resolve_token, revoke_sessions, send_account_email
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


class SessionSerializer(serializers.Serializer):
    """Lo que devuelven entrar, darse de alta y poner contraseña.

    Las tres se publicaban como `responses={200: None}` ---«sin cuerpo»--- y las
    tres devuelven los tokens. Es **la primera llamada** que hace cualquier
    integración, así que el contrato no solo estaba incompleto: no nombraba
    siquiera el campo `access`, y quien lo escribiera a mano tenía que adivinar
    entre `access`, `token`, `access_token` o `jwt`. Un cliente generado del
    esquema tipaba el retorno como vacío.
    """

    access = serializers.CharField(help_text="JWT de la persona. Va en `Authorization: Bearer`.")
    refresh = serializers.CharField(help_text="Se cambia por uno nuevo en /api/auth/refresh/.")
    user = UserSerializer()
    tenant = TenantSerializer()


@extend_schema(tags=["auth"])
class SignUpView(APIView):
    """Registers a company and its first administrator."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "login"

    @extend_schema(request=SignUpSerializer, responses={201: SessionSerializer}, auth=[])
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

    @extend_schema(request=SignInSerializer, responses={200: SessionSerializer}, auth=[])
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

        Lo que llega aquí no ha pasado por ninguna validación ---se llama porque
        el serializador **falló**--- y esta es la puerta de la calle: sin sesión,
        alcanzable desde Internet, y lo primero que prueba cualquiera. Con
        `{"email": 12}` la línea de abajo hacía `12.strip()` y devolvía un 500.

        La ironía es la parte que conviene recordar: esta función existe para
        dejar constancia de los intentos fallidos, que son la forma de un
        ataque, y se rompía justo con la entrada que más se parece a uno. En vez
        de la línea de registro salía una traza. Encontrado con una sonda que
        mete tipos equivocados en cada campo.
        """
        crudo = request.data.get("email") if isinstance(request.data, dict) else None
        email = crudo.strip().lower() if isinstance(crudo, str) else ""
        logger.warning(
            "Failed sign-in for %s from %s",
            email or "(no address)",
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR"),
        )


class RefreshRequestSerializer(serializers.Serializer):
    """El token de refresco. Va en el cuerpo, no en la cabecera.

    Existe para que el esquema lo diga. Estas dos operaciones se publicaban con
    `request=None` y las dos leen el cuerpo: quien integrara leyendo el contrato
    mandaba una petición vacía.
    """

    refresh = serializers.CharField()


@extend_schema(tags=["auth"])
class RefreshView(APIView):
    """Trades a refresh token for a fresh access token.

    Missing until 13/08/2026, and its absence was invisible in the tests and
    brutal in use: sign-in handed out a refresh token good for seven days,
    the browser stored it, and there was nowhere to spend it. So every session
    died fifteen minutes in --- mid form, mid roster, mid anything --- and
    dumped the person back at the sign-in screen having lost what they were
    doing.

    Rotation is on (`ROTATE_REFRESH_TOKENS`), so the answer carries a new
    refresh token and blacklists the one just used: a token that leaks is worth
    one use, and using it twice is what gives the theft away.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    # Cubeta propia, no la del login. Ver el comentario en los ajustes: son
    # llamadas anónimas, así que el límite va por IP, y compartirlo echaba del
    # panel a una oficina entera detrás del mismo NAT.
    throttle_scope = "session_renewal"

    @extend_schema(request=RefreshRequestSerializer, responses={200: dict})
    def post(self, request):
        token = request.data.get("refresh")
        if not token:
            raise BusinessRuleError(code="no_refresh_token", message=_("No session to renew."))
        try:
            refresh = RefreshToken(token)
            access = str(refresh.access_token)
            if settings.SIMPLE_JWT.get("ROTATE_REFRESH_TOKENS"):
                if settings.SIMPLE_JWT.get("BLACKLIST_AFTER_ROTATION"):
                    refresh.blacklist()
                refresh.set_jti()
                refresh.set_exp()
                refresh.set_iat()
        except TokenError as exc:
            # Expired, blacklisted or forged: all the same answer. Telling them
            # apart would say whether a token ever existed.
            raise BusinessRuleError(
                code="session_expired", message=_("The session has expired. Sign in again.")
            ) from exc

        return Response({"access": access, "refresh": str(refresh)})


@extend_schema(tags=["auth"])
class SignOutView(APIView):
    """Invalidates the refresh token, so signing out actually signs out."""

    permission_classes = [IsAuthenticatedInTenant]

    @extend_schema(request=RefreshRequestSerializer, responses={204: None})
    def post(self, request):
        token = request.data.get("refresh")
        if not token:
            # Sin token no se invalida nada, y devolver 204 sería mentir en el
            # peor sitio: quien integra lee «204», da la sesión por cerrada, y
            # el token de refresco sigue valiendo una semana. El esquema decía
            # `request=None`, así que un cliente escrito leyendo el contrato
            # mandaba justo la petición vacía.
            raise BusinessRuleError(
                code="no_refresh_token",
                message=_("Send the refresh token to close the session."),
            )
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


class DeactivationSerializer(serializers.Serializer):
    """Lo que deja atrás una baja.

    Esta operación pasó hoy de 204 mudo a 200 con cuerpo, y el esquema se quedó
    prometiendo el 204: quien integrara leyendo el contrato no sabría que la
    respuesta trae el recuento que le dice si hay un cuadrante que rehacer.
    """

    future_shifts = serializers.IntegerField(
        help_text="Turnos que le quedaban asignados después de la baja. No se han borrado."
    )


class MeEnvelopeSerializer(serializers.Serializer):
    """Quién eres y en qué empresa. Se declaraba como `User` a secas.

    Un cliente generado leía `respuesta.first_name` y recibía `undefined`: el
    nombre está un nivel más abajo, en `user`.
    """

    user = UserSerializer()
    tenant = TenantSerializer()


@extend_schema(tags=["auth"])
class MeView(APIView):
    permission_classes = [IsAuthenticatedInTenant]

    @extend_schema(responses={200: MeEnvelopeSerializer})
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


class PeopleFilter(django_filters.FilterSet):
    """Los filtros de la lista de personas.

    `can_manage` existe por un motivo concreto: el campo de «quién lleva el
    departamento» ofrecía a toda la plantilla y el servidor solo acepta perfiles
    que puedan gestionar, así que elegir a un operario daba un 400 después de
    haberlo elegido. Un desplegable que ofrece lo que luego se niega es una
    trampa, y la salida es no ofrecerlo.
    """

    can_manage = django_filters.BooleanFilter(method="filter_can_manage")

    #: «Sin departamento», que no se puede pedir con `?department=`: un
    #: parámetro vacío es indistinguible de no mandarlo. Y es la primera
    #: pregunta de cualquier reorganización --- quién se ha quedado suelto ---
    #: así que necesita su propio filtro en vez de mirarse a ojo.
    no_department = django_filters.BooleanFilter(field_name="department", lookup_expr="isnull")

    #: Declarados a mano, y no por `Meta.fields`, porque generados solos **no
    #: funcionaban**: `django-filter` construye la lista de opciones válidas al
    #: importar el módulo, y en ese momento no hay empresa en el contexto. Los
    #: gestores de un `TenantOwnedModel` devuelven vacío sin empresa, así que la
    #: lista quedaba vacía para siempre y **cualquier** identificador daba
    #: «Escoja una opción válida».
    #:
    #: `?department=` llevaba así desde que existe: la API lo anunciaba y no
    #: filtraba nada. Salió el 13/08/2026 al estrenar el filtro en la pantalla
    #: de Personas --- por eso ahora hay una prueba que lo pide con un
    #: identificador de verdad.
    #:
    #: Con `queryset` como función, se resuelve dentro de la petición y ve lo
    #: que tiene que ver.
    department = django_filters.ModelChoiceFilter(queryset=lambda request: Department.objects.all())
    workplace = django_filters.ModelChoiceFilter(queryset=lambda request: Workplace.objects.all())

    class Meta:
        model = User
        fields = [
            "role",
            "department",
            # El centro decide los festivos locales y la zona horaria en la que
            # se mide la jornada, así que separar por él no es cosmético.
            "workplace",
            "is_active",
            "is_worker_representative",
        ]

    def filter_can_manage(self, queryset, name, value):
        managing = {Role.MANAGER, Role.ADMIN}
        return queryset.filter(role__in=managing) if value else queryset.exclude(role__in=managing)


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
    filterset_class = PeopleFilter
    search_fields = ["first_name", "last_name", "email", "employee_id"]
    ordering_fields = ["last_name", "date_joined"]

    def get_queryset(self):
        # Users are not a TenantOwnedModel -- sign-in has to find them before the
        # company is known -- so the scoping is explicit here, and it is by what
        # the caller answers for rather than by company.
        # `workplace` y `tenant` porque la ficha lleva la zona en la que se
        # parte el día de esa persona, que sale de su centro o ---si no
        # tiene--- de la empresa. Sin los dos se preguntaba una vez por
        # persona: diez consultas con tres y diecinueve con doce, que es lo
        # que cazó `test_no_crece_con_la_plantilla` en cuanto se añadió el
        # campo.
        return people_queryset(self.request.user).select_related(
            "department", "workplace", "tenant"
        )

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

    @extend_schema(request=None, responses={200: dict})
    @action(detail=True, methods=["post"], url_path="deliver-record")
    def deliver_record(self, request, pk=None):
        """Manda a esa persona un enlace para descargar su propio registro.

        **Existe sobre todo para quien ya no trabaja aquí.** El art. 34.9 obliga
        a conservar su registro cuatro años y el art. 15 del RGPD le da derecho a
        pedirlo, y las dos cosas siguen valiendo después del último día: lo que
        se acaba es la relación laboral, no el derecho sobre los datos.

        Se permite igual con las cuentas activas: quien está de alta lo tiene en
        su pantalla, pero puede haber perdido el acceso, y no hay razón para que
        la administración tenga que elegir entre reactivar a alguien y atender su
        solicitud.

        El enlace no abre sesión. Ver `apps.reports.delivery`.
        """
        person = self.get_object()
        if not person.email:
            raise BusinessRuleError(
                code="no_address",
                message=_("There is no address to send it to. Add one first."),
            )

        send_delivery_email(person, base_url=settings.FRONTEND_URL)
        record(
            action=AuditAction.RECORD_DELIVERED,
            actor=request.user,
            target=person,
            target_type="user",
            target_label=person.get_full_name() or person.email,
            changes={"sent_to": person.email, "picked_up": False},
            note="" if person.is_active else "cuenta de baja",
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
            )
        else:
            record(
                action=AuditAction.PERSON_UPDATED,
                actor=self.request.user,
                target=person,
                target_label=person.get_full_name() or person.email,
            )

    @extend_schema(responses={200: DeactivationSerializer})
    def destroy(self, request, *args, **kwargs):
        """Devuelve cuántos turnos quedan colgando, en vez de un 204 mudo.

        Dar de baja a alguien deja sus turnos futuros sin nadie que los trabaje,
        y hasta ahora la pantalla no lo decía. Quien lo necesita saber es quien
        acaba de pulsar, en ese momento: es quien va a tener que rehacer el
        cuadrante, y si se entera tres días después ya han pasado tres días de
        ausencias sin justificar.
        """
        self._turnos_pendientes = 0
        super().destroy(request, *args, **kwargs)
        return Response({"future_shifts": self._turnos_pendientes})

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

        # Una baja sin fecha no se puede responder, y eso es justo lo que
        # faltaba. `is_active` es un sí o un no sin día, así que nada de lo que
        # razona por fechas ---la revisión del cuadrante, las ausencias--- podía
        # enterarse: quien se iba seguía con sus turnos del mes que viene
        # asignados, y como el cuadrante es contra lo que se comparan los
        # fichajes, iba a salir como ausencia sin justificar cada día.
        #
        # La fecha es hoy, en la zona de la empresa. Se pisa un `contract_end`
        # posterior porque irse antes de que venza el contrato es lo corriente
        # ---una baja voluntaria, un despido--- y lo que la fecha tiene que
        # decir es el último día que la relación cubre. Uno anterior no se toca:
        # ese contrato ya había terminado y la baja solo lo formaliza en el
        # sistema.
        campos = ["is_active"]
        hoy = local_today(instance)
        if instance.contract_end is None or instance.contract_end > hoy:
            instance.contract_end = hoy
            campos.append("contract_end")

        instance.is_active = False
        instance.save(update_fields=campos)

        # Y se cierran sus sesiones. El acceso deja de valer al instante ---la
        # autenticación mira `is_active`--- pero el refresco vivía siete días y
        # rotando, así que el móvil de quien acaba de irse seguía teniendo una
        # credencial viva.
        #
        # Lo que lo hace concreto es que la baja es **reversible**: medido, al
        # reincorporar a la persona su sesión de antes volvía a funcionar sin que
        # hubiera vuelto a escribir la contraseña.
        revoke_sessions(instance)

        # Los turnos que le quedaban no se borran, que es la promesa de esta
        # pantalla: dar de baja no borra nada. Se cuentan para decirlo, y a
        # partir de ahora la revisión del cuadrante los marca sola, porque ya
        # hay una fecha contra la que compararlos.
        from apps.shifts.models import Shift

        pendientes = Shift.objects.filter(employee=instance, day__gt=hoy).count()
        # Se guarda para que `destroy` lo devuelva: quien acaba de dar la baja es
        # quien tiene que ir a rehacer el cuadrante, y el momento de enterarse
        # es ahora y no cuando alguien abra la pantalla del cuadrante.
        self._turnos_pendientes = pendientes

        record(
            action=AuditAction.PERSON_DEACTIVATED,
            actor=self.request.user,
            target=instance,
            target_label=instance.get_full_name() or instance.email,
            changes={"contract_end": hoy.isoformat(), "future_shifts": pendientes},
            note=(
                str(_("Left on %(day)s. %(count)s shift(s) still rostered after that."))
                % {"day": hoy.isoformat(), "count": pendientes}
                if pendientes
                else str(_("Left on %(day)s.")) % {"day": hoy.isoformat()}
            ),
        )


@extend_schema(tags=["organisation"])
class DepartmentViewSet(StructureTrail, viewsets.ModelViewSet):
    queryset = Department.objects.none()
    serializer_class = DepartmentSerializer
    permission_classes = [ReadForAllWriteForAdmin]
    filterset_fields = ["is_active"]
    search_fields = ["name"]
    trail_fields = ("name", "is_active")

    def get_queryset(self):
        return Department.objects.all()

    def perform_create(self, serializer):
        self.anotar(serializer.save(tenant=self.request.user.tenant), _("Added"))

    def perform_destroy(self, instance):
        """Refused while somebody answers for it, and no `SET_NULL` will do.

        For the people **in** the department, losing it is tidy: they keep
        everything and lose a label. For the people **in charge of** it, it is
        the opposite, and that asymmetry is what made this easy to miss.

        **The reason changed, and the refusal stayed.** When this was written,
        `visible_people` read "in charge of nothing" as "nothing narrows them",
        so retiring somebody's only department did the opposite of prudent:
        measured on a live company, a manager went from seeing 2 people to
        seeing all of them, and a medical certificate from another department
        went from 404 to 200 --- art. 9 GDPR, reachable by somebody who never
        answered for that person. Nobody had touched their permissions, and the
        trail said "department deleted", not "she can now read the whole
        company".

        That widening is closed at the source now: `visible_people` tells apart
        *nothing has been decided here yet* from *it has been decided and you
        run none of them*, so this road no longer leads anywhere dangerous.

        What is left is the opposite consequence, and it is still worth
        refusing over: those managers stop being able to read **anybody but
        themselves**, which is not what somebody deleting a department is
        trying to do to them. Moving them first is a decision taken on purpose
        and leaves its own trail.

        Note the asymmetry: `PATCH` with an empty `managers` list reaches the
        same state and answers 200. Whether that should refuse too is a product
        question, written down in the notebook rather than decided here.
        """
        managers = instance.managers.filter(is_active=True).count()
        if managers:
            raise BusinessRuleError(
                code="department_has_managers",
                message=_(
                    "%(count)s people answer for this department. Move them first: "
                    "leaving them in charge of nothing means they can no longer read "
                    "anybody's record but their own."
                )
                % {"count": managers},
            )
        super().perform_destroy(instance)


@extend_schema(tags=["organisation"])
class WorkplaceViewSet(StructureTrail, viewsets.ModelViewSet):
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
    # `time_zone` es el que de verdad hay que poder mirar: es con la que se mide
    # la jornada de su gente, así que cambiarla mueve el límite del día de todos
    # a la vez y sin tocar ni un fichaje.
    trail_fields = ("name", "time_zone", "region", "municipality", "is_active")

    def get_queryset(self):
        return Workplace.objects.all()

    def perform_create(self, serializer):
        self.anotar(serializer.save(tenant=self.request.user.tenant), _("Added"))

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
        super().perform_destroy(instance)


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

    @extend_schema(request=PasswordSetSerializer, responses={200: SessionSerializer}, auth=[])
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

        # Y se cierran las sesiones que hubiera abiertas, **antes** de emitir la
        # nueva --- si no, se revocaría la que se acaba de dar.
        #
        # Quien cambia su contraseña suele estar haciendo justo esto: recuperar
        # una cuenta porque cree que le han visto la clave o ha perdido el móvil.
        # Medido antes de esta línea: ese móvil seguía renovando la sesión y
        # leyendo datos después del cambio. Recuperar la cuenta no echaba a nadie.
        revoke_sessions(user)

        # Straight in, so nobody has to type the password they just chose.
        return Response(
            {
                **issue_tokens(user),
                "user": UserSerializer(user).data,
                "tenant": TenantSerializer(user.tenant).data if user.tenant else None,
            }
        )
