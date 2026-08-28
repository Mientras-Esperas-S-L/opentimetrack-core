"""Serializers for identity and organisation."""

from __future__ import annotations

from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps import legal
from apps.common.campos import DecimalesTolerantes
from apps.common.clock import local_today
from apps.tenants.models import Tenant, validate_time_zone
from apps.users.models import (
    ActivityPeriod,
    AdaptationStatus,
    Department,
    RemoteWorkAgreement,
    Role,
    ScheduleAdaptation,
    Workplace,
)

User = get_user_model()

#: Para distinguir «no mandaron el campo» de «lo mandaron vacío». `None` no
#: sirve de centinela porque una lista vacía es un valor legítimo con
#: significado propio, y confundir los dos vacía lo que nadie pidió vaciar.
_SIN_TOCAR = object()


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name", "tax_id", "country", "time_zone", "language"]
        read_only_fields = ["id"]


class WorkplaceSerializer(serializers.ModelSerializer):
    people_count = serializers.SerializerMethodField()
    region_name = serializers.SerializerMethodField()
    #: What the workplace's day is actually sliced in, resolved. The field can
    #: be empty and mean "the company's", and a screen that showed the blank
    #: would be hiding the answer rather than saying there is a default.
    effective_time_zone = serializers.SerializerMethodField()

    class Meta:
        model = Workplace
        fields = [
            "id",
            "name",
            "address",
            "municipality",
            "municipality_code",
            "region",
            "region_name",
            "time_zone",
            "effective_time_zone",
            "is_active",
            "people_count",
        ]
        read_only_fields = ["id", "people_count", "region_name", "effective_time_zone"]

    def get_people_count(self, obj) -> int:
        return obj.people.filter(is_active=True).count()

    def get_region_name(self, obj) -> str:
        framework = legal.for_company(self.context["request"].user.tenant)
        return framework.regions.get(obj.region, "")

    def get_effective_time_zone(self, obj) -> str:
        return str(obj.tzinfo)

    def validate_region(self, value):
        """A code the country actually has.

        Free text here would be the same mistake as a calendar keyed by name:
        it looks stored and quietly matches nothing when the holidays arrive.
        """
        if not value:
            return value
        framework = legal.for_company(self.context["request"].user.tenant)
        if framework.regions and value not in framework.regions:
            raise serializers.ValidationError(
                _("%(code)s is not a region of %(country)s.")
                % {"code": value, "country": framework.name}
            )
        return value

    def validate_time_zone(self, value):
        if value:
            validate_time_zone(value)
        return value


