import math
import os
import random
from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from faker import Faker

from accounts.models import ProfileSkill, StudentProfile
from jobs.models import Company, Fair, JobPosting, Shift, Tag
from studies.curriculum import CURRICULUM
from studies.models import Course, StudyProgram

SEED = 42
NUM_COMPANIES = 20
NUM_POSTINGS = 200

FAIRS = [
    ("Jobmesse Potsdam 2027", date(2027, 3, 11), "Potsdam"),
    ("Karrieretag Berlin", date(2027, 4, 22), "Berlin"),
    ("Campus Recruiting Day", date(2027, 5, 18), "Potsdam"),
    ("Werkstudierenden-Forum Hamburg", date(2027, 6, 9), "Hamburg"),
    ("Talente-Treff Leipzig", date(2027, 10, 14), "Leipzig"),
]

INDUSTRIES = ["Bank", "Tech", "Beratung", "Gastro", "Handel", "Logistik", "Medien", "Gesundheit"]

TAGS = [
    "Python", "Excel", "SQL", "JavaScript", "Englisch", "Social Media",
    "Informatik", "BWL", "Wirtschaftsinformatik", "Jura", "Design",
    "Psychologie", "Maschinenbau", "Kommunikation", "Teamfähigkeit",
]

# Wertebereiche je Stellenart: Stunden pro Woche, Stundenlohn in Euro, Titel
KINDS = {
    JobPosting.Kind.WORKING_STUDENT: {
        "hours": (10, 20),
        "wage": (15, 22),
        "titles": [
            "Werkstudent*in Data Analytics", "Werkstudent*in Marketing",
            "Werkstudent*in Softwareentwicklung", "Werkstudent*in Controlling",
            "Werkstudent*in HR", "Werkstudent*in IT-Support",
            "Werkstudent*in Vertrieb", "Werkstudent*in Projektmanagement",
        ],
    },
    JobPosting.Kind.SHORT_JOB: {
        "hours": (3, 12),
        "wage": (13, 17),  # wird auf MIN_WAGE angehoben, siehe unten
        "titles": [
            "Aushilfe Inventur", "Servicekraft Messecatering", "Promoter*in",
            "Aushilfe Lager", "Event-Helfer*in", "Kassenaushilfe",
            "Umfrage-Interviewer*in", "Flyer-Verteilung",
        ],
    },
}

# Kein Seed-Lohn liegt darunter (Mindestlohn 2026: 13,90 €).
MIN_WAGE = Decimal("14.00")

# Diese Jobs gehen nur vor Ort, alle anderen können auch hybrid oder remote sein.
ONSITE_ONLY_TITLES = {
    "Aushilfe Inventur", "Servicekraft Messecatering", "Aushilfe Lager",
    "Event-Helfer*in", "Kassenaushilfe", "Flyer-Verteilung", "Promoter*in",
}

# Fahrzeiten der Firmen aus den Beispielen in docs/design.md, alle anderen zufällig 12–40 min.
DESIGN_EXAMPLE_COMMUTES = {
    "Weihmann GbR": 18,
    "Bauer": 12,
    "Holsten Förster AG & Co. OHG": 35,
}

# Schichten der Stellen mit festen Zeiten: höchstens 4 h pro Schicht, meist nachmittags.
MAX_SHIFT_MINUTES = 4 * 60
# Die Beispielstelle aus docs/design.md bekommt genau die Zeiten aus dem Design-Canvas.
DESIGN_EXAMPLE_SHIFTS = {
    ("Promoter*in", "Weihmann GbR", 7): [(1, time(15, 0), time(18, 30)), (2, time(16, 30), time(20, 0))],
}

