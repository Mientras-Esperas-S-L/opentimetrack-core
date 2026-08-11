"""Renderers for the report formats.

They exist for a reason that is easy to miss: DRF treats `?format=` as content
negotiation, so asking for `?format=pdf` without a renderer declaring that name
returns 404 rather than a document. Registering them keeps the query parameter
the API documentation promises, instead of inventing a different one to dodge
the framework.
"""

from __future__ import annotations

from rest_framework.renderers import BaseRenderer


class PassthroughRenderer(BaseRenderer):
    """Hands the bytes over untouched.

    The view builds the document itself, so there is nothing to serialise here.
    """

    charset = None
    render_style = "binary"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if isinstance(data, str):
            return data.encode("utf-8")
        return data


class CSVRenderer(PassthroughRenderer):
    media_type = "text/csv"
    format = "csv"


class PDFRenderer(PassthroughRenderer):
    media_type = "application/pdf"
    format = "pdf"
