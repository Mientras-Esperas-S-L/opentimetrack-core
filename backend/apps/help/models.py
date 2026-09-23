"""In-app help: sections, articles and the blocks they are made of.

Two decisions shape everything here, and both are the opposite of what the rest of
this codebase does.

**Help belongs to the installation, not to a company.** It does not inherit from
`TenantOwnedModel`: the default manager there filters by the current tenant, and an
article written for everyone would come back empty for everyone. What a screen does
is the same whichever company is looking at it.

**Content is seeded from code, not typed into a database.** An article that lives in
a `seed_help_*` command is reviewed in the pull request like any other change, ships
with the deployment, can be put back into a fresh installation and survives a restore.
Whatever is edited by hand later sits on top of that, it is not the original. This is
also how the other product does it, and the reason is written in its authoring guide.

There is deliberately less here than in a full help centre: no media table, no
guided tours and no analytics in this first version. They are additions, not
foundations, and leaving them out keeps the first version something a person can read
in one sitting.
"""

from __future__ import annotations

from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

#: `clocking.general`, `admin.installation`. Same shape as the other product's help,
#: on purpose: the two corpora get read side by side and a different convention would
#: be one more thing to remember. Django's `SlugField` rejects the dot, so it is a
#: `CharField` with the validator spelled out.
SLUG = RegexValidator(
    r"^[a-z0-9]+(?:[.\-][a-z0-9]+)*$",
    _("Use lowercase words separated by dots or hyphens, like «clocking.general»."),
)

#: The languages the interface is translated into. Kept here and not imported from
#: settings so that adding a language to the product does not silently orphan help
#: content: somebody has to come here and write the articles.
LANGUAGE_CHOICES = [("es", "Español"), ("en", "English"), ("ca", "Català"), ("gl", "Galego")]


class HelpSection(models.Model):
    """A group of articles, such as «Clocking in» or «Administration»."""

    slug = models.CharField(_("slug"), max_length=50, validators=[SLUG])
    language = models.CharField(_("language"), max_length=2, choices=LANGUAGE_CHOICES)
    title = models.CharField(_("title"), max_length=120)
    icon = models.CharField(_("icon"), max_length=50, blank=True)
    order = models.PositiveIntegerField(_("order"), default=0)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("help section")
        verbose_name_plural = _("help sections")
        ordering = ["order", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "language"], name="unique_help_section_per_language"
            )
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.language})"


class HelpArticle(models.Model):
    """One page of help, in one language."""

    slug = models.CharField(_("slug"), max_length=80, validators=[SLUG])
    language = models.CharField(_("language"), max_length=2, choices=LANGUAGE_CHOICES)
    section = models.ForeignKey(
        HelpSection,
        on_delete=models.CASCADE,
        related_name="articles",
        verbose_name=_("section"),
    )
    title = models.CharField(_("title"), max_length=160)
    summary = models.TextField(_("summary"), blank=True)
    is_published = models.BooleanField(_("published"), default=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("help article")
        verbose_name_plural = _("help articles")
        ordering = ["title"]
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "language"], name="unique_help_article_per_language"
            )
        ]

    def __str__(self) -> str:
        return f"{self.slug} ({self.language})"

    @property
    def is_visible(self) -> bool:
        """Published **and** in an active section.

        Both, because an article hanging off a switched-off section is invisible and
        says nothing about why. In the other product that cost an afternoon: the
        article existed, the `?` button asked for it, and the screen answered
        «article not found».
        """
        return self.is_published and self.section.is_active


class HelpBlock(models.Model):
    """A piece of an article: a paragraph, a heading, a list, a callout.

    Blocks rather than a blob of HTML so the client decides how each piece looks, and
    so an article cannot carry markup that the screen did not expect.
    """

    class Kind(models.TextChoices):
        PARAGRAPH = "paragraph", _("Paragraph")
        HEADING = "heading", _("Heading")
        LIST = "list", _("List")
        CALLOUT = "callout", _("Callout")

    article = models.ForeignKey(
        HelpArticle, on_delete=models.CASCADE, related_name="blocks", verbose_name=_("article")
    )
    order = models.PositiveIntegerField(_("order"), default=0)
    kind = models.CharField(_("kind"), max_length=20, choices=Kind.choices)
    #: Its shape depends on the kind: `{"text": …}`, `{"text": …, "level": 3}`,
    #: `{"items": [...], "ordered": false}`, `{"text": …, "variant": "info"}`.
    data = models.JSONField(_("content"), default=dict)

    class Meta:
        verbose_name = _("help block")
        verbose_name_plural = _("help blocks")
        ordering = ["order"]

    def __str__(self) -> str:
        return f"{self.article.slug}#{self.order} {self.kind}"
