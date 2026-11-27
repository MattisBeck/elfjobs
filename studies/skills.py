"""Woher die Skills einer Studentin kommen: aus belegten Modulen oder selbst eingetragen."""


def skill_sources(profile):
    """Alle Skills des Profils als {Tag-id: Quelle}, z. B. {7: "aus PT1", 3: "aus deinem Profil"}.

    Modul-Skills werden nicht gespeichert, sondern aus den belegten Modulen (profile.courses)
    abgeleitet. Steht ein Skill in mehreren Quellen, gewinnt das früheste Modul, danach
    der selbst eingetragene Skill (ProfileSkill).
    """
    sources = {}
    for course in profile.courses.prefetch_related("skills").order_by("semester", "name"):
        for tag in course.skills.all():
            sources.setdefault(tag.id, f"aus {course.label}")
    for profile_skill in profile.profile_skills.all():
        sources.setdefault(profile_skill.tag_id, profile_skill.get_source_display())
    return sources
