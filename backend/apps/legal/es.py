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
    LeaveFamily,
    LeaveKind,
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
            ceiling=40,
        ),
        "daily_rest_hours": Citation(
            "Art. 34.3 ET",
            "Doce horas entre el final de una jornada y el comienzo de la siguiente. "
            "El RD 1561/1995 lo modifica en sectores concretos, y por eso apartarse "
            "se avisa en vez de impedirse.",
            floor=12,
        ),
        "weekly_rest_hours": Citation(
            "Art. 37.1 ET",
            "Día y medio ininterrumpido. Acumulable en periodos de hasta catorce días.",
            floor=36,
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
            ceiling=80,
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
        # El preaviso de la distribución irregular. No es un incumplimiento
        # por sí solo ---un cambio urgente es legítimo--- pero es el dato que
        # nadie apunta y el que se pide cuando alguien reclama.
        "short_roster_notice": Citation("Art. 34.2 ET"),
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
        # Trabajar un festivo es lícito: el art. 37.2 los hace retribuidos y no
        # recuperables, no prohibidos. Lleva cita porque de ahí sale la
        # compensación, no porque se incumpla.
        "rostered_on_a_holiday": Citation("Art. 37.2 ET"),
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
    # ------------------------------------------------------------- permisos
    #
    # El art. 37.3, tal y como quedó tras el RDL 5/2023, más los que están
    # repartidos por otros artículos y en la práctica se piden igual.
    #
    # Dos detalles que un catálogo hecho de memoria se salta y son del 5/2023:
    # el permiso de cinco días alcanza a quien conviva en el mismo domicilio
    # aunque no haya parentesco; y los cuatro días de fuerza mayor se cuentan
    # **en horas**, no en días.
    #
    # Son el punto de partida de cada empresa, no la regla: el convenio mejora
    # cualquiera de estos, y lo que se copia a la empresa es lo que manda desde
    # ese momento.
    leave_types=(
        LeaveKind(
            code="es.vacation",
            name="Vacaciones",
            family=LeaveFamily.VACATION,
            basis="Art. 38 ET",
            amount=None,
            note="La cifra sale de los ajustes de la empresa, no de aquí: es la única "
            "que depende del convenio persona a persona.",
        ),
        LeaveKind(
            code="es.sick.common",
            name="Baja por enfermedad común o accidente no laboral",
            vacation_recovery="EIGHTEEN_MONTHS",
            family=LeaveFamily.SICK_LEAVE,
            basis="Art. 45.1.c ET",
            amount=None,
            note="No se guarda el parte: desde el RD 1060/2022 el INSS se lo manda "
            "directamente a la empresa.",
        ),
        LeaveKind(
            code="es.sick.work",
            name="Baja por accidente de trabajo o enfermedad profesional",
            vacation_recovery="EIGHTEEN_MONTHS",
            family=LeaveFamily.SICK_LEAVE,
            basis="Art. 45.1.c ET",
            amount=None,
            note="Otra contingencia que la común, y otra entidad la que paga. Se "
            "distinguen porque el informe y la cotización no las tratan igual.",
        ),
        # ---------------------------------------------------------- art. 37.3
        LeaveKind(
            code="es.marriage",
            name="Matrimonio o registro de pareja de hecho",
            family=LeaveFamily.PAID_LEAVE,
            basis="Art. 37.3.a ET",
            amount=15,
            unit="DAYS_CALENDAR",
            per="EVENT",
            needs_justification=True,
        ),
        LeaveKind(
            code="es.family_illness",
            name="Accidente o enfermedad graves, hospitalización o intervención",
            family=LeaveFamily.PAID_LEAVE,
            basis="Art. 37.3.b ET",
            amount=5,
            unit="DAYS_CALENDAR",
            per="EVENT",
            needs_justification=True,
            note="Cónyuge, pareja de hecho o parientes hasta segundo grado, y también "
            "cualquier persona que conviva en el mismo domicilio y necesite cuidado "
            "efectivo, aunque no haya parentesco (RDL 5/2023).",
        ),
        LeaveKind(
            code="es.bereavement",
            name="Fallecimiento de familiar hasta segundo grado",
            family=LeaveFamily.PAID_LEAVE,
            basis="Art. 37.3.b bis ET",
            amount=2,
            unit="DAYS_CALENDAR",
            per="EVENT",
            extra_when_travelling=2,
            needs_justification=True,
        ),
        LeaveKind(
            code="es.moving_house",
            name="Traslado del domicilio habitual",
            family=LeaveFamily.PAID_LEAVE,
            basis="Art. 37.3.c ET",
            amount=1,
            unit="DAYS_CALENDAR",
            per="EVENT",
        ),
        LeaveKind(
            code="es.public_duty",
            name="Deber inexcusable de carácter público y personal",
            family=LeaveFamily.PAID_LEAVE,
            basis="Art. 37.3.d ET",
            amount=None,
            needs_justification=True,
            note="El tiempo indispensable. Incluye el ejercicio del sufragio activo, "
            "el jurado y las citaciones judiciales.",
        ),
        LeaveKind(
            code="es.union_duties",
            name="Funciones sindicales o de representación",
            family=LeaveFamily.PAID_LEAVE,
            basis="Art. 37.3.e ET",
            amount=None,
            unit="HOURS",
            per="MONTH",
            note="El crédito horario lo fija el art. 68.e según el tamaño de la "
            "plantilla, y el convenio puede ampliarlo. Ponlo aquí cuando lo sepas.",
        ),
        LeaveKind(
            code="es.prenatal",
            name="Exámenes prenatales y preparación al parto",
            family=LeaveFamily.PAID_LEAVE,
            basis="Art. 37.3.f ET",
            amount=None,
            note="El tiempo indispensable, dentro de la jornada. También las sesiones "
            "preceptivas de información en adopción y acogimiento.",
        ),
        LeaveKind(
            code="es.force_majeure",
            name="Fuerza mayor familiar",
            family=LeaveFamily.PAID_LEAVE,
            basis="Art. 37.9 ET",
            amount=4,
            unit="DAYS_WORKING",
            per="YEAR",
            note="El artículo lo dice en horas: «las horas de ausencia ... equivalentes "
            "a cuatro días al año». Por eso se pide por horas y no por días sueltos.",
        ),
        # -------------------------------------------- cuidados y otros permisos
        LeaveKind(
            code="es.breastfeeding",
            name="Lactancia",
            family=LeaveFamily.PAID_LEAVE,
            basis="Art. 37.4 ET",
            amount=1,
            unit="HOURS",
            per="DAY",
            note="Una hora de ausencia, divisible en dos fracciones, o media hora de "
            "reducción, hasta que el menor cumpla nueve meses. Acumulable en jornadas "
            "completas cuando lo permita el convenio.",
        ),
        LeaveKind(
            code="es.exams",
            name="Exámenes de formación reglada",
            family=LeaveFamily.PAID_LEAVE,
            basis="Art. 23.1.a ET",
            amount=None,
            needs_justification=True,
        ),
        LeaveKind(
            code="es.job_search",
            name="Búsqueda de empleo durante el preaviso",
            family=LeaveFamily.PAID_LEAVE,
            basis="Art. 53.2 ET",
            amount=6,
            unit="HOURS",
            per="WEEK",
            note="Solo durante el preaviso de un despido por causas objetivas.",
        ),
        LeaveKind(
            code="es.parental",
            name="Permiso parental",
            family=LeaveFamily.UNPAID_LEAVE,
            basis="Art. 48 bis ET",
            paid=False,
            amount=8,
            unit="WEEKS",
            per="EVENT",
            note="Hasta que el menor cumpla ocho años. **No retribuido**, que es lo que "
            "más se confunde de él.",
        ),
        # ------------------------------------------------------- suspensiones
        #
        # Art. 45: el contrato se suspende y no hay obligación de trabajar.
        # Entran porque durante ellas **no debe esperarse jornada**, que es lo
        # que explica el hueco en el registro. La tramitación --- el parte al
        # INSS, el expediente del ERTE --- se hace en otro sitio.
        #
        # Ninguna va marcada como retribuida: la empresa no paga. Lo hace la
        # Seguridad Social, la mutua, o nadie. Quién paga se dice en la nota,
        # porque el campo solo distingue si sale de la nómina.
        LeaveKind(
            code="es.birth",
            name="Nacimiento y cuidado del menor",
            vacation_recovery="UNLIMITED",
            family=LeaveFamily.SUSPENSION,
            basis="Art. 48.4 ET",
            paid=False,
            amount=16,
            unit="WEEKS",
            per="EVENT",
            note="Dieciséis semanas, ampliables. Las seis primeras, inmediatamente "
            "después del parto, son obligatorias y a jornada completa. Paga la "
            "Seguridad Social.",
        ),
        LeaveKind(
            code="es.adoption",
            name="Adopción, guarda con fines de adopción o acogimiento",
            vacation_recovery="UNLIMITED",
            family=LeaveFamily.SUSPENSION,
            basis="Art. 48.5 ET",
            paid=False,
            amount=16,
            unit="WEEKS",
            per="EVENT",
        ),
        LeaveKind(
            code="es.pregnancy_risk",
            name="Riesgo durante el embarazo",
            vacation_recovery="UNLIMITED",
            family=LeaveFamily.SUSPENSION,
            basis="Art. 45.1.e ET",
            paid=False,
            initiated_by="COMPANY",
            amount=None,
            note="Cuando no cabe adaptar el puesto ni cambiar de función. Paga la "
            "mutua, y es contingencia profesional.",
        ),
        LeaveKind(
            code="es.breastfeeding_risk",
            name="Riesgo durante la lactancia natural",
            vacation_recovery="UNLIMITED",
            family=LeaveFamily.SUSPENSION,
            basis="Art. 45.1.e ET",
            paid=False,
            initiated_by="COMPANY",
            amount=None,
            note="Hasta que el menor cumpla nueve meses.",
        ),
        LeaveKind(
            code="es.unpaid_leave",
            name="Excedencia voluntaria",
            family=LeaveFamily.SUSPENSION,
            basis="Art. 46.2 ET",
            paid=False,
            amount=None,
            note="Entre cuatro meses y cinco años, con al menos un año de antigüedad. "
            "Solo da derecho preferente al reingreso, no a reserva del puesto.",
        ),
        LeaveKind(
            code="es.childcare_leave",
            name="Excedencia por cuidado de hijos",
            family=LeaveFamily.SUSPENSION,
            basis="Art. 46.3 ET",
            paid=False,
            # Tres años. Sin cifra a propósito: la unidad más larga de este
            # catálogo son semanas, y poner 156 sería exacto y ilegible. Una
            # cifra falsa se lee y se cree; un hueco con la nota al lado, no.
            amount=None,
            note="Hasta tres años. El primero reserva el mismo puesto; después, uno "
            "del mismo grupo profesional.",
        ),
        LeaveKind(
            code="es.family_care_leave",
            name="Excedencia por cuidado de familiares",
            family=LeaveFamily.SUSPENSION,
            basis="Art. 46.3 ET",
            paid=False,
            amount=None,
            note="Hasta dos años, salvo que el convenio dé más.",
        ),
        LeaveKind(
            code="es.public_office_leave",
            name="Excedencia forzosa por cargo público o sindical",
            family=LeaveFamily.SUSPENSION,
            basis="Art. 46.1 ET",
            paid=False,
            amount=None,
            note="Da derecho a la conservación del puesto y al cómputo de antigüedad.",
        ),
        LeaveKind(
            code="es.erte",
            name="ERTE",
            family=LeaveFamily.SUSPENSION,
            basis="Art. 47 ET",
            paid=False,
            initiated_by="COMPANY",
            amount=None,
            note="Puede **suspender** el contrato o **reducir la jornada** entre un 10 y "
            "un 70 %. Si reduce, pon el porcentaje en la solicitud: el cuadrante pasa a "
            "medirse contra la jornada reducida en vez de contra el contrato entero.",
        ),
        LeaveKind(
            code="es.red",
            name="Mecanismo RED",
            family=LeaveFamily.SUSPENSION,
            basis="Art. 47 bis ET",
            paid=False,
            initiated_by="COMPANY",
            amount=None,
            note="Igual que el ERTE en cuanto a jornada. Lo activa el Consejo de "
            "Ministros para un sector o para toda la economía.",
        ),
        LeaveKind(
            code="es.disciplinary",
            name="Suspensión de empleo y sueldo",
            family=LeaveFamily.SUSPENSION,
            basis="Art. 45.1.h ET",
            paid=False,
            initiated_by="COMPANY",
            amount=None,
            needs_justification=True,
            note="Sanción. La duración la fija el convenio según la falta.",
        ),
        LeaveKind(
            code="es.strike",
            name="Huelga",
            family=LeaveFamily.SUSPENSION,
            basis="Art. 45.1.l ET",
            paid=False,
            initiated_by="COMPANY",
            amount=None,
            note="Se registra porque explica el hueco del día, no para contar nada. "
            "Es un derecho fundamental: se ejerce, no se pide, y por eso la anota la "
            "empresa como hecho en vez de pasar por una cola de aprobación.",
        ),
        LeaveKind(
            code="es.lockout",
            name="Cierre patronal",
            family=LeaveFamily.SUSPENSION,
            basis="Art. 45.1.m ET",
            paid=False,
            initiated_by="COMPANY",
            amount=None,
        ),
        LeaveKind(
            code="es.custody",
            name="Privación de libertad sin sentencia",
            family=LeaveFamily.SUSPENSION,
            basis="Art. 45.1.g ET",
            paid=False,
            initiated_by="COMPANY",
            amount=None,
            note="Mientras no haya sentencia condenatoria.",
        ),
        LeaveKind(
            code="es.gender_violence_suspension",
            name="Suspensión por violencia de género",
            family=LeaveFamily.SUSPENSION,
            basis="Art. 45.1.n ET",
            paid=False,
            amount=None,
            note="Hasta seis meses, prorrogables por el juez hasta dieciocho. Cuenta "
            "como periodo de cotización efectiva.",
        ),
        # ---------------------------------------------------------- de convenio
        LeaveKind(
            code="es.medical",
            name="Visita médica",
            family=LeaveFamily.PAID_LEAVE,
            basis="",
            amount=None,
            unit="HOURS",
            needs_justification=True,
            note="No está en el Estatuto: sale del convenio, y casi siempre en horas. "
            "Se incluye porque lo pide todo el mundo; ajusta el tope al tuyo.",
        ),
        LeaveKind(
            code="es.personal_days",
            name="Asuntos propios",
            family=LeaveFamily.PAID_LEAVE,
            basis="",
            amount=None,
            unit="DAYS_WORKING",
            per="YEAR",
            note="Tampoco está en el Estatuto. Los da el convenio y no son vacaciones: "
            "no salen del mismo saldo. Pon los tuyos.",
        ),
    ),
    # ------------------------------------------------- comunidades autónomas
    #
    # Art. 37.2: catorce fiestas al año como máximo, dos de ellas locales. De
    # las doce restantes, las comunidades fijan las suyas y pueden sustituir
    # algunas de las nacionales, así que el calendario laboral no se puede
    # resolver sin saber la comunidad.
    #
    # Los códigos son los de la ISO 3166-2:ES. Las dos ciudades autónomas van en
    # la misma lista porque a estos efectos hacen lo mismo: fijan sus fiestas.
    #
    # Canarias además está en otra zona horaria, que es la otra razón por la que
    # el centro de trabajo existe.
    # Las dos de España. La hora canaria va una menos todo el año, así que un
    # turno de mañana en Las Palmas empieza a las 07:00 suyas y a las 08:00 de
    # Madrid --- y el registro tiene que contarlo en la de la persona.
    time_zones={
        "Europe/Madrid": "Península y Baleares",
        "Atlantic/Canary": "Canarias",
    },
    regions={
        "ES-AN": "Andalucía",
        "ES-AR": "Aragón",
        "ES-AS": "Principado de Asturias",
        "ES-CB": "Cantabria",
        "ES-CE": "Ceuta",
        "ES-CL": "Castilla y León",
        "ES-CM": "Castilla-La Mancha",
        "ES-CN": "Canarias",
        "ES-CT": "Cataluña",
        "ES-EX": "Extremadura",
        "ES-GA": "Galicia",
        "ES-IB": "Illes Balears",
        "ES-MC": "Región de Murcia",
        "ES-MD": "Comunidad de Madrid",
        "ES-ML": "Melilla",
        "ES-NC": "Comunidad Foral de Navarra",
        "ES-PV": "País Vasco",
        "ES-RI": "La Rioja",
        "ES-VC": "Comunitat Valenciana",
    },
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
