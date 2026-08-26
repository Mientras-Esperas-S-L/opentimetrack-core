"""El registro de la empresa incluye a quien ya no está.

Art. 34.9: la empresa conserva los registros cuatro años y los mantiene a
disposición de las personas trabajadoras, de sus representantes y de la
Inspección. Lo que se pone a disposición es **el registro del periodo**, no el
de quien siga en plantilla el día que se pide.

La descarga de toda la empresa filtraba por `is_active=True`, así que quien
trabajó en marzo y se fue en abril desaparecía de un informe de marzo. Y no lo
decía: salía un zip con doscientos documentos y una persona menos, que es
exactamente la forma de un dato incompleto que nadie va a detectar --- ni quien
lo descarga, ni quien lo recibe.

Es el caso normal, además: una empresa con rotación tiene bajas todos los meses,
y una inspección se pide justo del periodo en el que alguien se fue.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.common.models import tenant_context
from apps.punches.services import register_punch
from apps.tenants.models import Tenant
from apps.users.models import Role, User

PASSWORD = "a-sufficiently-long-password"


@pytest.fixture
def empresa(db):
    return Tenant.objects.create(
        name="Jardines del Sur S.L.", tax_id="B98765432", time_zone="Europe/Madrid"
    )


@pytest.fixture
def gente(empresa):
    with tenant_context(empresa.id):
        jefa = User.objects.create_user(
            email="jefa@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Luisa",
            last_name="Marín",
            role=Role.ADMIN,
        )
        sigue = User.objects.create_user(
            email="sigue@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Ana",
            last_name="García",
        )
        se_fue = User.objects.create_user(
            email="sefue@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Bruno",
            last_name="Peña",
        )
        for quien in (sigue, se_fue):
            with freeze_time("2026-03-10 06:00:00"):
                register_punch(employee=quien, company=empresa)
            with freeze_time("2026-03-10 14:00:00"):
                register_punch(employee=quien, company=empresa)

        # Se marcha después de haber trabajado el periodo que se va a pedir.
        se_fue.is_active = False
        se_fue.save(update_fields=["is_active"])

        yield {"jefa": jefa, "sigue": sigue, "se_fue": se_fue}


def descargar(quien, **extra):
    client = APIClient()
    client.force_authenticate(user=quien)
    return client.get(
        "/api/reports/working-time/",
        {"scope": "company", "date_from": "2026-03-01", "date_to": "2026-03-31", **extra},
    )


@pytest.mark.django_db
def test_el_zip_de_la_empresa_trae_a_quien_se_fue(empresa, gente):
    with tenant_context(empresa.id):
        respuesta = descargar(gente["jefa"])

    assert respuesta.status_code == 200
    dentro = zipfile.ZipFile(io.BytesIO(respuesta.content)).namelist()

    # Por quién está, no por el nombre exacto: la entrada lleva además el
    # identificador de cada persona ---dos que se llamen igual se pisaban--- y
    # los acentos se transliteran, porque el nombre es una ruta para quien
    # descomprime. Ver `apps/common/descargas.py`.
    assert any(n.startswith("Garcia_Ana_") for n in dentro), dentro
    assert any(n.startswith("Pena_Bruno_") for n in dentro), (
        f"falta quien se fue; solo hay {dentro}"
    )


@pytest.mark.django_db
def test_y_el_csv_tambien(empresa, gente):
    with tenant_context(empresa.id):
        respuesta = descargar(gente["jefa"], format="csv")

    assert respuesta.status_code == 200
    cuerpo = respuesta.content.decode("utf-8")
    assert "Peña" in cuerpo, "quien se fue no salía en el CSV"


@pytest.mark.django_db
def test_quien_se_fue_sin_fichajes_en_el_periodo_no_se_cuela(empresa, gente):
    """El contraste, y lo que evita que el arreglo sea «meter a todo el mundo».

    Alguien que se fue hace tres años no tiene nada que ver con un informe de
    marzo, y añadir su documento vacío ensucia justo lo que hay que revisar.
    """
    with tenant_context(empresa.id):
        User.objects.create_user(
            email="antiguo@example.com",
            password=PASSWORD,
            tenant=empresa,
            first_name="Vieja",
            last_name="Historia",
            is_active=False,
        )

        respuesta = descargar(gente["jefa"])

    dentro = zipfile.ZipFile(io.BytesIO(respuesta.content)).namelist()
    assert not any(n.startswith("Historia_Vieja_") for n in dentro), dentro


@pytest.mark.django_db
def test_un_periodo_anterior_a_su_entrada_no_lo_trae(empresa, gente):
    """Y el mismo contraste por el otro lado: fuera del rango, fuera del zip."""
    client = APIClient()
    client.force_authenticate(user=gente["jefa"])

    with tenant_context(empresa.id):
        respuesta = client.get(
            "/api/reports/working-time/",
            {"scope": "company", "date_from": "2026-01-01", "date_to": "2026-01-31"},
        )

    assert respuesta.status_code == 200
    dentro = zipfile.ZipFile(io.BytesIO(respuesta.content)).namelist()
    assert not any(n.startswith("Pena_Bruno_") for n in dentro), dentro


@pytest.mark.django_db
def test_el_conteo_de_personas_no_cambia_para_quien_sigue(empresa, gente):
    """Nadie se duplica al ampliar el filtro: sale una vez, no dos."""
    with tenant_context(empresa.id):
        respuesta = descargar(gente["jefa"])

    dentro = zipfile.ZipFile(io.BytesIO(respuesta.content)).namelist()
    assert len(dentro) == len(set(dentro))
    # La jefa está de alta y va también: administrar es trabajar.
    quienes = sorted(n.rsplit("_", 1)[0] for n in dentro)
    assert quienes == ["Garcia_Ana", "Marin_Luisa", "Pena_Bruno"], dentro


@pytest.mark.django_db
def test_por_departamento_se_comporta_igual(empresa, gente):
    """Porque el mismo filtro sirve a las dos descargas, y una inspección puede
    pedir solo una brigada."""
    from apps.users.models import Department

    with tenant_context(empresa.id):
        brigada = Department.objects.create(tenant=empresa, name="Brigada")
        for quien in (gente["sigue"], gente["se_fue"]):
            quien.department = brigada
            quien.save(update_fields=["department"])

        respuesta = descargar(gente["jefa"], department=str(brigada.id))

    assert respuesta.status_code == 200
    dentro = zipfile.ZipFile(io.BytesIO(respuesta.content)).namelist()
    assert any(n.startswith("Pena_Bruno_") for n in dentro), dentro
