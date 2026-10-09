import { alCatalogo } from '../i18n/index.js'

/** Cómo se llama en pantalla cada campo que el servidor anota en el registro.
 *
 *  El servidor guarda los cambios con el nombre interno del campo y el valor
 *  tal cual ---«kind: MODIFY», «department: — → Desarrollo»---, y así debe
 *  seguir: el registro no se reescribe, y lo que se guarda no depende del
 *  idioma de quien lo hizo. Se traduce aquí, al enseñarlo.
 *
 *  Un campo que no esté en la lista sale con su nombre interno. Es preferible
 *  a callarlo: el registro tiene que enseñar todo lo que se anotó.
 */
export const CAMPOS = {
  // Personas
  first_name: alCatalogo('Nombre'),
  last_name: alCatalogo('Apellidos'),
  email: alCatalogo('Correo'),
  employee_id: alCatalogo('Número de empleado'),
  role: alCatalogo('Perfil'),
  department: alCatalogo('Departamento'),
  workplace: alCatalogo('Centro de trabajo'),
  is_active: alCatalogo('Activa'),
  was_active: alCatalogo('Estaba activa'),
  regime: alCatalogo('Régimen'),
  contract_end: alCatalogo('Fin del contrato'),
  future_shifts: alCatalogo('Turnos futuros'),
  sent_to: alCatalogo('Enviado a'),
  picked_up: alCatalogo('Recogido'),

  // Correcciones, ausencias y horas extra
  kind: alCatalogo('Tipo'),
  agreed: alCatalogo('De acuerdo'),
  type: alCatalogo('Tipo'),
  from: alCatalogo('Desde'),
  to: alCatalogo('Hasta'),
  start_date: alCatalogo('Desde'),
  end_date: alCatalogo('Hasta'),
  code: alCatalogo('Código'),
  recorded_by_company: alCatalogo('Lo registró la empresa'),
  days: alCatalogo('Días'),
  minutes: alCatalogo('Minutos'),
  settlement: alCatalogo('Compensación'),
  decided_alone: alCatalogo('Decidido sobre su propio caso'),
  status: alCatalogo('Estado'),
  requested_on: alCatalogo('Pedida el'),
  answered_on: alCatalogo('Contestada el'),
  answer: alCatalogo('Respuesta'),
  called_on: alCatalogo('Llamamiento el'),
  signed_on: alCatalogo('Firmado el'),
  starts_on: alCatalogo('Empieza'),
  ends_on: alCatalogo('Termina'),
  agreed_share: alCatalogo('Parte pactada (%)'),

  // Permisos
  name: alCatalogo('Nombre'),
  amount: alCatalogo('Cantidad'),
  unit: alCatalogo('Unidad'),
  period: alCatalogo('Periodo'),

  // Cuadrante y turnos
  pattern: alCatalogo('Turno'),
  segments: alCatalogo('Tramos'),
  people: alCatalogo('Personas'),
  created: alCatalogo('Creados'),
  removed: alCatalogo('Quitados'),
  from_label: alCatalogo('De'),
  to_label: alCatalogo('A'),

  // Centros y festivos
  day: alCatalogo('Día'),
  scope: alCatalogo('Ámbito'),
  time_zone: alCatalogo('Zona horaria'),
  region: alCatalogo('Comunidad'),
  municipality: alCatalogo('Municipio'),

  // Empresa y ajustes
  tax_id: alCatalogo('CIF/NIF'),
  country: alCatalogo('País'),
  language: alCatalogo('Idioma'),
  administrator: alCatalogo('Quién la administra'),
  managers_see_whole_company: alCatalogo('Los responsables ven toda la empresa'),
  basis: alCatalogo('Con qué amparo se organizó el registro'),
  reference: alCatalogo('Cuál (convenio o acuerdo)'),
  in_force_since: alCatalogo('En vigor desde'),
  consulted_on: alCatalogo('Consulta a la representación'),
  note: alCatalogo('Nota'),
  annual_leave_days: alCatalogo('Días de vacaciones al año'),
  leave_days_are_working_days: alCatalogo('Contar en días laborables'),
  leave_year_start_month: alCatalogo('Mes en que empieza el periodo'),
  special_regime: alCatalogo('Régimen de jornada especial'),
  weekly_hours: alCatalogo('Horas semanales'),
  daily_rest_hours: alCatalogo('Descanso entre jornadas'),
  weekly_rest_hours: alCatalogo('Descanso semanal'),
  annual_overtime_hours: alCatalogo('Horas extra al año'),
  entry_tolerance_minutes: alCatalogo('Margen de entrada'),
  exit_tolerance_minutes: alCatalogo('Margen de salida'),
  max_open_hours: alCatalogo('Jornada abierta como mucho'),
  break_after_hours: alCatalogo('Descanso a partir de'),
  break_minutes: alCatalogo('Minutos de descanso'),
  break_counts_as_work: alCatalogo('El descanso computa como trabajo'),
  night_starts_at: alCatalogo('El trabajo nocturno empieza'),
  night_ends_at: alCatalogo('El trabajo nocturno acaba'),
  overtime_rest_days: alCatalogo('Plazo para descansar las horas extra'),
  holiday_worked_compensation: alCatalogo('Cómo se compensa el festivo trabajado'),
  holiday_rest_multiplier: alCatalogo('Descanso por hora de festivo'),
  night_worked_compensation: alCatalogo('Cómo se compensa el trabajo nocturno'),
  night_rest_multiplier: alCatalogo('Descanso por hora de noche'),
  complementary_hours_share: alCatalogo('Horas complementarias (%)'),
  correction_consent_days: alCatalogo('Plazo para aceptar una corrección (días)'),
  irregular_settlement_months: alCatalogo('Plazo para compensar la distribución irregular (meses)'),
  roster_notice_days: alCatalogo('Preaviso del cuadrante (días)'),
  seniority_leave: alCatalogo('Permiso por antigüedad'),
  standby_weekly_hours: alCatalogo('Horas de presencia a la semana'),
  quiet_from: alCatalogo('Sin avisos desde'),
  quiet_until: alCatalogo('Sin avisos hasta'),
  record_retention_years: alCatalogo('Conservación del registro'),
  security_metadata_retention_days: alCatalogo('Conservación de metadatos'),

  // Aplicaciones, acceso y mantenimiento
  scopes: alCatalogo('Permisos'),
  issuer: alCatalogo('Proveedor de identidad'),
  sessions_ended: alCatalogo('Sesiones cerradas'),
  rows: alCatalogo('Filas'),
  purged: alCatalogo('Borrados'),
  deleted: alCatalogo('Borrados'),
  kept_from: alCatalogo('Se conserva desde'),
  declared_years: alCatalogo('Años declarados'),
  applied_years: alCatalogo('Años aplicados'),
  // `before` suelto es una fecha de corte; con `after`, la foto de antes.
  before: alCatalogo('Anteriores a'),
}

