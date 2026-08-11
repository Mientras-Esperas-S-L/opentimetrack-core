"""Modelos base y aislamiento entre empresas.

Aquí vive la pieza más delicada del sistema: el filtrado por inquilino. Una
consulta que se escape de su empresa es una brecha de privacidad, no un fallo
funcional, así que el aislamiento no se deja a que cada vista se acuerde de
filtrar: va en el gestor por defecto del modelo.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from contextvars import ContextVar

from django.db import models

# Inquilino de la petición en curso. Se usa una variable de contexto y no un
# atributo de módulo porque esto tiene que ser correcto también con servidores
# asíncronos, donde varias peticiones comparten hilo.
_inquilino_actual: ContextVar[uuid.UUID | None] = ContextVar("inquilino_actual", default=None)


def obtener_inquilino_actual() -> uuid.UUID | None:
    return _inquilino_actual.get()


def fijar_inquilino_actual(tenant_id: uuid.UUID | None):
    return _inquilino_actual.set(tenant_id)


def restaurar_inquilino(token) -> None:
    _inquilino_actual.reset(token)


@contextmanager
def inquilino(tenant_id: uuid.UUID | None):
    """Ejecuta un bloque en el contexto de una empresa concreta."""
    token = fijar_inquilino_actual(tenant_id)
    try:
        yield
    finally:
        restaurar_inquilino(token)


class SinAlcanceDeInquilino(Exception):
    """Se consultó un modelo por inquilino sin haber fijado cuál.

    Es un error de programación, no una condición esperada. Fallar aquí es
    preferible a devolver datos de todas las empresas.
    """


class BaseModel(models.Model):
    """Identificador opaco y marcas de tiempo, comunes a todo el dominio."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantQuerySet(models.QuerySet):
    def del_inquilino(self, tenant_id):
        return self.filter(tenant_id=tenant_id)


class TenantManager(models.Manager):
    """Gestor por defecto: filtra por el inquilino del contexto, siempre.

    Si no hay inquilino fijado, no devuelve nada en lugar de devolverlo todo.
    Esa asimetría es deliberada: el fallo por defecto tiene que ser no ver datos,
    nunca verlos de más.
    """

    def get_queryset(self):
        qs = TenantQuerySet(self.model, using=self._db)
        tenant_id = obtener_inquilino_actual()
        if tenant_id is None:
            return qs.none()
        return qs.filter(tenant_id=tenant_id)


class TodosLosInquilinosManager(models.Manager):
    """Gestor sin filtrar. Para migraciones, tareas de sistema y pruebas.

    Su nombre es largo a propósito: en una revisión de código, ver
    `objects_all_tenants` en una vista tiene que cantar.
    """

    def get_queryset(self):
        return TenantQuerySet(self.model, using=self._db)


class TenantOwnedModel(BaseModel):
    """Todo lo que pertenece a una empresa hereda de aquí."""

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="%(class)ss",
        db_index=True,
    )

    # El gestor por defecto filtra. El sin filtrar hay que pedirlo por su nombre.
    objects = TenantManager()
    objects_all_tenants = TodosLosInquilinosManager()

    class Meta:
        abstract = True
