"""Entregar a alguien su propio registro cuando ya no trabaja allí.

**La pregunta que resuelve esto no es de producto, es de derechos.** El art. 34.9
ET obliga a conservar el registro cuatro años y a tenerlo a disposición de la
persona trabajadora; el art. 15 del RGPD le da derecho de acceso a sus datos, y
ese derecho **no se extingue el día que deja la empresa**: mientras los datos se
conserven, puede pedirlos.

Lo que no se sigue de ahí es que deba conservar la cuenta. El derecho de acceso se
ejerce **por solicitud y se satisface con una entrega**; no obliga a mantener a
nadie dentro del producto. Y mantenerla dentro tiene coste real para todos: vería
el cuadrante, a sus antiguos compañeros y lo que la empresa haya cambiado desde que
se fue.

Así que esto es una entrega, no un acceso:

- La administración genera un enlace para una persona concreta, esté de alta o de
  baja, y le llega por correo.
- El enlace no abre sesión ni sirve para nada más que descargar **su** registro.
- **Caduca** con el mismo plazo que el enlace de contraseña, y hasta entonces vale
  las veces que haga falta. No es de un solo uso a propósito: la misma persona
  suele querer el PDF y el CSV, y un enlace que muere en la primera descarga
  obliga a pedir otro para la segunda. Lo que lo mata antes de tiempo es que la
  cuenta se reactive o que cambie su contraseña ---los dos entran en el valor
  firmado---, y las dos cosas significan que ya hay otra puerta.
- Queda asiento de quién lo generó y de cada descarga.

**Se entrega exactamente lo que se conserva.** El periodo lo decide
`first_day_kept`, el mismo que usa la purga para decidir qué borrar: si un día
dejan de estar, dejan de entregarse, y no hay dos definiciones del plazo que
puedan separarse.
"""

from __future__ import annotations

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.http import HttpResponse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.common.clock import local_today
from apps.common.descargas import nombre_seguro
from apps.common.models import tenant_context
from apps.punches.management.commands.purge_expired_records import first_day_kept
from apps.reports.pdf import render_pdf
from apps.reports.renderers import CSVRenderer, PDFRenderer
from apps.reports.services import build_report, to_csv

#: Un literal propio dentro del hash. Sin esto, un enlace de entrega valdría para
#: poner una contraseña y al revés: los dos se derivan de los mismos campos del
#: usuario, así que lo único que los separa es esto.
AMBITO = "entrega-del-registro"


class RecordDeliveryTokenGenerator(PasswordResetTokenGenerator):
    """Firmado y con caducidad, sin tabla propia, como el de las cuentas.

    Hereda de `PasswordResetTokenGenerator` por el plazo y la firma, **no** por el
    consumo al usarse: aquel se invalida solo porque poner una contraseña cambia
    el hash que va en el valor firmado, y descargar un informe no cambia nada. Así
    que este vale hasta que caduque, que es lo que se quiere ---el PDF y el CSV son
    dos descargas de la misma solicitud---.

    Lo que sí lo mata antes: **reactivar la cuenta** (`is_active` entra en el
    valor) y **cambiar la contraseña**. Las dos significan que esa persona ya
    tiene otra forma de entrar, así que el enlace de emergencia sobra.
    """

    def _make_hash_value(self, user, timestamp: int) -> str:
        last = user.last_login
        login = "" if last is None else last.replace(microsecond=0, tzinfo=None)
        return f"{AMBITO}{user.pk}{user.password}{login}{timestamp}{user.is_active}"


token_generator = RecordDeliveryTokenGenerator()


def build_delivery_link(user, *, base_url: str) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    return f"{base_url.rstrip('/')}/api/record-delivery/{uid}/{token_generator.make_token(user)}/"


def resolve_delivery_token(uid: str, token: str):
    """La persona detrás del enlace, o `None`.

    **Sin filtrar por `is_active`**, que es toda la diferencia con
    `resolve_token`: allí una cuenta de baja no puede poner contraseña, y aquí una
    cuenta de baja es justamente el caso que hay que atender.
    """
    from django.contrib.auth import get_user_model

    try:
        user = get_user_model().objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except Exception:
        # Un enlace mal formado es un enlace inválido y no hay nada que
        # distinguir para quien pregunta.
        return None

    if not token_generator.check_token(user, token):
        return None
    return user


