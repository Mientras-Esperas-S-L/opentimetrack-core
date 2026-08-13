"""La importación del calendario de festivos.

El comando escribe días en **todas** las empresas del país de un tirón y no
tenía ni una prueba. Lo que escribe no es un dato cualquiera: un festivo cambia
la cuenta de las vacaciones ---un día festivo dentro de un permiso no se gasta---
y decide si un cuadrante señala trabajo en día de fiesta.

Aquí se cubren las tres cosas que un comando así tiene que garantizar: que
escribe lo que dice el fichero, que **no** pisa lo que puso una persona, y que
volver a ejecutarlo deja lo mismo que la primera vez.
"""

from __future__ import annotations

import datetime
import pathlib

import pytest
import yaml
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.common.models import tenant_context
from apps.tenants.holidays import HolidayScope, PublicHoliday
from apps.tenants.models import Tenant
from apps.users.models import Workplace

CALENDARIO = {
    "format": 1,
    "country": "ES",
    "year": 2030,
    "verified": True,
    "national": [
        {"day": datetime.date(2030, 1, 1), "name": "Año Nuevo", "irrenunciable": True},
        {"day": datetime.date(2030, 5, 1), "name": "Fiesta del Trabajo", "irrenunciable": True},
    ],
    "regions": {
        "AN": [{"day": datetime.date(2030, 2, 28), "name": "Día de Andalucía"}],
        "CT": [{"day": datetime.date(2030, 9, 11), "name": "Diada"}],
    },
}


@pytest.fixture
def calendario(tmp_path, settings):
    """Un calendario de mentira en un directorio propio.

    Se inventa un año lejano a propósito: probar contra el fichero que se
    publica sería atar la prueba a lo que diga el BOE, y entonces cambiaría de
    color cada mes de octubre sin que nadie hubiera tocado el código.
    """
    pais = tmp_path / "es"
    pais.mkdir()
    (pais / "2030.yaml").write_text(yaml.safe_dump(CALENDARIO), encoding="utf-8")
    settings.HOLIDAYS_DIR = str(tmp_path)

    # El comando lee `settings.HOLIDAYS_DIR` al importarse, no al ejecutarse.
    import apps.tenants.management.commands.import_holidays as modulo

    modulo.ROOT = pathlib.Path(tmp_path)
    return tmp_path


@pytest.fixture
def empresa(db):
    compania = Tenant.objects.create(
        name="ACME Ltd", tax_id="B11111111", time_zone="Europe/Madrid", country="ES"
    )
    with tenant_context(compania.id):
        Workplace.objects.create(tenant=compania, name="Sevilla", region="AN")
        Workplace.objects.create(tenant=compania, name="Lleida", region="CT")
    return compania


def dias_de(empresa, scope=None):
    with tenant_context(empresa.id):
        filas = PublicHoliday.objects.all()
        if scope:
            filas = filas.filter(scope=scope)
        return sorted(filas.values_list("day", flat=True))


@pytest.mark.django_db
def test_escribe_los_nacionales_y_los_de_cada_comunidad(calendario, empresa):
    call_command("import_holidays", year=2030, company="B11111111")

    assert dias_de(empresa, HolidayScope.NATIONAL) == [
        datetime.date(2030, 1, 1),
        datetime.date(2030, 5, 1),
    ]
    # Cada centro recibe los suyos, no los del otro.
    with tenant_context(empresa.id):
        por_centro = {
            fila.workplace.name: fila.day
            for fila in PublicHoliday.objects.filter(scope=HolidayScope.REGIONAL).select_related(
                "workplace"
            )
        }
    assert por_centro == {
        "Sevilla": datetime.date(2030, 2, 28),
        "Lleida": datetime.date(2030, 9, 11),
    }


@pytest.mark.django_db
def test_volver_a_ejecutarlo_deja_lo_mismo(calendario, empresa):
    """Idempotencia. Es lo que se hace cuando el BOE corrige una fecha."""
    call_command("import_holidays", year=2030, company="B11111111")
    primera = dias_de(empresa)

    call_command("import_holidays", year=2030, company="B11111111")

    assert dias_de(empresa) == primera


