# Schritt 3 von 3 für #30: alte Felder entfernen, Skills laufen jetzt über ProfileSkill.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_move_study_program_and_skills'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='studentprofile',
            name='study_program_text',
        ),
        migrations.RemoveField(
            model_name='studentprofile',
            name='skills',
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='skills',
            field=models.ManyToManyField(blank=True, related_name='students', through='accounts.ProfileSkill', to='jobs.tag', verbose_name='Skills'),
        ),
    ]
