"""Serializers for identity and organisation."""

from __future__ import annotations

from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

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

    class Meta:
        model = Department
        fields = ["id", "name", "description", "is_active", "people_count"]
        read_only_fields = ["id", "people_count"]

    def get_people_count(self, obj) -> int:
        return obj.users.filter(is_active=True).count()


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
            "part_time",
            "part_time_percentage",
            "contracted_schedule",
            "default_work_mode",
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
            "part_time",
            "part_time_percentage",
            "contracted_schedule",
            "default_work_mode",
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
        # Art. 6.1 ET forbids work below sixteen. Anything under it is a typo or
        # something nobody should be recording as an employee.
        if age < 16:
            raise serializers.ValidationError(
                _("That gives an age of %(age)s. Art. 6.1 ET does not allow work below sixteen.")
                % {"age": age}
            )
        if age > 100:
            raise serializers.ValidationError(_("That gives an age of over a hundred years."))
        return value

    def validate(self, attrs):
        """The percentage and the part-time flag have to agree.

        Art. 3.b asks for both, and they only mean anything together: a
        percentage on a full-time contract is a leftover somebody forgot to
        clear, and part time with no percentage is the field the article
        actually requires left empty.
        """
        part_time = attrs.get("part_time", getattr(self.instance, "part_time", False))
        percentage = attrs.get(
            "part_time_percentage", getattr(self.instance, "part_time_percentage", None)
        )

        if part_time and percentage is None:
            raise serializers.ValidationError(
                {"part_time_percentage": _("Art. 3.b asks for it whenever the work is part time.")}
            )
        if not part_time and percentage is not None:
            raise serializers.ValidationError(
                {
                    "part_time_percentage": _(
                        "Only applies to part-time work. Clear it or mark the contract part time."
                    )
                }
            )
        if percentage is not None and not (0 < percentage < 100):
            raise serializers.ValidationError(
                {
                    "part_time_percentage": _(
                        "It is a fraction of a full day: above zero and below a hundred."
                    )
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