class DepartmentSerializer(serializers.ModelSerializer):
    people_count = serializers.SerializerMethodField()
    manager_names = serializers.SerializerMethodField()

    #: Quién está dentro. El vínculo vive en la persona ---`User.department`---
    #: así que este campo es el lado inverso y hay que escribirlo a mano.
    #:
    #: Existe porque sin él la pantalla que se llama «Departamentos» era justo
    #: donde no se podía componer uno: los miembros se asignaban desde la ficha
    #: de cada persona, de una en una. Quince personas, quince diálogos.
    members = serializers.ListField(child=serializers.UUIDField(), required=False)
    member_names = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "people_count",
            # Who answers for it, which is what decides who reads whose record.
            "managers",
            "manager_names",
            # Y quién está dentro, que es cosa distinta: alguien de oficina
            # puede llevar la brigada sin pertenecer a ella.
            "members",
            "member_names",
        ]
        read_only_fields = ["id", "people_count", "manager_names", "member_names"]

    def get_people_count(self, obj) -> int:
        return obj.users.filter(is_active=True).count()

    def get_manager_names(self, obj) -> list[str]:
        return [person.get_full_name() for person in obj.managers.all()]

    def get_member_names(self, obj) -> list[str]:
        return [person.get_full_name() for person in obj.users.filter(is_active=True)]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["members"] = [str(person.id) for person in instance.users.filter(is_active=True)]
        return data

    def create(self, validated_data):
        members = validated_data.pop("members", None)
        department = super().create(validated_data)
        self._set_members(department, members)
        return department

    def update(self, instance, validated_data):
        # `pop` con centinela y no `.get(...) or []`: **omitir** el campo en un
        # PATCH significa «no lo toques», y una lista vacía significa «vacíalo».
        # Confundirlos aquí dejaría sin departamento a toda la plantilla cada
        # vez que alguien renombra uno.
        members = validated_data.pop("members", _SIN_TOCAR)
        department = super().update(instance, validated_data)
        if members is not _SIN_TOCAR:
            self._set_members(department, members)
        return department

    def _set_members(self, department, members) -> None:
        """Deja dentro exactamente a quien diga la lista, y a nadie más.

        Quien sale se queda **sin departamento**, no se borra ni se desactiva:
        estar fuera de un departamento es un estado normal, y el modelo lo
        permite a propósito.

        Cada cambio se apunta persona a persona en el registro de actividad. Es
        lo mismo que hace la ficha individual, y tiene que seguir siendo así:
        cambiar de departamento decide quién puede leer el registro de quién, y
        una reorganización de veinte personas no puede aparecer como un solo
        apunte sin nombres.
        """
        if members is None:
            return

        from apps.audit.models import AuditAction
        from apps.audit.services import record

        company = department.tenant
        request = self.context.get("request")
        actor = getattr(request, "user", None)

        quiere = set(members)
        dentro = {person.id for person in department.users.all()}

        entran = User.objects.filter(tenant=company, pk__in=quiere - dentro)
        # Una persona que no es de esta empresa sencillamente no aparece en la
        # consulta, así que un identificador ajeno no hace nada. Silencioso a
        # propósito: decir «esa persona no existe aquí» confirmaría que existe
        # en algún sitio.
        salen = User.objects.filter(tenant=company, pk__in=dentro - quiere)

        for person in [*entran, *salen]:
            antes = person.department.name if person.department_id else ""
            person.department = department if person.id in quiere else None
            person.save(update_fields=["department", "updated_at"])
            record(
                action=AuditAction.PERSON_UPDATED,
                actor=actor,
                target=person,
                target_label=person.get_full_name() or person.email,
                changes={
                    "department": [antes, person.department.name if person.department else ""]
                },
            )

    def validate_managers(self, value):
        """Somebody in this company, and somebody who can actually manage.

        Putting an employee in charge of a department would not grant them
        anything --- the scope only applies to the manager profile --- so it
        would read as a permission given and be none at all.
        """
        company = self.context["request"].user.tenant
        for person in value:
            if person.tenant_id != company.id:
                raise serializers.ValidationError(
                    _("Somebody in that list is not in this company.")
                )
            if not person.can_manage:
                raise serializers.ValidationError(
                    _(
                        "%(name)s does not have a manager profile, so putting them in "
                        "charge would grant nothing."
                    )
                    % {"name": person.get_full_name()}
                )
        return value


class UserSerializer(DecimalesTolerantes, serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)
    workplace_name = serializers.CharField(source="workplace.name", read_only=True, default=None)
    #: En la que se parte **su** día, resuelta: la de su centro de trabajo si lo
    #: tiene, y si no la de la empresa.
    #:
    #: Salía solo la de la empresa, y las pantallas no tenían otra cosa que
    #: usar. Para una delegación en Las Palmas eso son sesenta minutos: quien
    #: fichaba a las 23:30 lo veía en su pantalla como las 00:30 **del día
    #: siguiente**, mientras el informe que se entrega ---que sí resuelve por
    #: persona--- lo ponía en el día correcto. El registro que uno consulta y el
    #: que se entrega tienen que ser el mismo (art. 34.9).
    effective_time_zone = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "employee_id",
            "department",
            "department_name",
            "workplace",
            "workplace_name",
            "effective_time_zone",
            "locale",
            "annual_leave_days",
            # Art. 3.b and 3.e of the pending decree: the regime the person
            # works under. Part of the record's minimum content, so it has to
            # reach the report --- and to reach it, somebody has to be able to
            # enter it.
            "regime",
            "contracted_hours",
            "contracted_period",
            "contract_start",
            "contract_end",
            "seasonal",
            "contracted_schedule",
            "default_work_mode",
            # Art. 36 ET. Neither is a property of the shift: a night worker
            # carries the eight-hour average on every day they work, and
            # rotating shifts change which rest applies at a changeover.
            "night_worker",
            "rotating_shifts",
            "voluntary_night_shift",
            # Only for the under-eighteen protections. Without it none of them
            # apply, and `age_is_known` stays false, which is the system saying
            # it does not know rather than assuming an adult.
            "date_of_birth",
            # Art. 4.b: informed when somebody disagrees with a change to their
            # record. With nobody marked, that obligation can never be met.
            "is_worker_representative",
            "wants_punch_reminders",
            "is_active",
            "is_federated",
            "date_joined",
        ]
        read_only_fields = [
            "id",
            "full_name",
            "department_name",
            "workplace_name",
            "effective_time_zone",
            "is_federated",
            "date_joined",
        ]

    def get_effective_time_zone(self, obj) -> str:
        return str(obj.tzinfo)