@pytest.mark.django_db
def test_los_dias_locales_no_se_tocan(calendario, empresa):
    """Los dos del ayuntamiento son los únicos que costó teclear a alguien.

    Nadie los puede volver a poner: no se publican en ningún sitio del que se
    puedan leer. Perderlos en una reimportación sería el peor daño que puede
    hacer este comando.
    """
    with tenant_context(empresa.id):
        sevilla = Workplace.objects.get(name="Sevilla")
        PublicHoliday.objects.create(
            tenant=empresa,
            day=datetime.date(2030, 6, 15),
            name="Feria",
            scope=HolidayScope.LOCAL,
            workplace=sevilla,
        )

    call_command("import_holidays", year=2030, company="B11111111")

    assert datetime.date(2030, 6, 15) in dias_de(empresa, HolidayScope.LOCAL)


@pytest.mark.django_db
def test_dry_run_no_escribe(calendario, empresa):
    call_command("import_holidays", year=2030, company="B11111111", dry_run=True)

    assert dias_de(empresa) == []


@pytest.mark.django_db
def test_no_toca_las_empresas_de_otro_pais(calendario, empresa, db):
    fuera = Tenant.objects.create(
        name="Fora Lda", tax_id="PT500", time_zone="Europe/Lisbon", country="PT"
    )

    call_command("import_holidays", year=2030)

    assert dias_de(empresa) != []
    assert dias_de(fuera) == []


@pytest.mark.django_db
def test_un_centro_sin_comunidad_recibe_solo_los_nacionales(calendario, empresa):
    with tenant_context(empresa.id):
        Workplace.objects.create(tenant=empresa, name="Sin poner", region="")

    call_command("import_holidays", year=2030, company="B11111111")

    with tenant_context(empresa.id):
        huerfano = Workplace.objects.get(name="Sin poner")
        assert not PublicHoliday.objects.filter(workplace=huerfano).exists()


@pytest.mark.django_db
def test_un_año_que_no_se_publica_lo_dice(calendario, empresa):
    with pytest.raises(CommandError, match="2031"):
        call_command("import_holidays", year=2031)


@pytest.mark.django_db
def test_un_centro_dado_de_baja_no_recibe_festivos(calendario, empresa):
    """Y los que ya tenía tampoco reviven: la baja de un centro es una baja."""
    with tenant_context(empresa.id):
        Workplace.objects.filter(name="Lleida").update(is_active=False)

    call_command("import_holidays", year=2030, company="B11111111")

    with tenant_context(empresa.id):
        lleida = Workplace.objects.get(name="Lleida")
        assert not PublicHoliday.objects.filter(workplace=lleida).exists()


# --------------------------------------------------------- el fichero que se envía


def test_el_calendario_que_se_publica_cuadra_con_su_propio_año():
    """Sobre el fichero de verdad, no sobre uno inventado.

    Una errata de año en una fecha ---«2025-01-06» dentro del fichero de 2026---
    se escribiría igual, y una reimportación de 2026 no la borraría nunca:
    el comando limpia por el rango del año que le pides. Quedaría un festivo
    fantasma que no se puede quitar sin entrar en la base.
    """
    from django.conf import settings

    raiz = pathlib.Path(settings.HOLIDAYS_DIR)
    ficheros = sorted(raiz.glob("*/[0-9][0-9][0-9][0-9].yaml"))
    assert ficheros, f"no se encontró ningún calendario en {raiz}"

    for fichero in ficheros:
        datos = yaml.safe_load(fichero.read_text(encoding="utf-8"))
        año = datos["year"]
        assert año == int(fichero.stem), f"{fichero} dice {año} y se llama {fichero.stem}"

        entradas = list(datos.get("national") or [])
        for dias in (datos.get("regions") or {}).values():
            entradas.extend(dias)

        for entrada in entradas:
            dia = entrada["day"]
            assert isinstance(dia, datetime.date), f"{fichero}: {dia!r} no es una fecha"
            assert dia.year == año, f"{fichero}: {dia} está fuera de {año}"
            assert entrada.get("name"), f"{fichero}: {dia} sin nombre"


