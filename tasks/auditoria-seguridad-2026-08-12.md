# Auditoría de seguridad · 12/08/2026

Dos pasadas. La primera pregunta qué puede hacer alguien **con una sesión
legítima** para que el registro diga lo que no debe. La segunda mira el
producto por fuera: configuración, autenticación, entrada de datos,
dependencias y lo que se publica sin querer.

Todo lo que sigue está comprobado ejecutándolo, no leyendo. Lo arreglado lleva
su prueba, escrita como ataque: si alguien reabre el agujero, la prueba se
pone roja y dice por qué importaba.

---

## Parte 1 · Lógica de negocio

54 ataques con sesión válida contra las reglas que protegen el registro.
**Cincuenta y uno ya estaban cerrados.** Tres no.

### Lo que estaba bien

Lo apunto porque un informe que solo lista fallos no dice si se ha mirado.

- La marca temporal la pone el servidor siempre. Mandarla en el cuerpo no hace
  nada.
- No se puede fichar por otra persona, ni elegir si es entrada o salida.
- Un fichaje no se puede editar ni borrar por API, tampoco siendo
  administrador: el viewset no expone PATCH ni DELETE.
- Una manipulación hecha por debajo, directamente en la base de datos, la
  detecta el hash.
- Nadie aprueba una corrección ajena, ni acepta un cambio propuesto a otro, ni
  impone uno sobre su propio registro, ni discrepa en nombre de nadie.
- Una corrección no se aplica dos veces, ni se aprueba después de rechazada, ni
  puede colocar un fichaje en el futuro.
- Nadie se asciende a sí mismo, ni el único administrador puede degradarse o
  darse de baja.
- Quien está de baja no puede fichar aunque su token siga vivo.
- Ningún endpoint responde sin sesión (14 comprobados).
- Consultar el registro de otra persona deja rastro; consultar el propio, no.
- La auditoría no admite escritura por API.

### Lo que no

**Un responsable o administrador podía aprobar un cambio en su propio registro
horario.** Lo pedía, lo aprobaba, y no había segundo par de ojos en todo el
camino. Igual con las vacaciones. Y había una segunda puerta: proponerse el
cambio a uno mismo, que lo deja esperando la conformidad de la persona
afectada, y aceptarlo.

No es un fallo de permisos, y por eso lo pasaron todas las comprobaciones: los
dos perfiles tienen derecho a aprobar. Es un hueco de separación de funciones.
El procedimiento de corrección existe para que un cambio en el tiempo de
trabajo pase por una segunda persona, y justo para quienes más podían abusar
de él, no pasaba.

Arreglado en `apps/common/four_eyes.py`. Si hay alguien más que pueda decidir,
se rechaza. Si no lo hay —un autónomo, una empresa de dos personas— se aplica
**y queda dicho en la nota de resolución**, que es lo que viaja al informe de
Inspección. Permitirlo en silencio dejaría al registro sin poder distinguir una
corrección que aprobó un segundo par de ojos de una que no.

La comprobación filtra por empresa a propósito: `User.objects` abarca todas,
porque el inicio de sesión tiene que encontrar a la gente antes de saber de
qué empresa es. Sin ese filtro, el administrador de otro cliente contaría como
segundo par de ojos. Hay prueba de eso.

---

## Parte 2 · Pentest

### Crítico · sin límite de intentos, en ninguna parte

`DEFAULT_THROTTLE_RATES` estaba en los ajustes con cuatro límites y **ningún
`DEFAULT_THROTTLE_CLASSES` al lado**. DRF solo lee `throttle_scope` si
`ScopedRateThrottle` está entre las clases, y solo aplica los límites de anónimo
y usuario si esas clases están listadas. No estaba ninguna.

Comprobado contra el servidor: doce contraseñas seguidas contra
`/api/auth/token/`, todas procesadas. Ocho correos de recuperación seguidos a
la misma dirección, todos enviados.

Es decir: adivinación de contraseñas sin límite contra cualquier dirección
conocida, y un endpoint que manda correo a cualquier dirección tantas veces
como se le pida.

Arreglado. Ahora corta en el sexto intento, y la contraseña correcta tampoco
pasa con el cubo lleno —si no, el límite sería un trámite—.

Al activarlo apareció un segundo problema que habría tumbado todas las
integraciones: `UserRateThrottle` de DRF construye su clave con
`request.user.pk`, y una aplicación externa autentica como `ApplicationUser`,
que no tiene clave primaria. Cada fichaje delegado respondía con un
AttributeError. Hay dos clases propias en `apps/common/throttling.py`: las
aplicaciones también se limitan —una integración en bucle es el origen más
probable de una avalancha— pero en su propio cubo y por credencial, para que el
bucle de un cliente no deje sin sesión a la plantilla.

