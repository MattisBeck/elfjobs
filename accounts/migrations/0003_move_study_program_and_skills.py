# Schritt 2 von 3 für #30: bestehende Daten übertragen.
# - Studiengang (Freitext) -> StudyProgram, wenn Name oder Kürzel bekannt ist, sonst leer.
# - Skills (einfache M2M) -> ProfileSkill mit Quelle "profil".

from django.db import migrations

# Studiengänge, die es zum Zeitpunkt dieser Migration gab (wie im Seed, studies/curriculum.py).
# Bewusst hier kopiert: Migrationen dürfen sich nicht ändern, wenn sich der Seed ändert.
KNOWN_PROGRAMS = [
    ("IT-Systems Engineering", "ITSE", "HPI", 6),
    ("Wirtschaftsinformatik", "WI", "Uni Potsdam", 6),
    ("Betriebswirtschaftslehre", "BWL", "Uni Potsdam", 6),
    ("Psychologie", "Psy", "Uni Potsdam", 6),
    ("Medien- und Kommunikationswissenschaft", "MuK", "Uni Potsdam", 6),
]


def find_program(StudyProgram, text):
    text = text.strip().lower()
    if not text:
        return None
    for program in StudyProgram.objects.all():
        if text in (program.name.lower(), program.abbreviation.lower()):
            return program
    for name, abbreviation, university, standard_semesters in KNOWN_PROGRAMS:
        if text in (name.lower(), abbreviation.lower()):
            program, _ = StudyProgram.objects.get_or_create(
                university=university,
                abbreviation=abbreviation,
                defaults={"name": name, "standard_semesters": standard_semesters},
            )
            return program
    return None


def forwards(apps, schema_editor):
    StudentProfile = apps.get_model("accounts", "StudentProfile")
    ProfileSkill = apps.get_model("accounts", "ProfileSkill")
    StudyProgram = apps.get_model("studies", "StudyProgram")

    for profile in StudentProfile.objects.all():
        profile.study_program = find_program(StudyProgram, profile.study_program_text)
        profile.save(update_fields=["study_program"])
        for tag in profile.skills.all():
            ProfileSkill.objects.get_or_create(profile=profile, tag=tag, defaults={"source": "profil"})


def backwards(apps, schema_editor):
    StudentProfile = apps.get_model("accounts", "StudentProfile")
    ProfileSkill = apps.get_model("accounts", "ProfileSkill")

    for profile in StudentProfile.objects.select_related("study_program"):
        profile.study_program_text = profile.study_program.abbreviation if profile.study_program else ""
        profile.save(update_fields=["study_program_text"])
        profile.skills.set([ps.tag for ps in ProfileSkill.objects.filter(profile=profile)])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_studyprogram_courses_profileskill'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