def test_ningun_dia_se_repite_dentro_del_fichero():
    """Un día repetido lo tira `ignore_conflicts` sin decir nada.

    Y entonces el resumen del comando ---«N días a escribir»--- cuenta uno que
    no se escribió, que es la clase de número que se lee y se da por bueno.
    """
    from django.conf import settings

    for fichero in sorted(pathlib.Path(settings.HOLIDAYS_DIR).glob("*/[0-9][0-9][0-9][0-9].yaml")):
        datos = yaml.safe_load(fichero.read_text(encoding="utf-8"))

        nacionales = [e["day"] for e in datos.get("national") or []]
        assert len(nacionales) == len(set(nacionales)), f"{fichero}: día nacional repetido"

        for comunidad, dias in (datos.get("regions") or {}).items():
            fechas = [e["day"] for e in dias]
            assert len(fechas) == len(set(fechas)), f"{fichero}: {comunidad} repite un día"
            repetidos = set(fechas) & set(nacionales)
            assert not repetidos, f"{fichero}: {comunidad} repite el nacional {repetidos}"


# ------------------------------------------------ lo que el fichero puede traer mal
#
# `HOLIDAYS_DIR` existe para que un despliegue traiga su propio calendario,
# transcrito por su asesoría. O sea que el fichero **no** es de fiar, y un error
# ahí no se ve al leerlo: se ve en marzo, cuando alguien pregunta por qué le
# contaron un día de vacaciones que era festivo.


def escribir(raiz, pais, año, datos):
    directorio = raiz / pais
    directorio.mkdir(exist_ok=True)
    (directorio / f"{año}.yaml").write_text(yaml.safe_dump(datos), encoding="utf-8")


@pytest.mark.django_db
def test_una_fecha_del_año_equivocado_para_el_comando(calendario, empresa):
    """La errata natural: copiar el fichero del año anterior y olvidar una.

    Y la peor de las que no se ven, porque **no se puede deshacer
    reimportando**: la limpieza va por el rango del año que pides, así que un
    día de 2029 metido en el fichero de 2030 se queda ahí para siempre.
    """
    escribir(
        calendario,
        "es",
        2030,
        {
            "country": "ES",
            "year": 2030,
            "verified": True,
            "national": [{"day": datetime.date(2029, 1, 6), "name": "Epifanía"}],
        },
    )

    with pytest.raises(CommandError, match="fuera de 2030"):
        call_command("import_holidays", year=2030, company="B11111111")

    assert dias_de(empresa) == [], "no debería haber escrito nada"


@pytest.mark.django_db
def test_un_dia_repetido_para_el_comando(calendario, empresa):
    """Antes lo tragaba `ignore_conflicts` y el resumen contaba los dos.

    Copiar diecinueve comunidades de una resolución del BOE a mano es donde se
    repite un día, y el aviso tiene que llegar al importar, no al cuadrar los
    días de alguien seis meses después.
    """
    escribir(
        calendario,
        "es",
        2030,
        {
            "country": "ES",
            "year": 2030,
            "verified": True,
            "national": [
                {"day": datetime.date(2030, 1, 1), "name": "Año Nuevo"},
                {"day": datetime.date(2030, 1, 1), "name": "Año Nuevo otra vez"},
            ],
        },
    )

    with pytest.raises(CommandError, match="dos veces"):
        call_command("import_holidays", year=2030, company="B11111111")