**Lo que no cubre:** un ataque distribuido desde muchas IP. El límite es por
origen, que es la mitigación estándar y la primera; un bloqueo por cuenta
sería la siguiente y no está.

### Alto · el justificante no validaba nada

Ni tipo, ni tamaño, ni contenido. Dos consecuencias.

**Tamaño.** Cualquiera con sesión podía subir un fichero de cualquier tamaño,
tantas veces como quisiera. En despliegue con disco eso es el disco; con
almacenamiento de objetos, la factura.

**Tipo.** La descarga sirve con `as_attachment=True`, así que con disco no se
renderiza nada. Con almacenamiento de objetos no: ese camino redirige a una URL
firmada, y el fichero vuelve del dominio del almacén con el tipo con el que se
subió y sin `Content-Disposition`. Un `.html` subido como justificante se
renderizaría ahí, en un dominio que la empresa considera suyo, con el documento
de otra persona dentro.

Arreglado por los dos lados: lista blanca de extensiones y 10 MB en
`apps/absences/uploads.py`, y `ContentDisposition: attachment` en los
parámetros de S3. Cualquiera de los dos bastaría para el caso conocido; el par
es lo que sobrevive a que alguien cambie el otro más adelante.

Un detalle del arreglo: los validadores estaban solo en el modelo y saltaban
desde `full_clean()` como `ValidationError` de Django, que DRF no traduce, así
que un fichero demasiado grande devolvía un 500 en vez de decir cuál es el
límite. Están también en el serializer.

### Lo que se revisó y está bien

- **`manage.py check --deploy`** limpio con los ajustes de producción. TLS
  obligatorio, HSTS con preload, cookies seguras, nosniff, `X-Frame-Options:
  DENY`, referrer policy.
- **CORS** por lista blanca. Un origen no autorizado no recibe ninguna cabecera
  CORS. Sin credenciales.
- **Dependencias**: `pip-audit` y `npm audit` sin vulnerabilidades conocidas,
  ni en producción ni en desarrollo.
- **Secretos**: `.env` ignorado, solo `.env.example` versionado. Las
  contraseñas que aparecen en el repositorio son de pruebas y de `seed_demo`,
  que se niega a ejecutarse sin DEBUG.
- **Admin de Django**: solo montado con DEBUG. En producción esa ruta no
  existe.
- **Descarga de justificantes**: comprueba permisos primero, 404 en vez de 403
  para no confirmar que la ausencia existe, deja rastro cuando el documento es
  de otra persona, y con S3 la URL firmada caduca en cinco minutos.
- **Frontend**: ni un `dangerouslySetInnerHTML`, ni `innerHTML`, ni `eval`.
- **Inyección SQL**: todo pasa por el ORM; no hay SQL en crudo fuera de las
  migraciones, y esas no llevan entrada del usuario.

### Pendiente, por orden

- [x] **Sin CSP en ninguna parte.** Escrita en `deploy/cabeceras.md`, con las
      tres decisiones que hay que entender antes de tocarla (`unsafe-inline`
      para Emotion, la API en `connect-src`, `blob:` para las descargas).
      Pendiente de aplicar cuando exista el servidor web: no hay configuración
      donde ponerla todavía.
- [x] **`/api/schema/` y `/api/docs/` responden 200 sin sesión.**
      `PUBLISH_API_SCHEMA`, por defecto sí. Configurable, no cerrado: con un
      producto AGPL el esquema no es secreto, pero es la instancia del cliente
      la que lo publica.
- [ ] **Bloqueo por cuenta** tras N fallos, contra el ataque distribuido que el
      límite por IP no ve.
- [ ] **Rotación de la clave de firma (JWT)**. Hoy es `SECRET_KEY`: rotarla
      invalida todas las sesiones a la vez y no hay procedimiento escrito.
- [ ] **Cabeceras del servidor web** cuando exista: CSP, `Permissions-Policy`,
      y `Cross-Origin-Opener-Policy`.

---

## Cifras

| | |
|---|---|
| Ataques de lógica de negocio | 54 |
| Refutados sin cambios | 51 |
| Arreglados | 3 (misma causa) |
| Hallazgos del pentest | 2 (uno crítico, uno alto) |
| Pruebas nuevas | 64 |
| Suite completa | 435 |