class UserWriteSerializer(DecimalesTolerantes, serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=12)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "employee_id",
            "department",
            "workplace",
            "locale",
            "regime",
            "contracted_hours",
            "contracted_period",
            "contract_start",
            "contract_end",
            "seasonal",
            "contracted_schedule",
            "default_work_mode",
            "night_worker",
            "rotating_shifts",
            "voluntary_night_shift",
            "date_of_birth",
            "is_worker_representative",
            "wants_punch_reminders",
            "is_active",
            "password",
        ]
        read_only_fields = ["id"]

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        company = self.context["request"].user.tenant
        existing = User.objects.filter(tenant=company, email=value)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError(_("Somebody in this company already uses it."))
        return value

    def validate_employee_id(self, value: str) -> str:
        """Único dentro de la empresa, cuando lo hay.

        La base ya lo impide, pero un choque contra la restricción sale como un
        500 y quien lo ve no sabe qué corregir. Aquí sale como lo que es: un
        número que ya usa otra persona.

        En blanco es lo normal en una empresa que no numera a su gente, y no
        puede chocar consigo mismo.
        """
        value = (value or "").strip()
        if not value:
            return value

        # `iexact` y no exacto, porque **el resto del producto ya trata
        # «EMP-9» y «emp-9» como la misma persona**: así los busca `_resolve`
        # en la puerta de integración y así los busca el fichaje delegado, que
        # además rechaza la referencia por ambigua si encuentra dos.
        #
        # Comparando exacto, esta puerta dejaba crear las dos. Medido: quedaban
        # dos personas, `_resolve` devolvía una de ellas ---la primera, sin
        # decir que había otra--- y el fichaje delegado se plantaba con
        # «la referencia coincide con más de una persona» para todo el mundo.
        company = self.context["request"].user.tenant
        existing = User.objects.filter(tenant=company, employee_id__iexact=value)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if (otra := existing.first()) is not None:
            raise serializers.ValidationError(
                _("%(name)s already uses that staff number.")
                % {"name": otra.get_full_name() or otra.email}
            )
        return value

    def validate_workplace(self, value):
        # Same belt and braces as the department, and it matters more here: a
        # workplace from another company would decide this person's time zone.
        if value is not None and value.tenant_id != self.context["request"].user.tenant_id:
            raise serializers.ValidationError(_("That workplace belongs to another company."))
        return value

    def validate_department(self, value):
        # Belt and braces: the queryset is already scoped, but an explicit check
        # here turns a potential cross-company reference into a clear error.
        if value is not None and value.tenant_id != self.context["request"].user.tenant_id:
            raise serializers.ValidationError(_("That department belongs to another company."))
        return value

    def validate_date_of_birth(self, value):
        """Refuses a date that cannot belong to somebody who works here.

        This field decides whether the under-eighteen protections apply, so a
        typo in it is not cosmetic: a mistyped year turns a minor into an adult
        and the eight-hour limit, the thirty-minute break and the ban on night
        work all stop being checked, silently.
        """
        if value is None:
            return value

        today = timezone.localdate()
        if value >= today:
            raise serializers.ValidationError(_("It cannot be today or a future date."))

        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        # Below the country's minimum working age it is a typo, or somebody who
        # should not be recorded as an employee at all.
        framework = legal.for_company(self.context["request"].user.tenant)
        citation = framework.minors.citations.get("minimum_age")
        if age < 16:
            raise serializers.ValidationError(
                _("That gives an age of %(age)s, below the minimum working age. %(basis)s")
                % {"age": age, "basis": citation.basis if citation else ""}
            )
        if age > 100:
            raise serializers.ValidationError(_("That gives an age of over a hundred years."))
        return value

    def validate(self, attrs):
        """The figure and the regime have to agree.

        Art. 3.b asks for the regime and the agreed hours, and they only mean
        anything together: a part-time contract without a figure leaves empty
        the number the article requires, and a figure on a contract with no
        agreed hours is a leftover somebody forgot to clear when the terms
        changed.
        """
        from apps.users.models import HoursPeriod, WorkingTimeRegime

        current = self.instance
        regime = attrs.get("regime", getattr(current, "regime", WorkingTimeRegime.FULL_TIME))
        hours = attrs.get("contracted_hours", getattr(current, "contracted_hours", None))
        period = attrs.get(
            "contracted_period", getattr(current, "contracted_period", HoursPeriod.WEEK)
        )

        if regime == WorkingTimeRegime.VARIABLE and hours is not None:
            raise serializers.ValidationError(
                {
                    "contracted_hours": _(
                        "There is no agreed figure on this regime. Clear it, or choose "
                        "one that has hours."
                    )
                }
            )

        # Los tres formativos, no solo el que había antes de separarlos: la
        # obligación del art. 3.b es de todos, y dejar fuera a los nuevos por
        # olvido habría abierto un hueco justo el día de la separación.
        pide_horas = {
            WorkingTimeRegime.PART_TIME,
            WorkingTimeRegime.TRAINING,
            WorkingTimeRegime.TRAINING_ALTERNATING,
            WorkingTimeRegime.TRAINING_PRACTICE,
        }
        if regime in pide_horas and hours is None:
            raise serializers.ValidationError(
                {"contracted_hours": _("Art. 3.b asks for the agreed hours on this regime.")}
            )

        start = attrs.get("contract_start", getattr(current, "contract_start", None))
        finish = attrs.get("contract_end", getattr(current, "contract_end", None))
        if start and finish and finish < start:
            raise serializers.ValidationError({"contract_end": _("It ends before it starts.")})

        if hours is not None and hours <= 0:
            raise serializers.ValidationError({"contracted_hours": _("It has to be above zero.")})

        # Art. 6.2 ET is a prohibition, not a limit, so there is no amount of
        # night work to allow and nothing to warn about: the answer is no. The
        # roster already refuses to plan it; refusing it here as well stops the
        # status being recorded for somebody it cannot lawfully apply to, which
        # would then switch on the eight-hour average and hide the real problem
        # behind a lesser one.
        night = attrs.get("night_worker", getattr(current, "night_worker", "AUTO"))
        born = attrs.get("date_of_birth", getattr(current, "date_of_birth", None))
        if night == "YES" and born:
            from apps.users.models import User as Person

            probe = Person(date_of_birth=born)
            if probe.is_minor_on(timezone.localdate()):
                framework = legal.for_company(self.context["request"].user.tenant)
                citation = framework.minors.citations.get("night_work")
                raise serializers.ValidationError(
                    {
                        "night_worker": _(
                            "%(basis)s: workers under eighteen may not work at night, so "
                            "the status cannot apply to them."
                        )
                        % {"basis": citation.basis if citation else ""}
                    }
                )

        # A weekly figure above the company's ordinary week is either a typo or
        # a contract that does not hold: art. 34.1 ET is a ceiling and no
        # contract may agree past it.
        if hours is not None and period == HoursPeriod.WEEK:
            from apps.tenants.rules import WorkingTimeRules

            company = self.context["request"].user.tenant
            ceiling = WorkingTimeRules.for_company(company).weekly_hours
            if hours > ceiling:
                raise serializers.ValidationError(
                    {
                        "contracted_hours": _(
                            "%(hours)s h a week is above the company's %(ceiling)s h. A "
                            "contract cannot agree past the legal maximum."
                        )
                        % {"hours": f"{hours:g}", "ceiling": f"{ceiling:g}"}
                    }
                )

        return attrs

    def create(self, validated):
        password = validated.pop("password", None)
        company = self.context["request"].user.tenant

        user = User(tenant=company, **validated)
        if password:
            user.set_password(password)
        else:
            # No password yet: they will set one through the reset flow. An
            # account that cannot be signed into is safer than a default one.
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated):
        password = validated.pop("password", None)
        for field, value in validated.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class SignUpSerializer(serializers.Serializer):
    """Registers a company and its first administrator in one step."""

    company_name = serializers.CharField(max_length=255)
    tax_id = serializers.CharField(max_length=32)
    country = serializers.CharField(max_length=2, default="ES")
    time_zone = serializers.CharField(max_length=64, required=False)

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=12)
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)

    def validate_tax_id(self, value: str) -> str:
        value = value.strip().upper()
        if Tenant.objects.filter(tax_id=value).exists():
            raise serializers.ValidationError(_("A company with this tax number already exists."))
        return value

    def validate_time_zone(self, value: str) -> str:
        validate_time_zone(value)
        return value

    @transaction.atomic
    def create(self, validated):
        company = Tenant.objects.create(
            name=validated["company_name"],
            tax_id=validated["tax_id"],
            country=validated["country"].upper(),
            **({"time_zone": validated["time_zone"]} if validated.get("time_zone") else {}),
        )
        admin = User.objects.create_user(
            email=validated["email"],
            password=validated["password"],
            tenant=company,
            first_name=validated["first_name"],
            last_name=validated["last_name"],
            role=Role.ADMIN,
        )

        # El catálogo de permisos del país, desde el minuto uno.
        #
        # Sin esto una empresa recién dada de alta se quedaba con **cero**
        # permisos: el desplegable de «Qué pides» salía vacío y nadie podía
        # pedir un matrimonio, un fallecimiento ni una hospitalización. Todo el
        # art. 37.3 quedaba fuera del producto, y no había forma de meterlo
        # desde ninguna pantalla --- el endpoint que lo siembra existía y no lo
        # llamaba nadie.
        #
        # Que sea automático no contradice el «copiar y no referenciar» del
        # catálogo: esa decisión es sobre las ediciones de después. Los permisos
        # del art. 37.3 son de la empresa desde que existe, pulse alguien un
        # botón o no, y lo que se siembra es el suelo legal. Lo que su convenio
        # mejore se edita encima, que es justo lo que la copia permite.
        #
        # `seed_leave_types` es idempotente, así que volver a llamarlo ---por
        # el endpoint, para las empresas de antes--- añade lo que falte y no
        # toca lo que hay.
        # Importado aquí dentro, no arriba: `users` está por debajo de
        # `absences` en el orden que declara la configuración, y traerlo al
        # principio del módulo invertiría esa dependencia para siempre. Hoy
        # no da ciclo ---`absences.models` no mira a `users`--- y el día que
        # lo hiciera, reventaría al arrancar y lejos de aquí.
        from apps.absences.catalogue import seed_leave_types

        seed_leave_types(company)

        return {"company": company, "user": admin}


class SignInSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    tax_id = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        company_id = None
        if attrs.get("tax_id"):
            company = Tenant.objects.filter(tax_id=attrs["tax_id"].strip().upper()).first()
            if company is None:
                raise serializers.ValidationError(_("Wrong credentials."))
            company_id = company.id

        user = authenticate(
            self.context.get("request"),
            email=attrs["email"],
            password=attrs["password"],
            tenant_id=company_id,
        )
        if user is None:
            # Deliberately vague: whether the address exists, whether it is
            # ambiguous or whether the company is deactivated are all things the
            # caller does not get to learn.
            raise serializers.ValidationError(_("Wrong credentials."))

        attrs["user"] = user
        return attrs


def issue_tokens(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordSetSerializer(serializers.Serializer):
    """Sets the password from a single-use link."""

    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=12)

    def validate_password(self, value: str) -> str:
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError

        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


class ScheduleAdaptationSerializer(serializers.ModelSerializer):
    """Una solicitud de adaptación de jornada (art. 34.8 ET) y su respuesta."""

    #: Opcional porque **la solicitud la abre quien la ejerce**: sin decir nada
    #: es la suya. Administración sí lo manda, para registrar la de otra persona.
    employee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    employee_name = serializers.SerializerMethodField()
    days_waiting = serializers.SerializerMethodField()
    out_of_time = serializers.SerializerMethodField()

    class Meta:
        model = ScheduleAdaptation
        fields = [
            "id",
            "employee",
            "employee_name",
            "requested_on",
            "asked_for",
            "status",
            "answered_on",
            "answer",
            "answered_by",
            "days_waiting",
            "out_of_time",
        ]
        read_only_fields = ["answered_by"]

    def get_employee_name(self, obj) -> str:
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip() or obj.employee.email

    def get_days_waiting(self, obj) -> int | None:
        return obj.days_waiting(local_today(self.context["request"].user.tenant))

    def get_out_of_time(self, obj) -> bool:
        return obj.out_of_time(local_today(self.context["request"].user.tenant))

    def validate_employee(self, value):
        empresa = self.context["request"].user.tenant
        if value.tenant_id != empresa.id:
            raise serializers.ValidationError(_("That person is not in this company."))
        return value

    def validate(self, attrs):
        """La motivación, que es lo único que el artículo no deja a la empresa.

        «Comunicará la aceptación de la petición, planteará una propuesta
        alternativa... o bien manifestará la negativa a su ejercicio. **En los
        dos últimos casos, se motivará**.» No es un consejo ni una mejora que el
        convenio pueda quitar: una negativa sin motivo escrito no cumple el
        artículo, así que aquí sí se impide en vez de avisar.

        Aceptar no pide motivo, y forzarlo sería inventarse una obligación:
        quien dice que sí no tiene nada que justificar.
        """
        instancia = self.instance
        estado = attrs.get("status", getattr(instancia, "status", AdaptationStatus.PENDING))
        motivo = attrs.get("answer", getattr(instancia, "answer", ""))
        contestada = attrs.get("answered_on", getattr(instancia, "answered_on", None))

        if (
            estado in {AdaptationStatus.ALTERNATIVE, AdaptationStatus.REFUSED}
            and not motivo.strip()
        ):
            raise serializers.ValidationError(
                {
                    "answer": _(
                        "Art. 34.8 asks for a reason when the answer is an alternative or a "
                        "refusal."
                    )
                }
            )

        # Una respuesta sin fecha deja el plazo del artículo sin poder medirse,
        # que es justo lo que este expediente existe para poder mirar.
        resueltas = {
            AdaptationStatus.ACCEPTED,
            AdaptationStatus.ALTERNATIVE,
            AdaptationStatus.REFUSED,
        }
        if estado in resueltas and contestada is None:
            raise serializers.ValidationError(
                {"answered_on": _("An answer needs the date it was given.")}
            )

        return attrs


