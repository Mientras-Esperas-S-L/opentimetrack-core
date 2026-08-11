#!/usr/bin/env python
"""Utilidad de línea de órdenes de Django."""

import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "No se encuentra Django. ¿Está activado el entorno virtual "
            "o se está ejecutando dentro del contenedor?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
