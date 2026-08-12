"""España.

Todo lo que antes estaba repartido entre `tenants/rules.py`, `shifts/services.py`,
`users/models.py` y la pantalla de ajustes del frontend.

Las citas están en español y no pasan por gettext. Es deliberado: son el nombre
propio de una norma, y traducirlas produciría un texto que se lee bien y señala
a la ley equivocada. Las notas sí describen, así que podrían traducirse algún
día; de momento se quedan aquí, junto a lo que explican.

Ninguna cifra bloquea nada. El RD 1561/1995 modifica varias en sectores
concretos --- conducción, guardias, relevos de turno --- y un producto que se
negara a guardar sería inservible en transporte o en sanidad. Avisa, dice con
qué artículo, y decide la empresa.
"""

from __future__ import annotations

from datetime import time

from apps.legal.base import (
    Citation,
    ComplementaryHours,
    LegalFramework,
    MinorProtections,
)

ESPANA = LegalFramework(
    country="ES",
    name="España",
    # --------------------------------------------------------------- valores
    defaults={
        "weekly_hours": 40,
        "daily_rest_hours": 12,
        "weekly_rest_hours": 36,
        "break_after_hours": 6,
        "break_minutes": 15,
        "break_counts_as_work": False,
        "annual_overtime_hours": 80,
        "night_starts_at": time(22, 0),
        "night_ends_at": time(6, 0),
        "correction_consent_days": 7,
        "roster_notice_days": 5,
        "complementary_hours_share": 30,
    },
    # ------------------------------------------------------------ de dónde salen
    citations={
        "weekly_hours": Citation(
            "Art. 34.1 ET",
            "40 horas semanales de promedio en cómputo anual. Es un máximo legal "
            "ordinario; el convenio o el contrato pueden mejorarlo.",
        ),
        "daily_rest_hours": Citation(
            "Art. 34.3 ET",
            "Doce horas entre el final de una jornada y el comienzo de la siguiente. "
            "El RD 1561/1995 lo modifica en sectores concretos, y por eso apartarse "
            "se avisa en vez de impedirse.",
        ),
        "weekly_rest_hours": Citation(
            "Art. 37.1 ET",
            "Día y medio ininterrumpido. Acumulable en periodos de hasta catorce días.",
        ),
        "break_after_hours": Citation(
            "Art. 34.4 ET",
            "Quince minutos cuando la jornada continuada excede de seis horas.",
        ),
        "break_minutes": Citation("Art. 34.4 ET"),
        "break_counts_as_work": Citation(
            "Art. 34.4 ET",
            "Solo cuenta como trabajo efectivo cuando lo dice el convenio o el "
            "contrato. Darlo por hecho inflaría las horas registradas.",
        ),
        "annual_overtime_hours": Citation(
            "Art. 35.2 ET",
            "Ochenta horas al año. No cuentan las compensadas con descanso dentro de "
            "los cuatro meses siguientes, ni las de fuerza mayor del art. 35.3.",
        ),
        "night_starts_at": Citation(
            "Art. 36.1 ET",
            "Entre las 22:00 y las 06:00. Trabajar en esa franja no convierte a nadie "
            "en trabajador nocturno: esa condición la determina la empresa, y de ella "
            "dependen los límites.",
        ),
        "night_ends_at": Citation("Art. 36.1 ET"),
        "correction_consent_days": Citation(
            "Art. 4.b del proyecto de RD de registro de jornada",
            "El artículo exige la autorización de las dos partes para modificar un "
            "asiento y no fija plazo para responder. Sin plazo, una propuesta quedaría "
            "colgada para siempre; lo pone la empresa y está a la vista.",
        ),
        "complementary_hours_share": Citation(
            "Art. 12.5.c ET",
            "Hasta el 30 % de las horas ordinarias pactadas, y el convenio puede "
            "subirlo al 60 %. Es lo único que limita cuánto se puede pedir por "
            "encima de un contrato parcial, porque las horas extraordinarias las "
            "prohíbe el art. 12.4.c.",
        ),
        "roster_notice_days": Citation(
            "Art. 34.2 ET",
            "Cinco días de preaviso para la distribución irregular de la jornada. El "
            "art. 38.3 pide el calendario de vacaciones con dos meses.",
        ),
        "record_retention_years": Citation(
            "Art. 34.9 ET",
            "Cuatro años como mínimo. Conservar más tiempo necesita su propia "
            "justificación: no es dato del registro de jornada.",
        ),
        "annual_leave_days": Citation(
            "Art. 38.1 ET",
            "Treinta días naturales como mínimo, que en jornada de cinco días a la "
            "semana son veintidós laborables. El convenio puede dar más.",
        ),
    },
    # --------------------------------------------------- avisos del cuadrante
    finding_citations={
        "short_daily_rest": Citation("Art. 34.3 ET"),
        "weekly_hours_exceeded": Citation("Art. 34.1 ET"),
        # No es un incumplimiento: las horas por encima de lo pactado en jornada
        # parcial son complementarias, lícitas y con su propio tope.
        "over_contracted_hours": Citation("Art. 12.5 ET"),
        "no_agreed_weekly_hours": Citation(""),
        # Tampoco incumple un artículo: es un error de planificación, como el de
        # poner a alguien de vacaciones.
        "outside_the_contract": Citation(""),
        "break_owed": Citation("Art. 34.4 ET"),
        "short_weekly_rest": Citation("Art. 37.1 ET"),
        "looks_like_night_work": Citation("Art. 36.1 ET"),
        "minor_over_daily_limit": Citation("Art. 34.3 ET"),
        "minor_break_owed": Citation("Art. 34.4 ET"),
        "minor_night_work": Citation("Art. 6.2 ET"),
        # Estar en el cuadrante un día de vacaciones aprobadas no incumple
        # ningún artículo: es el error de planificación más corriente que hay, y
        # el que antes le llega a la persona. Sin cita a propósito.
        "rostered_on_leave": Citation(""),
    },
    # -------------------------------------------------- horas complementarias
    #
    # Lo único que protege de verdad a quien tiene jornada parcial. El art.
    # 12.4.c le prohíbe las horas extraordinarias, y lo que le deja hacer a
    # cambio son estas; sin tope, esa prohibición no le sirve de nada.
    #
    # Art. 12.5.c: las pactadas no pueden pasar del 30 % de las ordinarias, y el
    # convenio puede subirlo hasta el 60 %. Por eso el porcentaje acaba siendo
    # un valor que la empresa configura, con este como punto de partida.
    #
    # Art. 12.5.h: «se registrarán día a día y se totalizarán mensualmente»,
    # que es de dónde sale el periodo.
    complementary=ComplementaryHours(
        max_share=0.30,
        period_months=1,
        citation=Citation(
            "Art. 12.5.c ET",
            "Hasta el 30 % de las horas ordinarias, ampliable al 60 % por convenio. "
            "Se totalizan mensualmente (art. 12.5.h).",
        ),
    ),
    # ------------------------------------------------------ menores de 18 años
    #
    # No son ajustes y no pueden serlo. Ningún convenio puede rebajarlos, así
    # que ofrecer un campo para tocarlos sería ofrecer uno cuyo único uso es
    # incumplir.
    minors=MinorProtections(
        # Art. 34.3: «no podrán realizar más de ocho horas diarias de trabajo
        # efectivo», incluyendo la formación y sumando las de varios empleadores.
        # Sin el «salvo que el convenio disponga otra cosa» que el mismo
        # artículo concede para las personas adultas.
        max_daily_hours=8,
        # Art. 34.4: treinta minutos, y desde cuatro horas y media en vez de seis.
        break_after_hours=4.5,
        break_minutes=30,
        # Art. 37.1: dos días ininterrumpidos, no día y medio.
        weekly_rest_hours=48,
        # Art. 6.2: prohibición, no límite. No hay cantidad permitida.
        night_work_forbidden=True,
        # Art. 6.3: «Se prohíbe realizar horas extraordinarias a los menores de
        # dieciocho años.» Sin la excepción de fuerza mayor que el art. 12.4.c
        # concede a la jornada parcial.
        overtime_forbidden=True,
        citations={
            "max_daily_hours": Citation("Art. 34.3 ET"),
            "break": Citation("Art. 34.4 ET"),
            "weekly_rest": Citation("Art. 37.1 ET"),
            "night_work": Citation("Art. 6.2 ET"),
            "overtime": Citation("Art. 6.3 ET"),
            # Art. 6.1: no se puede trabajar por debajo de los dieciséis.
            "minimum_age": Citation("Art. 6.1 ET"),
        },
    ),
)
