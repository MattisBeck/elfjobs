# Schritt 1 von 3 für #30: neue Felder und ProfileSkill anlegen, alte Felder bleiben noch.
# Schritt 2 (0003) überträgt die Daten, Schritt 3 (0004) entfernt die alten Felder.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('jobs', '0003_company_commute_minutes'),
        ('studies', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProfileSkill',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(choices=[('profil', 'aus deinem Profil'), ('lebenslauf', 'aus deinem Lebenslauf')], default='profil', max_length=20, verbose_name='Quelle')),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='profile_skills', to='accounts.studentprofile', verbose_name='Studi-Profil')),
                ('tag', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='profile_skills', to='jobs.tag', verbose_name='Skill')),
            ],
            options={
                'verbose_name': 'Skill im Profil',
                'verbose_name_plural': 'Skills im Profil',
                'constraints': [models.UniqueConstraint(fields=('profile', 'tag'), name='unique_skill_per_profile')],
            },
        ),
        migrations.RenameField(
            model_name='studentprofile',
            old_name='study_program',
            new_name='study_program_text',
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='study_program',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='students', to='studies.studyprogram', verbose_name='Studiengang'),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='courses',
            field=models.ManyToManyField(blank=True, related_name='students', to='studies.course', verbose_name='Belegte Module'),
        ),
    ]
