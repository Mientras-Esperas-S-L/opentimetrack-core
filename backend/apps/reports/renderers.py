"""Renderers for the report formats.

They exist for a reason that is easy to miss: DRF treats `?format=` as content
negotiation, so asking for `?format=pdf` without a renderer declaring that name
returns 404 rather than a document. Registering them keeps the query parameter
the API documentation promises, instead of inventing a different one to dodge
the framework.
"""

from __future__ import annotations

import json

from rest_framework.renderers import BaseRenderer


class PassthroughRenderer(BaseRenderer):
    """Hands the bytes over untouched --- but an error is not bytes.

    The view builds the document itself, so there is nothing to serialise for a
    successful response.

    A **failed** one is another matter, and this is where it went wrong. Being
    the only renderers declared, these also render the error bodies, and handing
    a dict straight to `HttpResponse` makes Django iterate its keys: every
    refusal from this endpoint came back as five bytes, `error`, labelled
    `application/pdf`.

    So none of them ever arrived. Not the two hundred people limit that says to
    narrow it down by department, not the reversed date range, not «nobody
    worked in that period», not the wrong parameter name. All of them written
    with care, all of them invisible.

    Anything that is not bytes or text is an error body: it goes out as JSON,
    and the content type is corrected to say so.
    """

    charset = None
    render_style = "binary"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode("utf-8")

        respuesta = (renderer_context or {}).get("response")
        if respuesta is not None:
            # Un cliente que pidió un PDF y recibe un fallo necesita poder
            # leerlo. Dejarle `application/pdf` con JSON dentro es peor que no
            # contestar nada.
            respuesta["Content-Type"] = "application/json"
        return json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")


class CSVRenderer(PassthroughRenderer):
    media_type = "text/csv"
    format = "csv"


class PDFRenderer(PassthroughRenderer):
    media_type = "application/pdf"
    format = "pdf"
