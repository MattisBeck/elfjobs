"""Qualifikation pro Stelle: Welche Anforderungen bringt die Studentin laut Lehrplan mit?

Regel aus docs/design.md „Qualifikation aus dem Lehrplan“:
- gelernt: Skill aus einem belegten Modul oder selbst im Profil (studies/skills.py)
- kommt noch: Skill aus einem Modul des eigenen Studiengangs in einem späteren Semester
- nicht im Studium: alles andere
"""

from .models import Course
from .skills import skill_sources

LEARNED = "gelernt"
UPCOMING = "kommt_noch"
NOT_IN_STUDIES = "nicht_im_studium"


def skill_lookup(profile):
    """Alle Skills, die das Profil hat oder noch bekommt, als {Tag-id: (Einordnung, Text)}.

    Zum Beispiel {7: ("gelernt", "aus PT1"), 12: ("kommt_noch", "ab 3. Semester")}.
    Einmal pro Request laden und dann für beliebig viele Stellen mit classify() nutzen.
    """
    lookup = {tag_id: (LEARNED, source) for tag_id, source in skill_sources(profile).items()}

    # Ohne Studiengang oder Semester wissen wir nicht, was noch kommt.
    if profile.study_program_id and profile.semester:
        later_courses = (
            Course.objects.filter(program_id=profile.study_program_id, semester__gt=profile.semester)
            .prefetch_related("skills")
            .order_by("semester", "name")
        )
        for course in later_courses:
            for tag in course.skills.all():
                # setdefault: Gelerntes bleibt gelernt, sonst gewinnt das früheste Semester.
                lookup.setdefault(tag.id, (UPCOMING, f"ab {course.semester}. Semester"))
    return lookup


def classify(lookup, tags):
    """Ordnet jeden Tag einer Stelle ein: [{"tag", "status", "text"}, ...] in derselben Reihenfolge."""
    requirements = []
    for tag in tags:
        status, text = lookup.get(tag.id, (NOT_IN_STUDIES, ""))
        requirements.append({"tag": tag, "status": status, "text": text})
    return requirements


def summary(requirements):
    """Hinweis für die Stellenliste, z. B. „2 von 3 Anforderungen aus dem Studium“.

    Gezählt wird nur „gelernt“ (dazu gehören auch eigene Skills aus dem Profil).
    Ohne Anforderungen gibt es keinen Hinweis.
    """
    if not requirements:
        return ""
    learned = sum(1 for requirement in requirements if requirement["status"] == LEARNED)
    noun = "Anforderung" if len(requirements) == 1 else "Anforderungen"
    return f"{learned} von {len(requirements)} {noun} aus dem Studium"


def verdict(requirements):
    """Ermutigendes Urteil für eine Stelle (#86, Wording #98), gegen die Angst vorm Bewerben.

    - keine Anforderungen → „✓ Du bist qualifiziert“, „Vorkenntnisse braucht es hier nicht.“
    - alles gelernt → „✓ Du bist qualifiziert“, „Du bringst mit: Git aus PT1.“
    - der Rest kommt noch im eigenen Studium → „✓ Passt zu deinem Studium“,
      „Du bringst mit: Git aus PT1. Kommt noch im Studium: SQL ab 3. Semester.“
    - sonst None, dann bleibt es beim Hinweis aus summary()

    Gibt {"level", "label", "detail"} zurück; level ist "kannst" oder "bald" (für die CSS-Klasse).
    Die Zeile „detail“ steht nur im Stellendetail.
    """
    if not requirements:
        return {"level": "kannst", "label": "✓ Du bist qualifiziert", "detail": "Vorkenntnisse braucht es hier nicht."}
    if any(requirement["status"] == NOT_IN_STUDIES for requirement in requirements):
        return None
    learned = [r for r in requirements if r["status"] == LEARNED]
    upcoming = [r for r in requirements if r["status"] == UPCOMING]
    sentences = []
    if learned:
        sentences.append("Du bringst mit: " + ", ".join(f"{r['tag'].name} {r['text']}" for r in learned) + ".")
    if upcoming:
        sentences.append("Kommt noch im Studium: " + ", ".join(f"{r['tag'].name} {r['text']}" for r in upcoming) + ".")
    detail = " ".join(sentences)
    if not upcoming:
        return {"level": "kannst", "label": "✓ Du bist qualifiziert", "detail": detail}
    return {"level": "bald", "label": "✓ Passt zu deinem Studium", "detail": detail}
