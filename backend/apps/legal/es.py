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
    NightWork,
    ShiftWork,
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
        # Sobre lo fichado, no sobre lo planificado. El art. 34.1 habla de horas
        # trabajadas, y quien no tiene cuadrante ---horario flexible--- no tenía
        # ninguna comprobación.
        "worked_over_the_maximum": Citation("Art. 34.1 ET"),
        "worked_over_the_contract": Citation("Art. 12.5 ET"),
        "break_owed": Citation("Art. 34.4 ET"),
        "short_weekly_rest": Citation("Art. 37.1 ET"),
        "looks_like_night_work": Citation("Art. 36.1 ET"),
        "night_worker_average": Citation("Art. 36.1 ET"),
        "consecutive_night_weeks": Citation("Art. 36.3 ET"),
        # No incumple: es la reducción que el propio RD permite al cambiar de
        # turno. Se avisa de la diferencia porque hay que devolverla, no porque
        # esté mal hecha.
        "changeover_rest_owed": Citation("Art. 19.a RD 1561/1995"),
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
    # ------------------------------------------------------------ nocturnidad
    #
    # El art. 36.1 define dos cosas distintas y la diferencia lo es todo:
    #
    # «Se considera trabajo nocturno el realizado entre las diez de la noche y
    # las seis de la mañana.» Eso es una ventana del reloj, y la toca cualquiera
    # que cierre un bar.
    #
    # «Se considerará trabajador nocturno a aquel que realice normalmente en
    # período nocturno una parte no inferior a tres horas de su jornada diaria
    # de trabajo, así como a aquel que se prevea que puede realizar en tal
    # período una parte no inferior a un tercio de su jornada de trabajo anual.»
    # Eso es un estado de la persona, y es al estado al que se le pegan los
    # límites: las ocho horas de promedio y la prohibición de horas extras.
    #
    # Confundirlos fue uno de los cuatro errores que corrigió la revisión
    # jurídica del 11/08. Quien cubre una noche suelta no es trabajador nocturno
    # y no le aplica nada de esto.
    night=NightWork(
        window_starts_at=time(22, 0),
        window_ends_at=time(6, 0),
        qualifying_daily_hours=3,
        qualifying_annual_share=1 / 3,
        # «La jornada de trabajo de los trabajadores nocturnos no podrá exceder
        # de ocho horas diarias de promedio, en un período de referencia de
        # quince días.» Promedio, no techo: nueve horas un día no incumplen nada
        # si la quincena sale a ocho.
        average_daily_hours=8,
        average_over_days=15,
        # «Los trabajadores nocturnos no podrán realizar horas extraordinarias.»
        overtime_forbidden=True,
        # Art. 36.2: el trabajo nocturno tiene una retribución específica que
        # fija la negociación colectiva, «salvo que el salario se haya
        # establecido atendiendo a que el trabajo sea nocturno por su propia
        # naturaleza o se haya acordado la compensación de este trabajo por
        # descansos». De ahí salen los días libres de más de un turno de noche:
        # de esa compensación o del convenio, no del Estatuto directamente.
        rest_may_compensate=True,
        citations={
            "definition": Citation(
                "Art. 36.1 ET",
                "Tres horas de la jornada diaria en período nocturno, o un tercio de "
                "la jornada anual. Es un estado de la persona, no una propiedad del "
                "turno.",
            ),
            "average": Citation(
                "Art. 36.1 ET",
                "Ocho horas de promedio en quince días. Promedio, no máximo diario.",
            ),
            "overtime": Citation("Art. 36.1 ET"),
            "pay": Citation(
                "Art. 36.2 ET",
                "Retribución específica por convenio, salvo que el salario ya lo "
                "contemple o se compense con descansos.",
            ),
            "health": Citation(
                "Art. 36.4 ET",
                "Evaluación de salud gratuita antes de la asignación y periódicamente "
                "después. Fuera del registro de jornada, pero va con el estado.",
            ),
        },
    ),
    # --------------------------------------------------------- trabajo a turnos
    #
    # Estas cifras no añaden límites: quitan los que no tocan. Un equipo que rota
    # de noches a mañanas no puede descansar doce horas en el relevo, y el
    # cuadrante lo estaba avisando como incumplimiento. No lo es.
    shifts=ShiftWork(
        # Art. 36.3: «ningún trabajador estará en el de noche más de dos semanas
        # consecutivas, salvo adscripción voluntaria».
        max_consecutive_night_weeks=2,
        # Art. 19.a RD 1561/1995: en trabajo a turnos, cuando el trabajador
        # cambie de equipo, el descanso entre jornadas podrá reducirse hasta un
        # mínimo de siete horas, compensando la diferencia en períodos de hasta
        # cuatro semanas.
        changeover_rest_hours=7,
        # Art. 19.b: el descanso semanal puede acumularse por períodos de hasta
        # cuatro semanas, frente a los catorce días del art. 37.1 general.
        accumulation_weeks=4,
        citations={
            "night_weeks": Citation(
                "Art. 36.3 ET",
                "Dos semanas consecutivas como máximo en el turno de noche, salvo que "
                "la persona se haya adscrito voluntariamente.",
            ),
            "changeover_rest": Citation(
                "Art. 19.a RD 1561/1995",
                "Hasta siete horas en el relevo de turno, compensando la diferencia en "
                "cuatro semanas.",
            ),
            "rest_accumulation": Citation("Art. 19.b RD 1561/1995"),
        },
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
