"""Reading the help: the list of sections with their articles, and one article.

**Anyone signed in can read it, including the account that administers the
installation.** That account belongs to no company, so `IsAuthenticatedInTenant`
turns it away from the rest of the service on purpose; help is not service data, and
the person setting an installation up is exactly who needs it most. Hence
`sin_empresa = True`.

**The language is the reader's, with a fallback.** Asking for help in a language
nobody has written yet should return the Spanish article, not an empty drawer: half
an answer beats none, and the drawer says which language it ended up showing.
"""

from __future__ import annotations

from django.db.models import Prefetch
from django.utils import translation
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAuthenticatedInTenant
from apps.help.models import HelpArticle, HelpBlock, HelpSection

#: What is served when the reader's language has no content yet.
FALLBACK_LANGUAGE = "es"


def _languages_for(request) -> list[str]:
    asked = (request.query_params.get("language") or translation.get_language() or "")[:2]
    return [lang for lang in (asked, FALLBACK_LANGUAGE) if lang]


def _article_brief(article: HelpArticle) -> dict:
    return {
        "slug": article.slug,
        "title": article.title,
        "summary": article.summary,
        "section": article.section.slug,
    }


class HelpIndexView(APIView):
    """The sections with their articles: what the drawer shows when nothing is picked."""

    permission_classes = [IsAuthenticatedInTenant]
    sin_empresa = True

    @extend_schema(request=None, responses={200: dict})
    def get(self, request):
        for language in _languages_for(request):
            secciones = (
                HelpSection.objects.filter(language=language, is_active=True)
                .prefetch_related(
                    Prefetch(
                        "articles",
                        queryset=HelpArticle.objects.filter(is_published=True).order_by("title"),
                    )
                )
                .order_by("order", "title")
            )
            salida = [
                {
                    "slug": s.slug,
                    "title": s.title,
                    "icon": s.icon,
                    "articles": [_article_brief(a) for a in s.articles.all()],
                }
                for s in secciones
                if s.articles.all()
            ]
            if salida:
                return Response({"language": language, "sections": salida})
        return Response({"language": FALLBACK_LANGUAGE, "sections": []})


class HelpArticleView(APIView):
    """One article, with its blocks in order."""

    permission_classes = [IsAuthenticatedInTenant]
    sin_empresa = True

    @extend_schema(request=None, responses={200: dict})
    def get(self, request, slug):
        for language in _languages_for(request):
            article = (
                HelpArticle.objects.filter(slug=slug, language=language, is_published=True)
                .select_related("section")
                .first()
            )
            # An article in a switched-off section is not served, and the reason is in
            # `HelpArticle.is_visible`: it would be invisible without saying why.
            if article is None or not article.is_visible:
                continue
            bloques = HelpBlock.objects.filter(article=article).order_by("order")
            return Response(
                {
                    "language": language,
                    **_article_brief(article),
                    "blocks": [{"kind": b.kind, "data": b.data} for b in bloques],
                    "updated_at": article.updated_at,
                }
            )
        return Response({"detail": "No such article."}, status=404)


class HelpSearchView(APIView):
    """Articles whose title, summary or text matches what was typed.

    Plain `icontains` over title, summary and blocks, and not full text search: the
    whole corpus is a few dozen short articles, the index would cost more to keep than
    the scan costs to run, and PostgreSQL's Spanish dictionary is one more thing to
    get wrong. When the corpus grows enough for this to be slow, it will be obvious.
    """

    permission_classes = [IsAuthenticatedInTenant]
    sin_empresa = True

    @extend_schema(request=None, responses={200: dict})
    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        if len(query) < 2:
            return Response({"query": query, "results": []})

        for language in _languages_for(request):
            articles = (
                HelpArticle.objects.filter(
                    language=language, is_published=True, section__is_active=True
                )
                .select_related("section")
                .order_by("title")
            )
            encontrados = [
                a
                for a in articles
                if query.lower() in a.title.lower()
                or query.lower() in a.summary.lower()
                or HelpBlock.objects.filter(article=a, data__icontains=query).exists()
            ]
            if encontrados:
                return Response(
                    {
                        "query": query,
                        "language": language,
                        "results": [_article_brief(a) for a in encontrados],
                    }
                )
        return Response({"query": query, "results": []})
