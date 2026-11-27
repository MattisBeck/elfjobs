import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = [("accounts", "0001_initial"), ("studies", "0001_initial"), ("jobs", "0003_company_commute_minutes")]
AFTER = [("accounts", "0004_remove_old_fields")]


def migrate(targets):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


@pytest.mark.django_db(transaction=True)
def test_migration_moves_study_program_and_skills():
    try:
        old_apps = migrate(BEFORE)
        User = old_apps.get_model("auth", "User")
        Tag = old_apps.get_model("jobs", "Tag")
        OldProfile = old_apps.get_model("accounts", "StudentProfile")
        python = Tag.objects.create(name="Python")
        lena = OldProfile.objects.create(user=User.objects.create(username="lena"), study_program="itse")
        lena.skills.add(python)
        OldProfile.objects.create(user=User.objects.create(username="tom"), study_program="Jura")

        new_apps = migrate(AFTER)
        Profile = new_apps.get_model("accounts", "StudentProfile")
        ProfileSkill = new_apps.get_model("accounts", "ProfileSkill")

        lena = Profile.objects.get(user__username="lena")
        assert (lena.study_program.abbreviation, lena.study_program.university) == ("ITSE", "HPI")
        skills = ProfileSkill.objects.filter(profile=lena).values_list("tag__name", "source")
        assert list(skills) == [("Python", "profil")]
        assert Profile.objects.get(user__username="tom").study_program is None
    finally:
        # Wieder auf den neuesten Stand, damit die anderen Tests das aktuelle Schema sehen.
        migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())
