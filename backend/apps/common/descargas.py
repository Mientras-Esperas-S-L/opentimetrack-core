"""Nombres de fichero que salen del sistema.

Un nombre de persona acaba en dos sitios que no son texto: la cabecera
`Content-Disposition` de una descarga y la entrada de un zip. Los dos lo tratan
como una **ruta**, y un nombre es texto libre que escribe la administración de la
empresa --- o un conector, por `/api/app/people/`.

Lo que se ha visto pasando un apellido raro por ahí:

- `../../../evil` produce la entrada `../../../evil_Nombre.pdf` dentro del zip.
  Quien lo descomprima con una herramienta que no valide rutas ---`extractall`
  de Python, sin ir más lejos--- escribe tres niveles por encima del destino. Y
  quien descomprime ese zip es la gestoría o la Inspección.
- Una comilla rompe la cabecera `Content-Disposition`, que lleva el nombre entre
  comillas sin escapar.
- Y sin apellido salía `_Jefa.pdf`, con el separador colgando: el respaldo que el
  código tenía previsto no llegaba a saltar porque la cadena no estaba vacía.
"""

from __future__ import annotations

import re
import unicodedata

#: Lo que se deja pasar. Todo lo demás ---barras, dos puntos, comillas, saltos de
#: línea, controles--- se convierte en un guion bajo. La lista es corta a
#: propósito: es más fácil razonar sobre lo que entra que sobre lo que no.
PERMITIDOS = re.compile(r"[^A-Za-z0-9._-]+")


def nombre_seguro(texto: str, *, respaldo: str = "sin-nombre") -> str:
    """Un trozo de nombre de fichero, sin nada que se lea como ruta.

    Los acentos se transliteran en vez de perderse: «García» sale como «Garcia»
    y no como «Garc_a», que es lo que haría un filtro a secas y deja un nombre
    que no se reconoce.
    """
    plano = unicodedata.normalize("NFKD", str(texto or ""))
    plano = plano.encode("ascii", "ignore").decode("ascii")
    limpio = PERMITIDOS.sub("_", plano).strip("._-")
    # Un nombre hecho solo de puntos ---«..»--- se queda en nada después del
    # `strip`, que es justo lo que se quiere.
    return limpio or respaldo


def nombre_de_persona(person, *, extension: str) -> str:
    """El fichero de una persona dentro de un lote, y **único**.

    Lleva su identificador porque dos personas pueden llamarse igual: sin él, el
    zip de una empresa con dos Ana García traía dos entradas con el mismo nombre
    y la segunda pisaba a la primera al descomprimir. Se entregaba un informe
    menos de los que dice la carátula, sin que nada avisara.

    El número de empleado si lo hay ---que es lo que reconoce quien recibe el
    fichero--- y si no, el principio del identificador interno.
    """
    apellido = nombre_seguro(person.last_name, respaldo="")
    nombre = nombre_seguro(person.first_name, respaldo="")
    quien = nombre_seguro(person.employee_id or str(person.id)[:8], respaldo="persona")
    partes = [p for p in (apellido, nombre, quien) if p]
    return f"{'_'.join(partes)}.{extension}"