class RemoteWorkAgreementSerializer(serializers.ModelSerializer):
    """El acuerdo de trabajo a distancia (art. 5 de la Ley 10/2021)."""

    employee_name = serializers.SerializerMethodField()
    signed_late = serializers.BooleanField(read_only=True)

    class Meta:
        model = RemoteWorkAgreement
        fields = [
            "id",
            "employee",
            "employee_name",
            "signed_on",
            "starts_on",
            "ends_on",
            "agreed_share",
            "signed_late",
            "note",
        ]

    def get_employee_name(self, obj) -> str:
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip() or obj.employee.email

    def validate_employee(self, value):
        empresa = self.context["request"].user.tenant
        if value.tenant_id != empresa.id:
            raise serializers.ValidationError(_("That person is not in this company."))
        return value

    def validate_agreed_share(self, value):
        """Entre cero y cien, que es lo que un porcentaje puede ser.

        No se contrasta con lo que se trabaja de verdad, y es a propósito: el
        art. 7.f pide que el acuerdo **diga** un porcentaje, y la cifra que
        obliga es la del papel. Compararla con el registro y quejarse sería
        inventar un incumplimiento que la ley no define.
        """
        if value is not None and not (0 <= value <= 100):
            raise serializers.ValidationError(_("A share goes from 0 to 100."))
        return value

    def validate(self, attrs):
        """Que las fechas tengan sentido y que no haya dos acuerdos a la vez.

        **Firmar tarde no se rechaza.** El art. 5.1 pide que el acuerdo sea
        previo, y un acuerdo firmado después de empezar es un incumplimiento
        **que ya ha ocurrido**: negarse a guardarlo no lo deshace, deja el
        registro peor ---sin rastro de un acuerdo que existe--- y empuja a poner
        una fecha falsa para que el formulario pase. Se guarda y se avisa, que
        es lo que hace la revisión del cuadrante.
        """
        instancia = self.instance
        inicio = attrs.get("starts_on", getattr(instancia, "starts_on", None))
        fin = attrs.get("ends_on", getattr(instancia, "ends_on", None))
        persona = attrs.get("employee", getattr(instancia, "employee", None))

        if fin and inicio and fin < inicio:
            raise serializers.ValidationError(
                {"ends_on": _("The agreement cannot end before it starts.")}
            )

        if persona is None or inicio is None:
            return attrs

        # Dos acuerdos solapados dirían dos cosas a la vez sobre los mismos
        # días, y la revisión coge el más reciente: el otro quedaría guardado
        # sin efecto y nadie sabría cuál manda.
        otros = RemoteWorkAgreement.objects.filter(employee=persona)
        if instancia is not None:
            otros = otros.exclude(pk=instancia.pk)
        for otro in otros:
            if (otro.ends_on is None or otro.ends_on >= inicio) and (
                fin is None or otro.starts_on <= fin
            ):
                raise serializers.ValidationError(
                    {
                        "starts_on": _("It overlaps the agreement that starts on %(day)s.")
                        % {"day": otro.starts_on.isoformat()}
                    }
                )

        return attrs


