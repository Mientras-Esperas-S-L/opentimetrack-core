"""El armazón contra el que se mide el registro, y quién lo movió.

Centros, departamentos, turnos-tipo y festivos. Ninguno dejaba rastro, y no son
decoración administrativa: un centro lleva la **zona horaria** con la que se mide
la jornada de su gente ---cambiarla mueve el límite del día de todos a la vez--- y
un festivo decide qué cuenta como laborable y qué entra en el saldo de vacaciones.

Salió del barrido de escrituras de la vuelta 42: cuatro vistas que cambian datos
sin dejar constancia de nadie. La misma clase que el cuadrante y el catálogo de
permisos, y por el mismo motivo ---son cosas que se configuran una vez y luego
nadie mira, hasta el día que los números no cuadran y hay que reconstruir por qué---.

Un solo `AuditAction` para las cuatro, con `target_type` diciendo cuál. Cuatro
entradas del enum para el mismo hecho ---«alguien movió el marco»--- solo harían
más difícil filtrar el rastro.
"""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from apps.audit.models import AuditAction
from apps.audit.services import record


def _legible(valor) -> str:
    """A texto, porque `changes` va a JSON y una fecha o un UUID no lo son.

    Y porque el rastro se lee años después: comparar dos textos es lo mismo que
    comparar los valores, y además sobrevive a que el campo cambie de tipo.
    """
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "sí" if valor else "no"
    return str(valor)


class StructureTrail:
    """Anota altas, cambios y bajas del armazón de la empresa.

    Se mezcla en un `ModelViewSet`. Cada vista declara en `trail_fields` lo que
    de verdad importa que quede: no todo el serializador, porque una entrada que
    recita quince campos idénticos y uno distinto no se lee.

    El alta hay que anotarla desde el `perform_create` de cada vista, que es
    donde se le pone la empresa al objeto. Los otros dos salen de aquí.
    """

    #: Campos cuyo cambio merece una entrada.
    trail_fields: tuple[str, ...] = ()

    def anotar(self, instance, que, cambios=None):
        record(
            action=AuditAction.STRUCTURE_CHANGED,
            actor=self.request.user,
            target=instance,
            target_label=f"{que}: {instance}",
            changes=cambios or {},
        )

    def _foto(self, instance) -> dict:
        return {campo: _legible(getattr(instance, campo, None)) for campo in self.trail_fields}

    def perform_update(self, serializer):
        antes = self._foto(serializer.instance)
        objeto = serializer.save()
        despues = self._foto(objeto)

        cambiados = {k: [antes[k], despues[k]] for k in antes if antes[k] != despues[k]}
        # Solo si cambió algo de la lista. Un rastro que anota cada pulsación de
        # «Guardar» es uno que nadie lee, y entonces da igual lo que tenga dentro.
        if cambiados:
            self.anotar(objeto, _("Changed"), cambiados)

    def perform_destroy(self, instance):
        # Antes de borrar: después el objeto ya no puede decir cómo se llamaba.
        self.anotar(instance, _("Deleted"), self._foto(instance))
        instance.delete()