@pytest.mark.django_db
def test_una_comunidad_que_repite_un_nacional_tambien(calendario, empresa):
    """El fichero lo dice con todas las letras: cuando una comunidad sustituye
    un nacional hay que quitarlo de arriba, no dejarlo en los dos sitios."""
    escribir(
        calendario,
        "es",
        2030,
        {
            "country": "ES",
            "year": 2030,
            "verified": True,
            "national": [{"day": datetime.date(2030, 1, 6), "name": "Epifanía"}],
            "regions": {"AN": [{"day": datetime.date(2030, 1, 6), "name": "Epifanía"}]},
        },
    )

    with pytest.raises(CommandError, match="repite el día nacional"):
        call_command("import_holidays", year=2030, company="B11111111")


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("falta", "queja"),
    [
        ({"year": 2030, "national": []}, "falta `country`"),
        ({"country": "ES", "year": 2030, "national": [{"name": "Sin fecha"}]}, "no es una fecha"),
        (
            {
                "country": "ES",
                "year": 2030,
                "national": [{"day": datetime.date(2030, 1, 1), "name": "  "}],
            },
            "no tiene nombre",
        ),
    ],
    ids=["sin país", "sin fecha", "sin nombre"],
)
def test_un_fichero_incompleto_se_queja_en_castellano(calendario, empresa, falta, queja):
    """Antes salía un `KeyError` pelado con su traza. Lo lee quien escribió el
    fichero, y lo que necesita es qué línea mirar."""
    escribir(calendario, "es", 2030, falta)

    with pytest.raises(CommandError, match=queja):
        call_command("import_holidays", year=2030, company="B11111111")


@pytest.mark.django_db
def test_dos_paises_publican_el_mismo_año_y_los_dos_se_importan(calendario, empresa, db):
    """El que hacía **imposible** importar el segundo.

    Se quedaba con el primero por orden alfabético, así que con `es/` y `pt/`
    publicando 2030, las empresas portuguesas no recibían nada y el comando
    decía que había terminado. Y la cabecera del módulo presume de que añadir
    un país es un fichero y no un cambio de código.
    """
    escribir(
        calendario,
        "pt",
        2030,
        {
            "country": "PT",
            "year": 2030,
            "verified": True,
            "national": [{"day": datetime.date(2030, 6, 10), "name": "Dia de Portugal"}],
        },
    )
    vecina = Tenant.objects.create(
        name="Fora Lda", tax_id="PT500", time_zone="Europe/Lisbon", country="PT"
    )

    call_command("import_holidays", year=2030)

    assert dias_de(vecina) == [datetime.date(2030, 6, 10)]
    assert datetime.date(2030, 1, 1) in dias_de(empresa), "y el de aquí sigue entrando"


@pytest.mark.django_db
def test_se_puede_pedir_solo_un_pais(calendario, empresa, db):
    escribir(
        calendario,
        "pt",
        2030,
        {
            "country": "PT",
            "year": 2030,
            "verified": True,
            "national": [{"day": datetime.date(2030, 6, 10), "name": "Dia de Portugal"}],
        },
    )
    vecina = Tenant.objects.create(
        name="Fora Lda", tax_id="PT500", time_zone="Europe/Lisbon", country="PT"
    )

    call_command("import_holidays", year=2030, country="PT")

    assert dias_de(vecina) != []
    assert dias_de(empresa) == [], "no se pidió el de aquí"


@pytest.mark.django_db
def test_el_resumen_dice_los_que_se_escribieron_de_verdad(calendario, empresa):
    """Cuando un día ya está puesto a mano, el que estaba manda y el otro no entra.

    Eso está bien ---nadie quiere que una importación pise lo que tecleó una
    persona--- pero el resumen decía «2 días a escribir» y escribía uno. Un
    número así se lee y se da por bueno.
    """
    import io

    with tenant_context(empresa.id):
        PublicHoliday.objects.create(
            tenant=empresa,
            day=datetime.date(2030, 1, 1),
            name="Puesto a mano para toda la empresa",
            scope=HolidayScope.LOCAL,
        )

    salida = io.StringIO()
    call_command("import_holidays", year=2030, company="B11111111", stdout=salida)
    dicho = salida.getvalue()

    assert "no se escribieron" in dicho, dicho
    with tenant_context(empresa.id):
        assert PublicHoliday.objects.filter(day=datetime.date(2030, 1, 1)).count() == 1
        assert (
            PublicHoliday.objects.get(day=datetime.date(2030, 1, 1)).scope == HolidayScope.LOCAL
        ), "el que estaba manda"