class ActivityPeriodSerializer(serializers.ModelSerializer):
    """Un periodo de actividad de un fijo discontinuo (art. 16 ET)."""

    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = ActivityPeriod
        fields = [
            "id",
            "employee",
            "employee_name",
            "start_date",
            "end_date",
            "called_on",
            "note",
        ]

    def get_employee_name(self, obj) -> str:
        return f"{obj.employee.first_name} {obj.employee.last_name}".strip() or obj.employee.email

    def validate_employee(self, value):
        """De esta empresa, y fijo discontinuo.

        Lo segundo no es quisquillosidad: un periodo de actividad sobre alguien
        que no lo es no cambia nada ---`is_engaged_on` solo los mira si
        `seasonal`--- así que aceptarlo sería guardar un dato que no hace nada y
        que quien lo escribió cree que sí.
        """
        empresa = self.context["request"].user.tenant
        if value.tenant_id != empresa.id:
            raise serializers.ValidationError(_("That person is not in this company."))
        if not value.seasonal:
            raise serializers.ValidationError(
                _("Periods of activity are for permanent-seasonal contracts (art. 16 ET).")
            )
        return value

    def validate(self, attrs):
        """Que el periodo tenga sentido y no pise a otro.

        El solape se comprueba aquí y no con una restricción de la base porque
        el mensaje importa: «se solapa con el del 3 de junio» se puede arreglar,
        y un error de integridad no.
        """
        instancia = self.instance
        inicio = attrs.get("start_date", getattr(instancia, "start_date", None))
        fin = attrs.get("end_date", getattr(instancia, "end_date", None))
        persona = attrs.get("employee", getattr(instancia, "employee", None))
        llamado = attrs.get("called_on", getattr(instancia, "called_on", None))

        if fin and inicio and fin < inicio:
            raise serializers.ValidationError(
                {"end_date": _("The season cannot end before it starts.")}
            )

        # El llamamiento es previo por definición: se llama para que vengan, no
        # después de que hayan venido (art. 16.3).
        if llamado and inicio and llamado > inicio:
            raise serializers.ValidationError(
                {"called_on": _("The call-up comes before the season starts, not after.")}
            )

        if persona and inicio:
            otros = ActivityPeriod.objects.filter(employee=persona)
            if instancia is not None:
                otros = otros.exclude(pk=instancia.pk)
            for otro in otros:
                if (fin is None or otro.start_date <= fin) and (
                    otro.end_date is None or inicio <= otro.end_date
                ):
                    raise serializers.ValidationError(
                        {
                            "start_date": _("It overlaps the period that starts on %(day)s.")
                            % {"day": otro.start_date.isoformat()}
                        }
                    )
        return attrs
