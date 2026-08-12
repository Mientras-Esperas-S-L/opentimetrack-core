"""Which country's law applies, and how to add another.

`Tenant.country` has existed since the first migration with a `help_text` that
says it "selects the applicable legal rules". Nothing read it. This is what
reads it.

## Adding a country

One file, `apps/legal/<iso>.py`, exporting a `LegalFramework`, and one line in
`FRAMEWORKS` below. Nothing else in the codebase should need to change --- if it
does, something is still hardcoded and that is the bug, not the new country.

The part that cannot be done by a programmer is the content. A framework is a
list of figures and the articles they come from; getting one wrong produces a
product that is confidently incorrect, which is worse than one that says
nothing. Somebody who knows that country's law writes it, the same way the
Spanish agreement fichas were written by reading the BOE.
"""

from __future__ import annotations

from apps.legal.base import DIRECTIVE, Citation, LegalFramework, MinorProtections
from apps.legal.es import ESPANA

#: ISO 3166-1 alpha-2 -> framework.
FRAMEWORKS: dict[str, LegalFramework] = {
    "ES": ESPANA,
}


def for_country(code: str | None) -> LegalFramework:
    """The framework for a country code, or the directive's floors.

    An unknown country gets `DIRECTIVE` and **not** Spain. Falling back to
    Spain would give a German company Spanish figures under a German flag: they
    would look configured, nobody would question them, and every warning would
    cite an article that does not apply there. The directive's floors are lower
    than any member state's own, so they under-warn rather than mislead.
    """
    if not code:
        return DIRECTIVE
    return FRAMEWORKS.get(code.upper(), DIRECTIVE)


def for_company(company) -> LegalFramework:
    return for_country(getattr(company, "country", None))


__all__ = [
    "DIRECTIVE",
    "FRAMEWORKS",
    "Citation",
    "LegalFramework",
    "MinorProtections",
    "for_company",
    "for_country",
]
