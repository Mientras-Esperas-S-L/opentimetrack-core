"""The name of this installation, for the templates that sign in its name."""

from __future__ import annotations

from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def installation_name() -> str:
    """«OpenTimeTrack», or the name the installation set for itself."""
    return settings.INSTALLATION_NAME
