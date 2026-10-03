from django.db import models
from django.utils.translation import gettext_lazy as _


class IonManager(models.Manager["Ion"]):
    """Queryset helpers for :class:`Ion`."""

    def cations(self) -> models.QuerySet["Ion"]:
        """Return only cations."""
        return self.get_queryset().filter(kind="cation")

    def anions(self) -> models.QuerySet["Ion"]:
        """Return only anions."""
        return self.get_queryset().filter(kind="anion")


class Ion(models.Model):
    """
    A cation or anion from the qualitative analysis catalog.

    Ions can be defined independently of substances; substances reference them
    via M2M and can be used to deduce ions for reference material.
    """

    class Kind(models.TextChoices):
        CATION = "cation", _("Cation")
        ANION = "anion", _("Anion")

    symbol = models.CharField(max_length=32, help_text=_("Ion symbol, e.g. 'NH4+' or 'SO4^2-'."))
    name = models.CharField(max_length=255, help_text=_("Human readable name, e.g. 'Ammonium'."))
    charge = models.IntegerField(default=0, help_text=_("Ionic charge (e.g. +2, -1, -2, -3)."))
    kind = models.CharField(max_length=8, choices=Kind.choices, help_text=_("Cation or anion."))
    group = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text=_("Systematic group, e.g. 'Group I', 'Group III', or free text."),
    )
    objects = IonManager()

    class Meta:
        verbose_name = _("Ion")
        verbose_name_plural = _("Ions")
        ordering = ["kind", "group", "symbol"]
        constraints = [
            models.UniqueConstraint(fields=["symbol", "kind"], name="unique_symbol_per_kind"),
        ]

    def __str__(self) -> str:
        return f"{self.symbol} ({self.get_kind_display()})"


class SubstanceManager(models.Manager["Substance"]):
    """Queryset helpers for :class:`Substance`."""

    def with_ion(self, ion_id: int) -> models.QuerySet["Substance"]:
        """Return substances containing the given ion."""
        return self.get_queryset().filter(ions__id=ion_id).distinct()


class Substance(models.Model):
    """
    A chemical substance (salt) and the ions it decomposes into.

    Substances are reference material shown to students next to the possible
    ion list. Ions are the source of truth: a substance's ion list is optional
    and editable, and ions may exist without any substance referencing them.
    """

    name = models.CharField(max_length=255, help_text=_("Common name, e.g. 'Sodium chloride'."))
    synonyms = models.JSONField(default=list, blank=True, help_text=_("List of synonyms / alternative names."))
    formula = models.CharField(max_length=128, blank=True, default="", help_text=_("Chemical formula, e.g. 'NaCl'."))
    ions = models.ManyToManyField(
        Ion,
        blank=True,
        related_name="substances",
        help_text=_("Ions this substance provides in aqueous solution."),
    )
    pubchem_id = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text=_("PubChem CID, if known."),
    )
    wikipedia_link = models.URLField(blank=True, default="", help_text=_("Link to a Wikipedia article, if any."))

    objects = SubstanceManager()

    class Meta:
        verbose_name = _("Substance")
        verbose_name_plural = _("Substances")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def pubchem_url(self) -> str | None:
        """
        URL of this substance's PubChem compound page, or ``None`` if unknown.

        The base URL comes from ``settings.PUBCHEM_BASE_URL`` so every app
        reuses the same base; the PubChem CID is appended to it.
        """
        if not self.pubchem_id:
            return None
        from django.conf import settings

        return f"{settings.PUBCHEM_BASE_URL.rstrip('/')}/{self.pubchem_id}"
