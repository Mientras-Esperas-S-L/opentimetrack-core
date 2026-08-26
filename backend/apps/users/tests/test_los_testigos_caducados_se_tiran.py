"""La lista negra de testigos no puede crecer sin techo.

La rotación está activada, así que **cada renovación deja dos filas**: el testigo
nuevo en `OutstandingToken` y el viejo en `BlacklistedToken`. Con un acceso de
quince minutos eso son unas treinta por persona y jornada.

Medido en la base de desarrollo antes de arreglarlo: **3.322 registrados, 1.769 de
ellos ya caducados** (el 53 %), el más antiguo de dos semanas atrás. En una empresa
de doscientas personas son del orden de dos millones de filas al año.

Y cada fila dice **de quién** era la sesión y cuándo empezó, así que no es solo un
problema de tamaño: guardarlas sin plazo es lo mismo que ya razona
`purge_security_metadata` para los metadatos de red --- conservar un dato porque
algún día pueda ser útil no es una base (art. 5.1.e del RGPD).

`flushexpiredtokens` viene con simplejwt; lo que faltaba era llamarlo.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.models import tenant_context
from apps.tenants.models import Tenant
from apps.users.models import User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def quien(db):
    empresa = Tenant.objects.create(
        name="Testigos", tax_id="B91600001", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(empresa.id):
        yield User.objects.create_user(
            email="quien@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Quien",
            last_name="Renueva",
        )


@pytest.mark.django_db
def test_la_purga_tira_los_caducados_y_deja_los_vigentes(quien):
    from config.celery import flush_expired_tokens

    vigente = RefreshToken.for_user(quien)
    caducado = RefreshToken.for_user(quien)

    # Uno de los dos se envejece: es como llegaría dentro de una semana.
    OutstandingToken.objects.filter(jti=caducado["jti"]).update(
        expires_at=timezone.now() - timedelta(days=1)
    )

    flush_expired_tokens()

    assert not OutstandingToken.objects.filter(jti=caducado["jti"]).exists(), (
        "el testigo caducado seguía guardado"
    )
    assert OutstandingToken.objects.filter(jti=vigente["jti"]).exists(), (
        "la purga se llevó una sesión que seguía viva"
    )


@pytest.mark.django_db
def test_y_se_lleva_su_apunte_en_la_lista_negra(quien):
    from config.celery import flush_expired_tokens

    caducado = RefreshToken.for_user(quien)
    caducado.blacklist()
    assert BlacklistedToken.objects.filter(token__jti=caducado["jti"]).exists()

    OutstandingToken.objects.filter(jti=caducado["jti"]).update(
        expires_at=timezone.now() - timedelta(days=1)
    )
    flush_expired_tokens()

    assert not BlacklistedToken.objects.filter(token__jti=caducado["jti"]).exists(), (
        "la fila de la lista negra se quedaba sin su testigo"
    )


@pytest.mark.django_db
def test_purgar_no_echa_a_quien_esta_dentro(quien):
    """Lo que no puede romperse: un testigo vigente sigue sirviendo después."""
    from rest_framework.test import APIClient

    from config.celery import flush_expired_tokens

    vigente = RefreshToken.for_user(quien)
    flush_expired_tokens()

    cliente = APIClient()
    respuesta = cliente.post("/api/auth/refresh/", {"refresh": str(vigente)}, format="json")
    assert respuesta.status_code == 200, respuesta.content
