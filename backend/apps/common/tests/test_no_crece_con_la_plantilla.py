"""Ningún endpoint puede hacer más consultas por tener más gente.

Un N+1 no se ve nunca en desarrollo. Con tres personas de prueba son doce
consultas y con doscientas son dos mil, y entre las dos cosas no hay ningún
aviso: la pantalla funciona, los datos son correctos, y el día que una empresa
grande abre el cuadrante se cae.

Por eso la comprobación es **comparativa** y no un número máximo. Un tope
absoluto envejece mal ---se sube cada vez que molesta--- mientras que «no puede
crecer» es una propiedad que o se cumple o no.

## Lo que encontró

`/api/shifts/review/`, la pantalla que un responsable abre para ver qué incumple
su cuadrante: **40 consultas con tres personas y 130 con doce**. Dos N+1 dentro
del mismo endpoint, y cada uno se veía solo con la ventana adecuada:

- Los festivos se preguntaban por persona, cuando la respuesta depende solo del
  centro de trabajo. Ese salía con cualquier ventana.
- Las reducciones de jornada (un ERTE del art. 47) se preguntaban por persona
  **y por semana**. Ese solo salía con una ventana que contuviera semanas
  completas, porque las semanas a medias se saltan: con la sonda de cinco días
  no aparecía, y estuve a punto de dar por inútil el arreglo.

Después: once consultas, con tres personas y con doce.

## Por qué doce y no doscientas

Doce bastan para ver la pendiente y la prueba tarda segundos. Con doscientas se
vería lo mismo y la suite entera dejaría de correrse.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.absences.models import Absence, AbsenceStatus
from apps.common.models import tenant_context
from apps.punches.models import Punch, PunchInterval, PunchType
from apps.shifts.models import Shift
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"
HOY = date.today()
#: Cuarenta días a propósito: tiene que caber alguna semana completa o la
#: comprobación de horas semanales se salta entera y con ella su N+1.
DESDE = HOY - timedelta(days=40)

POCAS, MUCHAS = 3, 12


def _empresa_con(cuantas: int, sufijo: str):
    empresa = Tenant.objects.create(
        name=f"Escala {sufijo}", tax_id=f"B{sufijo}", time_zone="Europe/Madrid"
    )
    with tenant_context(empresa.id):
        jefa = User.objects.create_user(
            email=f"jefa{sufijo}@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Jefa",
            role=Role.ADMIN,
        )
        ahora = timezone.now()
        for i in range(cuantas):
            quien = User.objects.create_user(
                email=f"p{sufijo}-{i}@example.com",
                password=PASSWORD,
                tenant=empresa,
                first_name=f"P{i}",
            )
            for d in range(0, 40, 3):
                Shift.objects.create(
                    tenant=empresa,
                    employee=quien,
                    day=HOY - timedelta(days=d),
                    segments=[{"start": "08:00", "end": "16:00"}],
                )
                for horas, tipo in ((9, PunchType.IN), (1, PunchType.OUT)):
                    Punch.objects.create(
                        tenant=empresa,
                        employee=quien,
                        punch_type=tipo,
                        interval=PunchInterval.WORK,
                        timestamp=ahora - timedelta(days=d, hours=horas),
                    )
            Absence.objects.create(
                tenant=empresa,
                employee=quien,
                start_date=HOY + timedelta(days=30 + i),
                end_date=HOY + timedelta(days=31 + i),
                status=AbsenceStatus.PENDING,
            )
    return empresa, jefa


def _conector_de(empresa):
    """Una aplicación autorizada de esa empresa, con su credencial.

    La puerta de integración no se mide con la sesión de una persona: quien
    llama es una aplicación, y su permiso es otro. Sin esto, las dos rutas de
    `/api/app/…` contestaban 403 y la sonda las daba por planas --- que es
    justo el falso negativo contra el que este fichero se protege más abajo.
    """
    from apps.tenants.models import Application, ApplicationCredential, ApplicationScope

    with tenant_context(empresa.id):
        aplicacion = Application.objects.create(
            tenant=empresa,
            name="Sonda",
            scopes=[str(ApplicationScope.READ_ATTENDANCE), str(ApplicationScope.READ_PEOPLE)],
        )
        _credencial, secreto = ApplicationCredential.issue(aplicacion)
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {secreto}")
    return cliente


#: Lo que llama un conector, que es lo que más se repite: una aplicación
#: integrada pregunta la asistencia del día cada pocos minutos, y lo hace con la
#: plantilla entera. `_attendance_of` está escrita para no consultar por cabeza,
#: y hasta ahora nadie vigilaba que siguiera así.
RUTAS_DE_INTEGRACION = ["/api/app/attendance/", "/api/app/people/"]


def _rutas() -> list[str]:
    ventana = f"?from={DESDE}&to={HOY}"
    return [
        "/api/employees/",
        "/api/overview/",
        f"/api/shifts/roster/{ventana}",
        f"/api/shifts/review/{ventana}",
        f"/api/shifts/coverage/{ventana}",
        "/api/shifts/today/",
        "/api/punches/",
        "/api/absences/",
        "/api/absences/pending/",
        f"/api/absences/calendar/{ventana}",
        "/api/overtime/",
        "/api/audit/",
        "/api/leave-types/",
        "/api/reports/payroll-summary/",
    ]


def _consultas_de(jefa, empresa) -> dict[str, tuple[int, int]]:
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(jefa).access_token}")
    conector = _conector_de(empresa)
    medidas = {}
    with tenant_context(empresa.id):
        for ruta in _rutas():
            with CaptureQueriesContext(connection) as capturadas:
                respuesta = cliente.get(ruta)
            medidas[ruta.split("?")[0]] = (len(capturadas), respuesta.status_code)
        for ruta in RUTAS_DE_INTEGRACION:
            with CaptureQueriesContext(connection) as capturadas:
                respuesta = conector.get(ruta)
            medidas[ruta] = (len(capturadas), respuesta.status_code)
    return medidas


@pytest.mark.django_db
def test_ningun_endpoint_consulta_mas_por_haber_mas_gente(settings):
    settings.DEBUG = True  # sin esto Django no guarda las consultas

    pocas, jefa_pocas = _empresa_con(POCAS, "40000001")
    muchas, jefa_muchas = _empresa_con(MUCHAS, "40000002")

    con_pocas = _consultas_de(jefa_pocas, pocas)
    con_muchas = _consultas_de(jefa_muchas, muchas)

    # Contraste: si las peticiones no llegaran a ninguna parte ---un 403, una
    # ruta mal escrita--- todo saldría plano y la prueba pasaría sin mirar nada.
    for ruta, (_n, codigo) in con_pocas.items():
        assert codigo == 200, f"{ruta} contestó {codigo}: no se está midiendo nada"
    assert min(n for n, _c in con_pocas.values()) >= 3, "hay rutas que no consultan la base"

    # Un poco de margen: alguna consulta más por haber más filas que serializar
    # es legítima. Lo que no lo es es crecer con el número de personas.
    tolerancia = 2
    crecen = []
    for ruta, (pocas_n, _c) in con_pocas.items():
        muchas_n, _c2 = con_muchas[ruta]
        if muchas_n - pocas_n > tolerancia:
            crecen.append(
                f"{ruta}: {pocas_n} con {POCAS} personas, {muchas_n} con {MUCHAS} "
                f"(+{muchas_n - pocas_n})"
            )

    assert not crecen, (
        "consultan más por tener más gente, así que en una empresa grande se caen:\n"
        + "\n".join(crecen)
    )