/** Lo que se anota para enlazar y no para leer: identificadores internos.
 *
 *  «correction: 9a6c1e37-…» no le dice nada a nadie. La entrada ya dice qué
 *  se hizo y sobre quién; el identificador sigue en la descarga.
 */
export const OCULTOS = new Set(['id', 'correction', 'absence', 'employee', 'oidc_sub', 'oidc_issuer'])

/** Los valores que son una opción de una lista, con su nombre de pantalla. */
export const VALORES = {
  role: {
    EMPLOYEE: alCatalogo('Persona trabajadora'),
    MANAGER: alCatalogo('Responsable'),
    ADMIN: alCatalogo('Administración'),
    ADVISOR: alCatalogo('Asesoría laboral'),
  },
  kind: {
    ADD: alCatalogo('Añadir un fichaje que falta'),
    MODIFY: alCatalogo('Cambiar la hora de un fichaje'),
    VOID: alCatalogo('Anular un fichaje que no debió existir'),
  },
  type: {
    VACATION: alCatalogo('Vacaciones'),
    SICK_LEAVE: alCatalogo('Baja médica'),
    PAID_LEAVE: alCatalogo('Permiso retribuido'),
    UNPAID_LEAVE: alCatalogo('Permiso sin sueldo'),
    SUSPENSION: alCatalogo('Contrato suspendido'),
    PERSONAL: alCatalogo('Permiso'),
    OTHER: alCatalogo('Otro'),
  },
  scope: {
    NATIONAL: alCatalogo('Nacional'),
    REGIONAL: alCatalogo('Autonómico'),
    LOCAL: alCatalogo('Local'),
    COMPANY: alCatalogo('Empresa'),
  },
  unit: {
    DAYS_CALENDAR: alCatalogo('días naturales'),
    DAYS_WORKING: alCatalogo('días laborables'),
    HOURS: alCatalogo('horas'),
    WEEKS: alCatalogo('semanas'),
  },
  period: {
    EVENT: alCatalogo('cada vez'),
    DAY: alCatalogo('al día'),
    WEEK: alCatalogo('a la semana'),
    MONTH: alCatalogo('al mes'),
    YEAR: alCatalogo('al año'),
  },
  status: {
    PENDING: alCatalogo('En negociación'),
    ACCEPTED: alCatalogo('Aceptada'),
    ALTERNATIVE: alCatalogo('Se propuso una alternativa'),
    REFUSED: alCatalogo('Denegada'),
    WITHDRAWN: alCatalogo('Retirada por la persona'),
  },
  regime: {
    FULL_TIME: alCatalogo('Jornada completa'),
    PART_TIME: alCatalogo('Tiempo parcial'),
    REDUCED: alCatalogo('Jornada reducida'),
    TRAINING_ALT: alCatalogo('Contrato formativo en alternancia'),
    TRAINING_PRO: alCatalogo('Contrato formativo para práctica profesional'),
    TRAINING: alCatalogo('Contrato formativo, sin concretar cuál'),
    VARIABLE: alCatalogo('Sin cifra pactada'),
    UNLIMITED: alCatalogo('Sin plazo (art. 38.3, párrafo segundo)'),
    EIGHTEEN_MONTHS: alCatalogo('Dieciocho meses (art. 38.3, párrafo tercero)'),
  },
  settlement: {
    REST: alCatalogo('Compensada con descanso'),
    PAID: alCatalogo('Retribuida'),
  },
  basis: {
    COLLECTIVE: alCatalogo('convenio colectivo'),
    COMPANY: alCatalogo('acuerdo de empresa'),
    EMPLOYER: alCatalogo('decisión de la empresa, previa consulta a la representación'),
  },
  holiday_worked_compensation: {
    REST: alCatalogo('descanso'),
    PAID: alCatalogo('dinero'),
  },
  night_worked_compensation: {
    REST: alCatalogo('descanso'),
    PAID: alCatalogo('un pago específico'),
    SALARY: alCatalogo('nada: el salario ya lo tiene en cuenta'),
  },
  special_regime: {
    URBAN_PROPERTY: alCatalogo('Porteros y empleados de fincas urbanas'),
    GUARDS: alCatalogo('Guardas y vigilantes'),
    FARMING: alCatalogo('Trabajos en el campo'),
    RETAIL_HOSPITALITY: alCatalogo('Comercio y hostelería'),
    ROAD_TRANSPORT: alCatalogo('Transporte por carretera'),
    RAIL: alCatalogo('Transporte ferroviario'),
    SEA: alCatalogo('Trabajo en el mar'),
    AIR: alCatalogo('Transporte aéreo'),
    HEALTHCARE: alCatalogo('Sanidad, con guardias'),
    HAZARDOUS: alCatalogo('Exposición a riesgos ambientales'),
    COLD_STORAGE: alCatalogo('Cámaras frigoríficas'),
    MINING: alCatalogo('Minería y trabajos subterráneos'),
    CONSTRUCTION: alCatalogo('Construcción y obras públicas'),
  },
  language: {
    es: alCatalogo('Español'),
    ca: alCatalogo('Catalán'),
    gl: alCatalogo('Gallego'),
    en: alCatalogo('Inglés'),
  },
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const esFoto = (valor) => valor !== null && typeof valor === 'object' && !Array.isArray(valor)

/** Las líneas que se enseñan de un `changes`: [campo, antes, después] o
 *  [campo, valor]. Sin lo que es solo un identificador.
 *
 *  `{before: {...}, after: {...}}` es la foto entera de una persona antes y
 *  después, que es como anota sus cambios la API de personas. Se enseña campo a
 *  campo y solo lo que cambió: escrita tal cual salía «[object Object]».
 */
export function lineasDelCambio(changes) {
  const cambios = changes ?? {}
  if (esFoto(cambios.before) || esFoto(cambios.after)) {
    const antes = esFoto(cambios.before) ? cambios.before : {}
    const despues = esFoto(cambios.after) ? cambios.after : {}
    const campos = [...new Set([...Object.keys(antes), ...Object.keys(despues)])]
    const resto = Object.fromEntries(
      Object.entries(cambios).filter(([campo]) => campo !== 'before' && campo !== 'after'),
    )
    return [
      ...campos
        .filter((campo) => !OCULTOS.has(campo))
        .filter((campo) => String(antes[campo] ?? '') !== String(despues[campo] ?? ''))
        .map((campo) => [campo, antes[campo], despues[campo]]),
      ...lineasDelCambio(resto),
    ]
  }
  return Object.entries(cambios)
    .filter(([campo, valor]) => {
      if (OCULTOS.has(campo)) return false
      const valores = Array.isArray(valor) ? valor : [valor]
      return !valores.every((v) => typeof v === 'string' && UUID.test(v))
    })
    .map(([campo, valor]) =>
      Array.isArray(valor) && valor.length === 2 ? [campo, valor[0], valor[1]] : [campo, valor],
    )
}
