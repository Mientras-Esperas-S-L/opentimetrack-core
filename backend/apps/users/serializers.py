"""Serializers for identity and organisation."""

from __future__ import annotations

from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps import legal
from apps.tenants.models import Tenant, validate_time_zone
from apps.users.models import Department, Role

User = get_user_model()


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name", "tax_id", "country", "time_zone", "language"]
        read_only_fields = ["id"]


class DepartmentSerializer(serializers.ModelSerializer):
    people_count = serializers.SerializerMethodField()
    manager_names = serializers.SerializerMethodField()

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
        ]
        read_only_fields = ["id", "people_count", "manager_names"]

    def get_people_count(self, obj) -> int:
        return obj.users.filter(is_active=True).count()

    def get_manager_names(self, obj) -> list[str]:
        return [person.get_full_name() for person in obj.managers.all()]

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


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)

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
            "is_active",
            "is_federated",
            "date_joined",
        ]
        read_only_fields = ["id", "full_name", "department_name", "is_federated", "date_joined"]


class UserWriteSerializer(serializers.ModelSerializer):
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

        if regime in {WorkingTimeRegime.PART_TIME, WorkingTimeRegime.TRAINING} and hours is None:
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

        limits = getattr(company, "limits", None)
        if limits is not None:
            current = User.objects.filter(tenant=company, is_active=True).count()
            if not limits.allows_another_employee(current):
                raise serializers.ValidationError(
                    {"non_field_errors": [_("The employee limit for this company is reached.")]}
                )

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
