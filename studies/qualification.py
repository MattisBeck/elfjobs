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
