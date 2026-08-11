"""Sample data for local development.

Refuses to run outside DEBUG. The passwords here are written in the open on
purpose -- they are for a throwaway database -- and that is exactly why this must
never execute against anything real.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchSource, PunchType
from apps.tenants.models import Tenant
from apps.users.models import Department, Role, User

PASSWORD = "demo-password-2026"  # noqa: S105 — sample data, DEBUG only


class Command(BaseCommand):
    help = "Creates a demo company with people and a few days of clock events."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete the demo company first and build it again.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo only runs with DEBUG enabled. It writes known passwords.")

        if options["reset"]:
            # Order matters, and the reason is a feature: Punch.employee is
            # PROTECT, so a person with recorded working time cannot be deleted.
            # Clearing sample data means dismantling it deliberately, which is
            # exactly the friction the model is meant to create.
            company = Tenant.objects.filter(tax_id="B00000001").first()
            if company is not None:
                Punch.objects_all_tenants.filter(tenant=company).delete()
                User.objects.filter(tenant=company).delete()
                company.delete()
            User.objects.filter(email="root@opentimetrack.local").delete()

        if Tenant.objects.filter(tax_id="B00000001").exists():
            raise CommandError("The demo company already exists. Use --reset to rebuild it.")

        company = Tenant.objects.create(
            name="Jardines Demo S.L.",
            tax_id="B00000001",
            country="ES",
            time_zone="Europe/Madrid",
        )

        with tenant_context(company.id):
            works = Department.objects.create(tenant=company, name="Obras y mantenimiento")
            gardening = Department.objects.create(tenant=company, name="Jardinería")

            people = [
                ("admin@demo.local", "Ana", "García", Role.ADMIN, works, "EMP-0001"),
                ("manager@demo.local", "Luis", "Ferrer", Role.MANAGER, works, "EMP-0002"),
                ("operario@demo.local", "Marta", "Ruiz", Role.EMPLOYEE, gardening, "EMP-0003"),
            ]

            created = []
            for email, first, last, role, department, staff_number in people:
                person = User.objects.create_user(
                    email=email,
                    password=PASSWORD,
                    tenant=company,
                    first_name=first,
                    last_name=last,
                    role=role,
                    department=department,
                    employee_id=staff_number,
                )
                created.append(person)

            # A few worked days, so reports have something to say.
            #
            # These are built directly rather than through register_punch: that
            # service stamps the current time and infers the type from what else
            # happened *today*, which is exactly right for a real clock-in and
            # exactly wrong for backdated sample data. Going through it and then
            # moving the timestamp produced six entries and no exits, because each
            # event was moved out of today before the next one looked for it.
            worker = created[-1]
            now = timezone.now()
            for days_ago in range(1, 4):
                day = (now - timedelta(days=days_ago)).astimezone(company.tzinfo)
                start = day.replace(hour=8, minute=0, second=0, microsecond=0)
                for punch_type, offset in ((PunchType.IN, 0), (PunchType.OUT, 6)):
                    Punch.objects.create(
                        tenant=company,
                        employee=worker,
                        punch_type=punch_type,
                        timestamp=start + timedelta(hours=offset),
                        source=PunchSource.MOBILE,
                        device_id="seed",
                    )

        # Platform superuser, for the Django admin. No company: it does not
        # operate on service data.
        root, is_new = User.objects.get_or_create(
            email="root@opentimetrack.local",
            defaults={
                "first_name": "Root",
                "last_name": "Local",
                "role": Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if is_new:
            root.set_password(PASSWORD)
            root.save()

        self.stdout.write(self.style.SUCCESS("Demo data ready.\n"))
        self.stdout.write(f"  Company        {company.name} ({company.tax_id})\n")
        self.stdout.write(f"  Time zone      {company.time_zone}\n\n")
        self.stdout.write("  Web panel — http://localhost:3000\n")
        for email, _first, _last, role, *_rest in people:
            self.stdout.write(f"    {email:22} {PASSWORD:20} {role}\n")
        self.stdout.write("\n  Django admin — http://localhost:8000/admin/\n")
        self.stdout.write(f"    {'root@opentimetrack.local':22} {PASSWORD:20} superuser\n")
