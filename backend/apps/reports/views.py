"""Report endpoints: the legal output of the product."""

from __future__ import annotations

import io
import zipfile
from datetime import date, timedelta

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.common.descargas import nombre_de_persona, nombre_seguro
from apps.common.exceptions import BusinessRuleError
from apps.common.permissions import IsAuthenticatedInTenant
from apps.common.scope import people_queryset, person_in_scope
from apps.punches.models import Punch
from apps.reports.payroll import PayrollSummary, period_containing
from apps.reports.pdf import render_pdf
from apps.reports.renderers import CSVRenderer, PDFRenderer
from apps.reports.services import build_report, to_csv
from apps.users.models import User


def _parse_date(value: str | None, fallback: date) -> date:
    if not value:
        return fallback
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({"detail": _("Dates must be written as YYYY-MM-DD.")}) from exc


#: How many people one request will produce documents for. Not a technical
#: limit --- it is generated synchronously, and past a few hundred the request
#: takes longer than any reverse proxy will wait. Refusing with a number beats
#: a gateway timeout that looks like the feature is broken.
MAX_PEOPLE_PER_EXPORT = 200


@extend_schema(
    tags=["reports"],
    summary="Working time report",
    description=(
        "Produces the record required by Article 34.9: company, employee, daily entries "
        "and exits, totals and a verification hash. A worker may request their own; a "
        "manager or administrator may request anyone's in the company."
    ),
    parameters=[
        OpenApiParameter("employee", str, description="Employee id. Defaults to the caller."),
        OpenApiParameter("date_from", str, description="YYYY-MM-DD. Defaults to 30 days ago."),
        OpenApiParameter("date_to", str, description="YYYY-MM-DD. Defaults to today."),
        OpenApiParameter("format", str, enum=["pdf", "csv"], description="Defaults to pdf."),
        OpenApiParameter(
            "scope",
            str,
            enum=["company"],
            description=(
                "Everybody in the company for that period, instead of one person. "
                "Includes people who have since left but worked during it."
            ),
        ),
        OpenApiParameter("department", str, description="Everybody in that department."),
    ],
    responses={200: None},
)
class ReportView(APIView):
    permission_classes = [IsAuthenticatedInTenant]
    # Declared so `?format=pdf` and `?format=csv` are understood as content
    # negotiation. Without them DRF answers 404 to a format it does not know.
    renderer_classes = [PDFRenderer, CSVRenderer]

    def get(self, request):
        company = request.user.tenant
        today = timezone.localdate()

        date_from = _parse_date(request.query_params.get("date_from"), today - timedelta(days=30))
        date_to = _parse_date(request.query_params.get("date_to"), today)
        if date_to < date_from:
            raise ValidationError({"detail": _("The end date cannot precede the start date.")})

        # An inspection asks for the workforce, not for one person at a time.
        # Producing two hundred documents one by one was the only way, which in
        # practice means it does not get done.
        if request.query_params.get("scope") == "company" or request.query_params.get("department"):
            return self._many(request, company, date_from, date_to)

        employee = request.user
        requested = request.query_params.get("employee")
        if requested and str(requested) != str(request.user.id):
            # Asking for somebody else's record requires a management role. The
            # lookup is scoped to the company, so an id from elsewhere is a 404.
            if not request.user.can_manage:
                raise ValidationError({"detail": _("You may only request your own record.")})
            # Scoped, and a person out of reach answers the same as one who does
            # not exist: the difference would say who works here.
            employee = person_in_scope(request.user, requested)
            if employee is None:
                raise ValidationError({"detail": _("That person does not exist.")})

        data = build_report(
            employee=employee, company=company, date_from=date_from, date_to=date_to
        )

        # Saneado: el apellido es texto libre y va dentro de unas comillas sin
        # escapar en la cabecera. Ver `apps/common/descargas.py`.
        stem = nombre_seguro(
            f"working-time_{employee.last_name}_{date_from}_{date_to}", respaldo="working-time"
        )

        if request.query_params.get("format", "pdf").lower() == "csv":
            response = HttpResponse(to_csv(data), content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="{stem}.csv"'
        else:
            response = HttpResponse(render_pdf(data), content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{stem}.pdf"'

        # Also as a header, so an automated consumer can check it without
        # opening the document.
        response["X-Report-Hash"] = data.fingerprint

        # Exporting somebody else's record is exactly the kind of thing an
        # inspection --- or the person concerned --- may later ask about.
        if employee.id != request.user.id:
            record(
                action=AuditAction.REPORT_EXPORTED,
                actor=request.user,
                target=employee,
                target_type="user",
                target_label=employee.get_full_name(),
                changes={"from": str(date_from), "to": str(date_to)},
                note=f"hash {data.fingerprint[:16]}",
            )
        return response

    def _many(self, request, company, date_from, date_to):
        """The whole company, or one department, in a single download.

        CSV comes back as one file with everybody in it, which is what somebody
        actually works with. PDF comes back as a zip of one document per person,
        because the PDF *is* the artefact that gets handed over and merging them
        into one would lose the per-person hash that makes each verifiable.

        Every document is recorded in the trail separately. A single entry
        saying "exported the company" would tell whoever asks later that
        somebody's record was read, without saying whose --- which is the
        question the trail exists to answer.
        """
        if not request.user.can_manage:
            raise ValidationError({"detail": _("You may only request your own record.")})

        # Quien está de alta, **más quien ya no está y trabajó en el periodo**.
        #
        # Filtrar solo por `is_active` borraba del informe a quien se fue: el de
        # marzo salía sin la persona que se marchó en abril, con doscientos
        # documentos y uno menos, sin decirlo. Un dato incompleto con esa forma
        # no lo detecta nadie, ni quien lo descarga ni quien lo recibe --- y lo
        # que el art. 34.9 pone a disposición de la Inspección es el registro
        # del periodo, no el de quien siga en plantilla el día que se pide. En
        # una empresa con rotación es todos los meses.
        #
        # Por fichajes en el rango y no «todos los de baja»: quien se fue hace
        # tres años no tiene nada que ver con un informe de marzo, y su
        # documento vacío ensucia justo lo que hay que revisar.
        people = people_queryset(request.user)
        trabajaron = Punch.objects.filter(
            employee__in=people.filter(is_active=False),
            timestamp__date__gte=date_from,
            timestamp__date__lte=date_to,
        ).values("employee_id")
        people = people.filter(Q(is_active=True) | Q(id__in=trabajaron))

        department = request.query_params.get("department")
        if department:
            people = people.filter(department_id=department)
        people = list(people.order_by("last_name", "first_name"))

        if not people:
            raise ValidationError({"detail": _("Nobody worked in that period.")})
        if len(people) > MAX_PEOPLE_PER_EXPORT:
            raise ValidationError(
                {
                    "detail": _(
                        "%(count)s people is over the %(limit)s this can produce in one "
                        "request. Narrow it down by department."
                    )
                    % {"count": len(people), "limit": MAX_PEOPLE_PER_EXPORT}
                }
            )

        reports = [
            build_report(employee=person, company=company, date_from=date_from, date_to=date_to)
            for person in people
        ]
        for person, data in zip(people, reports, strict=True):
            if person.id != request.user.id:
                record(
                    action=AuditAction.REPORT_EXPORTED,
                    actor=request.user,
                    target=person,
                    target_type="user",
                    target_label=person.get_full_name(),
                    changes={"from": str(date_from), "to": str(date_to)},
                    note=f"hash {data.fingerprint[:16]}",
                )

        stem = nombre_seguro(
            f"working-time_{company.tax_id}_{date_from}_{date_to}", respaldo="working-time"
        )

        if request.query_params.get("format", "pdf").lower() == "csv":
            body = "\n".join(to_csv(data) for data in reports)
            response = HttpResponse(body, content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="{stem}.csv"'
            return response

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
            for person, data in zip(people, reports, strict=True):
                # El nombre de la entrada es una **ruta** para quien
                # descomprime, y lleva su identificador para que dos personas
                # que se llamen igual no se pisen. Ver `apps/common/descargas.py`.
                bundle.writestr(nombre_de_persona(person, extension="pdf"), render_pdf(data))

        response = HttpResponse(buffer.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{stem}.zip"'
        return response


class PayrollRunRequestSerializer(serializers.Serializer):
    """Qué periodo se genera. Se publicaba como «sin cuerpo» y sí lo lee.

    Opcional de verdad ---sin él se toma hoy--- pero un integrador que lea «no
    lleva cuerpo» no puede saber que existe la opción, así que genera siempre el
    periodo en curso sin enterarse de que podía pedir otro.
    """

    day = serializers.DateField(
        required=False,
        help_text="Un día cualquiera del periodo que se quiere generar. Por defecto, hoy.",
    )


@extend_schema(tags=["reports"])
class PayrollSummaryView(APIView):
    """The summary that goes out with the payslip (art. 6.1).

    Read for the person concerned, generated by whoever runs the payroll. The
    period comes from the company's own pay cycle rather than from the caller,
    because the article ties it to «el periodo fijado para el abono» and letting
    a request pick its own dates would produce summaries that match no payslip.
    """

    permission_classes = [IsAuthenticatedInTenant]
    # Declared so `?format=pdf` and `?format=csv` are read as content
    # negotiation. Without them DRF answers 404 to a format it does not know ---
    # the same trap the inspection report fell into.
    renderer_classes = [JSONRenderer, PDFRenderer, CSVRenderer]

    @extend_schema(
        parameters=[
            OpenApiParameter("employee", str, description="Defaults to the caller."),
            OpenApiParameter(
                "day", str, description="Any day inside the period. Defaults to today."
            ),
            OpenApiParameter("format", str, enum=["json", "pdf", "csv"]),
        ],
        responses={200: None},
    )
    def get(self, request):
        company = request.user.tenant
        employee = _employee_for(request)

        anchor = _parse_date(request.query_params.get("day"), timezone.localdate())
        period = period_containing(anchor, company.payroll_period)

        data = build_report(
            employee=employee,
            company=company,
            date_from=period.first,
            date_to=period.last,
        )

        wanted = request.query_params.get("format", "json").lower()
        if wanted in {"pdf", "csv"}:
            return _as_file(data, wanted, employee, period)

        return Response(
            {
                "employee": str(employee.id),
                "employee_name": employee.get_full_name(),
                "period": {
                    "from": period.first.isoformat(),
                    "to": period.last.isoformat(),
                    "label": period.label,
                },
                "total_seconds": data.total_seconds,
                "overtime_seconds": data.total_overtime_seconds,
                "break_seconds": data.total_break_seconds,
                "days": len([r for r in data.rows if r.seconds or r.absence]),
                "fingerprint": data.fingerprint,
                "regime": data.regime,
                "contracted_hours": data.contracted_hours,
                "contracted_schedule": data.contracted_schedule,
            }
        )

    @extend_schema(request=PayrollRunRequestSerializer, responses={201: dict})
    def post(self, request):
        """Generates the period's summaries for the whole company, and records it.

        Bulk because that is how payroll happens: nobody produces these one at a
        time on the day the payslips go out. Recording it because «entregará» is
        an obligation the company has to be able to evidence --- and because the
        response says who is missing, which is the question somebody running
        payroll actually has.
        """
        if not request.user.can_manage:
            raise BusinessRuleError(
                code="not_allowed",
                message=_("Only a manager or an administrator generates the summaries."),
            )

        company = request.user.tenant
        anchor = _parse_date(request.data.get("day"), timezone.localdate())
        period = period_containing(anchor, company.payroll_period)

        made, skipped = [], []
        for person in User.objects.filter(tenant=company, is_active=True):
            data = build_report(
                employee=person,
                company=company,
                date_from=period.first,
                date_to=period.last,
            )
            if data.total_seconds == 0:
                # Nothing worked in the period. No summary rather than a page of
                # zeros: a payslip with no hours behind it invites the question
                # of whether the record failed or the person did not work.
                skipped.append(person.get_full_name() or person.email)
                continue

            PayrollSummary.objects.update_or_create(
                employee=person,
                period_start=period.first,
                period_end=period.last,
                defaults={
                    "tenant": company,
                    "total_seconds": data.total_seconds,
                    "overtime_seconds": data.total_overtime_seconds,
                    "fingerprint": data.fingerprint,
                    "generated_by": request.user,
                },
            )
            made.append(person.get_full_name() or person.email)

        return Response(
            {
                "period": {"from": period.first.isoformat(), "to": period.last.isoformat()},
                "generated": len(made),
                "without_hours": skipped,
            },
            status=status.HTTP_201_CREATED,
        )


def _employee_for(request):
    wanted = request.query_params.get("employee")
    if not wanted or wanted == str(request.user.id):
        return request.user
    if not request.user.can_manage:
        raise BusinessRuleError(
            code="not_your_summary",
            message=_("You may only ask for your own summary."),
        )
    person = person_in_scope(request.user, wanted)
    if person is None:
        raise BusinessRuleError(
            code="unknown_employee", message=_("That person is not in this company.")
        )
    return person


def _as_file(data, wanted, employee, period):
    stem = nombre_seguro(
        f"resumen_{employee.last_name}_{period.first}_{period.last}", respaldo="resumen"
    )
    if wanted == "csv":
        response = HttpResponse(to_csv(data), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{stem}.csv"'
    else:
        response = HttpResponse(render_pdf(data), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{stem}.pdf"'
    response["X-Report-Hash"] = data.fingerprint
    return response