# Orte für Stellen vor Ort und hybrid (#20): Berliner Kieze und Umland, Koordinaten
# fest eingetragen (Ortsmitte, auf ~0,01° genau), Adressen erfunden, PLZ passend zum Ort.
LOCATIONS = [
    ("Alexanderstraße 7, 10178 Berlin", "52.5219", "13.4132"),
    ("Friedrichstraße 120, 10117 Berlin", "52.5170", "13.3889"),
    ("Kastanienallee 32, 10435 Berlin", "52.5389", "13.4100"),
    ("Schönhauser Allee 80, 10439 Berlin", "52.5480", "13.4130"),
    ("Oranienstraße 45, 10999 Berlin", "52.5010", "13.4190"),
    ("Mehringdamm 61, 10961 Berlin", "52.4930", "13.3880"),
    ("Warschauer Straße 33, 10243 Berlin", "52.5100", "13.4500"),
    ("Sonnenallee 102, 12045 Berlin", "52.4810", "13.4350"),
    ("Karl-Marx-Straße 150, 12043 Berlin", "52.4760", "13.4390"),
    ("Kantstraße 58, 10627 Berlin", "52.5060", "13.3060"),
    ("Kurfürstendamm 190, 10707 Berlin", "52.5010", "13.3150"),
    ("Hauptstraße 12, 10827 Berlin", "52.4860", "13.3550"),
    ("Schloßstraße 30, 12163 Berlin", "52.4580", "13.3220"),
    ("Turmstraße 21, 10559 Berlin", "52.5260", "13.3420"),
    ("Müllerstraße 140, 13353 Berlin", "52.5470", "13.3540"),
    ("Altstädter Ring 5, 13597 Berlin", "52.5370", "13.2040"),
    ("Berliner Straße 90, 13507 Berlin", "52.5890", "13.2840"),
    ("Breite Straße 18, 13187 Berlin", "52.5690", "13.4040"),
    ("Frankfurter Allee 210, 10365 Berlin", "52.5150", "13.4850"),
    ("Marzahner Promenade 9, 12679 Berlin", "52.5450", "13.5650"),
    ("Bahnhofstraße 40, 12555 Berlin", "52.4580", "13.5760"),
    ("Rudower Straße 65, 12524 Berlin", "52.4330", "13.5300"),
    ("Brandenburgische Straße 20, 14467 Potsdam", "52.3990", "13.0600"),
    ("August-Bebel-Straße 88, 14482 Potsdam", "52.3940", "13.1300"),
    ("Potsdamer Straße 14, 14513 Teltow", "52.4020", "13.2700"),
    ("Breitscheidstraße 23, 16321 Bernau bei Berlin", "52.6790", "13.5870"),
    ("Bahnhofstraße 6, 15711 Königs Wusterhausen", "52.2970", "13.6310"),
    ("Berliner Straße 44, 16515 Oranienburg", "52.7540", "13.2370"),
    ("Spandauer Straße 120, 14612 Falkensee", "52.5600", "13.0920"),
    ("Rathausstraße 3, 15732 Schönefeld", "52.3900", "13.5100"),
]
# Höchstens so weit (in Grad) liegt eine Stelle neben dem Ortspunkt, damit nicht alle übereinander liegen.
LOCATION_JITTER = 0.01


def random_wage(low, high):
    """Zufälliger Stundenlohn, auf 0,50 € genau."""
    return Decimal(random.randint(low * 2, high * 2)) / 2