def send_delivery_email(person, *, base_url: str) -> str:
    """Manda el enlace, en el idioma de quien lo recibe. Devuelve el enlace.

    El idioma va explícito y no heredado del contexto: lo genera quien
    administra, así que heredarlo mandaría el correo en **su** idioma, que es el
    defecto que la vuelta 105 arregló en los otros tres correos.
    """
    from django.conf import settings
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.utils import translation

    link = build_delivery_link(person, base_url=base_url)
    company = person.tenant.name if person.tenant else _("the platform")
    idioma = person.locale or (person.tenant.language if person.tenant else "")

    with translation.override(idioma or None):
        cuerpo = render_to_string(
            "emails/record_delivery.txt",
            {
                # El nombre suelto: `{% blocktranslate %}` no resuelve accesos a
                # atributos y el hueco quedaría vacío. Ver `passwords.py`.
                "first_name": person.first_name,
                "company": company,
                "link": link,
                "hours": settings.PASSWORD_RESET_TIMEOUT // 3600,
            },
        )
        send_mail(
            subject=str(_("Your working time record at %(company)s") % {"company": company}),
            message=cuerpo,
            from_email=None,
            recipient_list=[person.email],
            fail_silently=False,
        )
    return link


class RecordDeliveryView(APIView):
    """El enlace, abierto: devuelve el registro y nada más.

    `AllowAny` porque quien llega aquí no tiene cuenta utilizable ---esa es la
    situación--- y lo que autoriza es el propio enlace. Tres cosas lo acotan:

    - Solo se puede pedir **el registro de quien firma el enlace**. No hay ningún
      parámetro que diga de quién: sale del identificador firmado.
    - El periodo es el que se conserva, no uno a elección. Pedir «desde 2015» no
      devuelve más de lo que hay.
    - Deja asiento. Una entrega que no consta no sirve para demostrar que se
      atendió la solicitud, que es la mitad de para lo que sirve.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    renderer_classes = [PDFRenderer, CSVRenderer]

    @extend_schema(
        summary="Descargar el propio registro con un enlace de entrega",
        description=(
            "Devuelve el registro de la persona que firma el enlace, en PDF o CSV según "
            "la cabecera Accept, y solo el periodo que la empresa conserva. No abre sesión. "
            "404 si el enlace caducó, se invalidó o no existe: los tres son lo mismo desde fuera."
        ),
        auth=[],
        responses={200: OpenApiTypes.BINARY, 404: None},
    )
    def get(self, request, uid: str, token: str):
        person = resolve_delivery_token(uid, token)
        if person is None or person.tenant_id is None:
            # Caducado, invalidado o inventado: los tres son lo mismo desde fuera.
            # Distinguirlos diría si esa dirección existe en el producto.
            raise NotFound(_("This link is no longer valid. Ask the company for a new one."))

        company = person.tenant
        # Fuera de toda petición con empresa en contexto: la activa el enlace, y
        # el `tenant` sale del identificador firmado, no de nada que llegue.
        with tenant_context(company.id):
            data = build_report(
                employee=person,
                company=company,
                date_from=first_day_kept(company),
                date_to=local_today(company),
            )
            stem = nombre_seguro(
                f"mi-registro_{person.last_name}_{data.date_from}_{data.date_to}",
                respaldo="mi-registro",
            )
            if request.query_params.get("format", "pdf").lower() == "csv":
                response = HttpResponse(to_csv(data), content_type="text/csv; charset=utf-8")
                response["Content-Disposition"] = f'attachment; filename="{stem}.csv"'
            else:
                response = HttpResponse(render_pdf(data), content_type="application/pdf")
                response["Content-Disposition"] = f'attachment; filename="{stem}.pdf"'
            response["X-Report-Hash"] = data.fingerprint

            # `actor` va vacío a propósito: no hay sesión, y quien descarga es la
            # propia persona. Lo que importa es que consta que se entregó.
            record(
                action=AuditAction.RECORD_DELIVERED,
                company=company,
                target=person,
                target_type="user",
                target_label=person.get_full_name(),
                actor_label=_("the person concerned, through their delivery link"),
                changes={"from": str(data.date_from), "to": str(data.date_to), "picked_up": True},
                note=f"hash {data.fingerprint[:16]}",
            )
        return response
