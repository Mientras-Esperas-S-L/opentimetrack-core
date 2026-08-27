# Dependencias: qué hay, por qué, y cómo se revisa

Auditadas el **27/08/2026**. El inventario está aquí para que la próxima revisión
empiece por comparar, no por descubrir.

## De un vistazo

| | Backend | Frontend |
|---|---|---|
| Declaradas | 31 (20 de base, 1 de producción, 10 de desarrollo) | 20 (11 de producción, 9 de desarrollo) |
| Instaladas con las transitivas | 93 | --- |
| Vulnerabilidades conocidas | **0** ---eran 2, en `pypdf`--- | **0** |
| Licencias | 14 MIT, 8 BSD-3, 3 BSD, 2 Apache-2.0, 1 LGPL-3.0, 1 MPL-2.0 | --- |

Ninguna licencia es incompatible con la AGPL-3.0 del producto. La LGPL y la MPL
son copyleft débil: obligan a publicar los cambios **de esa biblioteca**, no del
programa que la usa.

## Las dos vulnerabilidades que había, y por qué no eran explotables

`pypdf` por debajo de 6.15.0 puede consumir memoria sin techo con un PDF preparado
a mano ---un `/ToUnicode` enorme, o rangos de anchura de fuente CID muy grandes---.
Suena a que un justificante subido podría tumbar el servidor. **No aquí**, por dos
razones que conviene conocer antes de asustarse con el siguiente aviso:

- `pypdf` es una dependencia **de desarrollo**. Solo la usan cuatro pruebas, para
  leer los PDF que **genera el propio proyecto** y comprobar qué pone dentro.
- El PDF que sube una persona **no se parsea**. La validación de justificantes
  comprueba los **bytes de la cabecera** (`%PDF-`) y el tamaño, y nada más abre el
  fichero. El informe de jornada se genera con `reportlab`, que escribe PDF; no
  los lee.

Actualizada a 6.16.2 de todos modos: el arreglo es gratis y quita el aviso de cada
`push`.

## Dos que venían de prestado

Estaban **importadas y no declaradas**, funcionando porque otro paquete las
arrastraba. Eso aguanta hasta que ese otro paquete cambia su árbol de
dependencias, y entonces se rompe en el despliegue y no en desarrollo, donde ya
estaban instaladas.

| Paquete | Quién lo importa | Quién lo traía |
|---|---|---|
| `cryptography` | `vapid_keys`, un comando **de producción** | `pywebpush`, `py-vapid`, `http_ece` |
| `pillow` | La prueba que abre la imagen de un justificante | `reportlab` |

Ahora están declaradas, y lo vigila `test_las_dependencias_estan_declaradas`.

## Una que sobraba

`factory-boy`: cero importaciones en todo el proyecto. Las pruebas construyen sus
objetos a mano, que con dos empresas y cuatro perfiles se lee mejor que una
factoría. Retirada, y comprobado que las 1.299 pruebas siguen pasando **sin ella
instalada**, no solo sin ella declarada.

## Las que se usan sin nombrarse

Dos no aparecen en ningún fichero porque se usan **por su efecto**:

- `pytest-cov`: lo invoca el CI con `pytest --cov=apps`. La exención se valida
  contra la configuración de cobertura de `pyproject.toml` ---y contra el propio CI
  cuando se puede leer, que dentro del contenedor no: solo monta `backend/`---.
- `ipython`: `manage.py shell` lo usa si está instalado, sin decirlo en ninguna
  configuración. Es una comodidad del equipo; quitarlo no rompe nada y el shell
  cae al de Python. Esta exención **se sostiene solo en su propio texto**, y así
  queda dicho.

## Cómo se revisa

```bash
# Vulnerabilidades conocidas
gh api repos/Mientras-Esperas-S-L/opentimetrack-core/dependabot/alerts \
  --jq '.[] | select(.state=="open") | "\(.security_advisory.severity) \(.dependency.package.name)"'
cd frontend && npm audit

# Versiones más nuevas de lo que declaramos
podman exec -i opentimetrack_api_1 pip list --outdated
cd frontend && npx npm-check-updates

# Y las dos comprobaciones que van solas
podman exec -i opentimetrack_api_1 pytest apps/common/tests/test_las_dependencias_estan_declaradas.py
```

**Antes de declarar una versión, míra la que está instalada.** Suponerla da un
conflicto de resolución: el 27/08 declarar `cryptography==46.0.5` de memoria hizo
fallar la instalación entera, porque `pywebpush 2.4.0` pide una más nueva y la que
había puesta era la 50.

## Lo que el guard no comprueba

- **Si una dependencia está abandonada.** Que exista una versión nueva no dice si
  hay alguien detrás. Eso se mira a ojo, y toca hacerlo.
- **El árbol transitivo.** 93 paquetes instalados para 31 declarados: los otros 62
  los eligió alguien más. Dependabot los vigila, y ahí acaba lo que sabemos.
- **El frontend, más allá de `npm audit`.** No hay revisión de licencias del árbol
  de npm, que es mucho más grande. Queda pendiente y no es urgente: el frontend no
  se distribuye como biblioteca.
