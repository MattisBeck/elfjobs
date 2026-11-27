"""Skills aus dem Lebenslauf (#50): Text aus dem PDF lesen und mit den vorhandenen Tags abgleichen.

Keine KI und kein OCR: Ein Skill wird gefunden, wenn sein Name (oder ein Synonym) als
ganzes Wort im Text steht, Groß- und Kleinschreibung egal. Neue Tags entstehen dabei nie.
"""

import re

from django.conf import settings
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from jobs.models import Tag
from studies.skills import skill_sources

from .models import ProfileSkill

SAMPLE_CV_FOLDER = settings.BASE_DIR / "accounts" / "sample_cvs"

# Schreibweise im Lebenslauf → Name des Tags. Nur Tags, die es schon gibt, zählen.
SYNONYMS = {
    "MS Excel": "Excel",
    "Microsoft Excel": "Excel",
    "Python 3": "Python",
    "Python3": "Python",
    "English": "Englisch",
    "PostgreSQL": "SQL",
    "MySQL": "SQL",
    "PowerPoint": "Präsentieren",
    "Buchführung": "Buchhaltung",
    "Instagram": "Social Media",
    "TikTok": "Social Media",
    "Betriebswirtschaftslehre": "BWL",
    "im Team": "Teamfähigkeit",
}


def cv_path(profile):
    """Pfad zum Lebenslauf oder None: der hochgeladene (#38), sonst der gewählte Beispiel-Lebenslauf."""
    if profile.cv_file:
        return profile.cv_file.path
    if not profile.cv_sample:
        return None
    return SAMPLE_CV_FOLDER / f"{profile.cv_sample}.pdf"


def read_pdf_text(path):
    """Der ganze Text des PDFs. Ein PDF ohne Text (z. B. eingescannt) ergibt einen leeren Text."""
    try:
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except (OSError, PdfReadError):
        return ""


def contains_word(text, word):
    """Steht word als ganzes Wort im Text? „Informatik“ steckt z. B. nicht in „Wirtschaftsinformatik“."""
    pattern = r"(?<!\w)" + re.escape(word) + r"(?!\w)"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def find_skills(text):
    """Alle vorhandenen Tags, die im Text vorkommen, nach Name sortiert."""
    names = set()
    for tag_name in Tag.objects.values_list("name", flat=True):
        if contains_word(text, tag_name):
            names.add(tag_name)
    for synonym, tag_name in SYNONYMS.items():
        if contains_word(text, synonym):
            names.add(tag_name)
    return list(Tag.objects.filter(name__in=names).order_by("name"))


def cv_suggestions(profile):
    """Skills aus dem gewählten Lebenslauf, aufgeteilt in neue Vorschläge und schon vorhandene.

    Ergebnis: (neu, vorhanden). neu ist eine Liste von Tags, vorhanden eine Liste von
    (Tag, Quelle), z. B. (Python, "aus deinem Profil"). Die Vorschläge werden bei jedem
    Aufruf aus dem PDF berechnet, gespeichert wird erst, was die Studentin übernimmt.
    """
    path = cv_path(profile)
    if path is None:
        return [], []
    sources = skill_sources(profile)
    new, existing = [], []
    for tag in find_skills(read_pdf_text(path)):
        if tag.id in sources:
            existing.append((tag, sources[tag.id]))
        else:
            new.append(tag)
    return new, existing


def accept_cv_skills(profile, tag_ids):
    """Übernimmt die bestätigten Vorschläge als Skills mit der Quelle „aus deinem Lebenslauf“.

    Nur Tags, die gerade wirklich vorgeschlagen werden, zählen. Gibt die Anzahl zurück.
    """
    new, _ = cv_suggestions(profile)
    accepted = [tag for tag in new if str(tag.id) in tag_ids]
    for tag in accepted:
        ProfileSkill.objects.get_or_create(profile=profile, tag=tag, defaults={"source": ProfileSkill.Source.CV})
    return len(accepted)
