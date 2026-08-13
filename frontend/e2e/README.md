# Pruebas de interfaz

Playwright contra la pila de desarrollo, tal cual la usa una persona: navegador
de verdad, formularios de verdad, y la API llamada a pelo donde lo que se prueba
es la seguridad —porque que la interfaz esconda un botón no prueba nada—.

## Ejecutar

```bash
podman compose up -d
podman exec opentimetrack_api_1 python manage.py seed_demo --reset   # la primera vez
cd frontend && npx playwright test
```

Un informe navegable queda en `e2e-report/`.

## Cómo está montado, y por qué

**Las sesiones se abren una vez** (`00-sesiones.setup.js`) y se reutilizan. No es
una optimización: `/api/auth/token/` admite cinco intentos por minuto —es lo que
impide probar contraseñas a lo bruto— así que una suite que entrara en cada
prueba se estrellaría contra su propia defensa a partir de la sexta, y el fallo
parecería de la aplicación. Además reutiliza la sesión de la vuelta anterior si
sigue viva, para que lanzar la suite dos veces seguidas tampoco choque.

**Las pruebas de la entrada sí pasan por el formulario** y se espacian veinte
segundos, porque ahí lo que se prueba es justamente la puerta.

**En serie y con un trabajador.** Escriben en la base de desarrollo; dos a la vez
sobre la misma empresa se pisan.

**Sin reintentos.** Un fallo intermitente es información, no ruido que haya que
esconder repitiendo hasta que pase.

## Qué hay

| Fichero | Qué cubre |
|---|---|
| `01-entrada.spec.js` | La entrada: credenciales, mensaje idéntico exista o no el correo, cierre de sesión |
| `02-aislamiento.spec.js` | Que conocer un identificador no sirva de nada, y lo que un operario no puede hacer |
| `03-sesion.spec.js` | Renovación silenciosa del acceso, y qué ve cada perfil |

## La empresa vecina

`seed_demo` crea **Vecina S.L.** con dos personas y un departamento. Existe para
una sola cosa: que otra empresa tenga identificadores que alguien de la primera
pueda intentar usar. Sin ella, el aislamiento sería una promesa sin comprobar.