def make_shifts(posting, rng):
    """Schichten, die zusammen genau hours_per_week ergeben, an verschiedenen Wochentagen."""
    key = (posting.title, posting.company.name, posting.hours_per_week)
    if key in DESIGN_EXAMPLE_SHIFTS:
        return DESIGN_EXAMPLE_SHIFTS[key]

    total = posting.hours_per_week * 60
    count = math.ceil(total / MAX_SHIFT_MINUTES)
    # Gleichmäßig auf halbe Stunden verteilen, der Rest landet in der letzten Schicht.
    length = round(total / count / 30) * 30
    lengths = [length] * (count - 1) + [total - length * (count - 1)]

    shifts = []
    for weekday, minutes in zip(sorted(rng.sample(range(5), count)), lengths):
        # Beginn zwischen 13:00 und so spät, dass die Schicht bis 20:00 endet.
        latest_start = 20 * 60 - minutes
        start = rng.randrange(13 * 60, latest_start + 1, 30)
        end = start + minutes
        shifts.append((weekday, time(start // 60, start % 60), time(end // 60, end % 60)))
    return shifts


# Skills aus dem Lehrplan, die manche Stellen zusätzlich abfragen (je 1–2 davon).
CURRICULUM_REQUIREMENTS = {
    "Werkstudent*in Softwareentwicklung": ["C-Grundlagen", "Memory Management", "Git", "Java", "SQL"],
    "Werkstudent*in Data Analytics": ["SQL", "Statistik"],
    "Werkstudent*in IT-Support": ["Linux", "Netzwerke"],
}


def create_curriculum():
    """Studiengänge und Module aus studies/curriculum.py, fehlende Tags werden angelegt.

    Studiengänge und Module werden aktualisiert statt gelöscht, damit Profile ihre
    Auswahl behalten.
    """
    for name, abbreviation, university, standard_semesters, courses in CURRICULUM:
        program, _ = StudyProgram.objects.update_or_create(
            university=university,
            abbreviation=abbreviation,
            defaults={"name": name, "standard_semesters": standard_semesters},
        )
        for semester, short_name, course_name, skills in courses:
            course, _ = Course.objects.update_or_create(
                program=program,
                name=course_name,
                defaults={"short_name": short_name, "semester": semester},
            )
            course.skills.set([Tag.objects.get_or_create(name=skill)[0] for skill in skills])


DEMO_EMAIL = "mia@student.hpi.uni-potsdam.de"


def create_demo_student(password):
    """Demo-Studentin Mia aus docs/design.md, Login mit DEMO_EMAIL und DEMO_PASSWORD."""
    user, _ = User.objects.get_or_create(username=DEMO_EMAIL)
    user.email = DEMO_EMAIL
    user.first_name = "Mia"
    user.set_password(password)
    user.save()
    itse = StudyProgram.objects.get(university="HPI", abbreviation="ITSE")
    profile, _ = StudentProfile.objects.update_or_create(
        user=user,
        # Lebenslauf gewählt, aber noch nichts übernommen: In der Demo kann man „Übernehmen“ ausprobieren (#50).
        defaults={
            "study_program": itse,
            "semester": 1,
            "home_town": "Potsdam",
            "cv_sample": StudentProfile.CvSample.MIA,
        },
    )
    profile.skills.set(
        Tag.objects.filter(name__in=["Python", "Englisch", "Informatik"]),
        through_defaults={"source": ProfileSkill.Source.PROFILE},
    )
    profile.courses.set(itse.courses.filter(short_name__in=["PT1", "MA1"]))


class Command(BaseCommand):
    help = "Füllt die Datenbank mit reproduzierbaren Beispieldaten (Messen, Firmen, Tags, Stellen, Lehrpläne)."

    @transaction.atomic
    def handle(self, *args, **options):
        demo_password = os.environ.get("DEMO_PASSWORD")
        if not demo_password:
            raise CommandError("DEMO_PASSWORD fehlt in .env (Vorlage: .env.example).")

        # Immer gleiche Zufallszahlen, damit alle im Team dieselben Daten sehen.
        random.seed(SEED)
        Faker.seed(SEED)
        fake = Faker("de_DE")

        # Alte Daten löschen (User bleiben unberührt).
        JobPosting.objects.all().delete()
        Company.objects.all().delete()
        Fair.objects.all().delete()
        Tag.objects.all().delete()

        fairs = [Fair.objects.create(name=n, date=d, location=loc) for n, d, loc in FAIRS]
        tags = [Tag.objects.create(name=name) for name in TAGS]

        # Die ersten Firmen decken jede Branche ab, der Rest wird zufällig gewählt.
        industries = INDUSTRIES + random.choices(INDUSTRIES, k=NUM_COMPANIES - len(INDUSTRIES))
        companies = []
        for industry in industries:
            company = Company.objects.create(name=fake.company(), industry=industry)
            company.fairs.set(random.sample(fairs, random.randint(0, 2)))
            companies.append(company)

        for _ in range(NUM_POSTINGS):
            kind = random.choice(list(KINDS))
            rules = KINDS[kind]
            # Reihenfolge der Zufallsaufrufe nicht ändern: docs/design.md und die
            # Issues verweisen auf konkrete Seed-Stellen (z. B. Promoter*in, Weihmann GbR).
            company = random.choice(companies)
            title = random.choice(rules["titles"])
            description = fake.paragraph(nb_sentences=3)
            workplace = random.choice(JobPosting.Workplace.values)
            if title in ONSITE_ONLY_TITLES:
                workplace = JobPosting.Workplace.ONSITE
            schedule = random.choice(JobPosting.Schedule.values)
            hourly_wage = max(random_wage(*rules["wage"]), MIN_WAGE)
            posting = JobPosting.objects.create(
                company=company,
                title=title,
                description=description,
                kind=kind,
                workplace=workplace,
                schedule=schedule,
                hourly_wage=hourly_wage,
                hours_per_week=random.randint(*rules["hours"]),
            )
            posting.tags.set(random.sample(tags, random.randint(0, 3)))

        # Fahrzeiten und Schichten haben je einen eigenen Zufallsgenerator,
        # damit neue Daten die Stellen oben nicht verändern.
        commute_random = random.Random(SEED)
        for company in Company.objects.order_by("id"):
            company.commute_minutes = DESIGN_EXAMPLE_COMMUTES.get(
                company.name, commute_random.randint(12, 40)
            )
            company.save()

        shift_random = random.Random(SEED)
        for posting in JobPosting.objects.filter(schedule=JobPosting.Schedule.FIXED).order_by("id"):
            for weekday, start, end in make_shifts(posting, shift_random):
                Shift.objects.create(posting=posting, weekday=weekday, start=start, end=end)

        # Orte (#20) mit eigenem Zufallsgenerator, Remote-Stellen bleiben ohne Ort.
        location_random = random.Random(SEED + 20)
        onsite_postings = JobPosting.objects.exclude(
            workplace=JobPosting.Workplace.REMOTE
        ).order_by("id")
        for posting in onsite_postings:
            address, latitude, longitude = location_random.choice(LOCATIONS)
            posting.address = address
            posting.latitude = round(
                Decimal(latitude) + Decimal(location_random.uniform(-LOCATION_JITTER, LOCATION_JITTER)), 6
            )
            posting.longitude = round(
                Decimal(longitude) + Decimal(location_random.uniform(-LOCATION_JITTER, LOCATION_JITTER)), 6
            )
            posting.save()

        # Lehrpläne (#30) nach den Stellen, mit eigenem Zufallsgenerator für die Anforderungen.
        create_curriculum()
        requirement_random = random.Random(SEED)
        postings = JobPosting.objects.filter(title__in=CURRICULUM_REQUIREMENTS).order_by("id")
        for posting in postings:
            options = CURRICULUM_REQUIREMENTS[posting.title]
            names = requirement_random.sample(options, requirement_random.randint(1, 2))
            posting.tags.add(*Tag.objects.filter(name__in=names))

        create_demo_student(demo_password)

        self.stdout.write(self.style.SUCCESS(
            f"{NUM_POSTINGS} Stellen von {NUM_COMPANIES} Firmen angelegt "
            f"({len(fairs)} Messen, {Tag.objects.count()} Tags, "
            f"{StudyProgram.objects.count()} Studiengänge mit {Course.objects.count()} Modulen), "
            f"Demo-Login: {DEMO_EMAIL}."
        ))
