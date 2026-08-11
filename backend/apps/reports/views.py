"""Report endpoints: the legal output of the product."""

from __future__ import annotations

from datetime import date, timedelta

from django.http import HttpResponse
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from apps.common.permissions import IsAuthenticatedInTenant
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
        today = date.today()

        date_from = _parse_date(request.query_params.get("date_from"), today - timedelta(days=30))
        date_to = _parse_date(request.query_params.get("date_to"), today)
        if date_to < date_from:
            raise ValidationError({"detail": _("The end date cannot precede the start date.")})

        employee = request.user
        requested = request.query_params.get("employee")
        if requested and str(requested) != str(request.user.id):
            # Asking for somebody else's record requires a management role. The
            # lookup is scoped to the company, so an id from elsewhere is a 404.
            if not request.user.can_manage:
                raise ValidationError({"detail": _("You may only request your own record.")})
            employee = User.objects.filter(tenant=company, pk=requested).first()
            if employee is None:
                raise ValidationError({"detail": _("That person does not exist.")})

        data = build_report(
            employee=employee, company=company, date_from=date_from, date_to=date_to
        )

        stem = f"working-time_{employee.last_name}_{date_from}_{date_to}".replace(" ", "-")

        if request.query_params.get("format", "pdf").lower() == "csv":
            response = HttpResponse(to_csv(data), content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="{stem}.csv"'
        else:
            response = HttpResponse(render_pdf(data), content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{stem}.pdf"'

        # Also as a header, so an automated consumer can check it without
        # opening the document.
        response["X-Report-Hash"] = data.fingerprint
        return response
