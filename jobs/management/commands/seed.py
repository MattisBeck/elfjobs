import math
import os
import random
from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from faker import Faker

from accounts.models import StudentProfile
from jobs.models import Company, Fair, JobPosting, Shift, Tag
from timetable.models import LectureSlot

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

# Schichten der Stellen mit festen Zeiten: höchstens 4 h pro Schicht, meist nachmittags.
MAX_SHIFT_MINUTES = 4 * 60
# Die Beispielstelle aus docs/design.md bekommt genau die Zeiten aus dem Design-Canvas.
DESIGN_EXAMPLE_SHIFTS = {
    ("Promoter*in", "Weihmann GbR", 7): [(1, time(15, 0), time(18, 30)), (2, time(16, 30), time(20, 0))],
}


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


DEMO_EMAIL = "mia@student.hpi.uni-potsdam.de"


# Wochentag 0–4 (Mo–Fr), Beginn, Ende, Veranstaltung
DEMO_LECTURES = [
    (0, time(9, 15), time(12, 30), "Mathematik I"),
    (0, time(13, 30), time(15, 0), "Programmiertechnik I"),
    (1, time(9, 15), time(10, 45), "Digitale Systeme"),
    (1, time(11, 0), time(12, 30), "Modellierung I"),
    (2, time(9, 15), time(12, 30), "Programmiertechnik I"),
    (3, time(13, 30), time(17, 0), "Übungen Mathe / Digitale Systeme"),
    (4, time(9, 15), time(12, 30), "Wirtschaftliche Grundlagen"),
]


def create_demo_student(password):
    """Demo-Studentin Mia aus docs/design.md, Login mit DEMO_EMAIL und DEMO_PASSWORD."""
    user, _ = User.objects.get_or_create(username=DEMO_EMAIL)
    user.email = DEMO_EMAIL
    user.first_name = "Mia"
    user.set_password(password)
    user.save()
    profile, _ = StudentProfile.objects.update_or_create(
        user=user,
        defaults={"study_program": "ITSE", "semester": 1, "home_town": "Potsdam"},
    )
    profile.skills.set(Tag.objects.filter(name__in=["Python", "Englisch", "Informatik"]))

    # Mias Stundenplan aus docs/design.md, bei jedem Seed neu.
    profile.lectures.all().delete()
    for weekday, start, end, title in DEMO_LECTURES:
        LectureSlot.objects.create(profile=profile, weekday=weekday, start=start, end=end, title=title)


class Command(BaseCommand):
    help = "Füllt die Datenbank mit reproduzierbaren Beispieldaten (Messen, Firmen, Tags, Stellen)."

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

        # Eigener Zufallsgenerator, damit neue Daten die Stellen oben nicht verändern.
        shift_random = random.Random(SEED)
        for posting in JobPosting.objects.filter(schedule=JobPosting.Schedule.FIXED).order_by("id"):
            for weekday, start, end in make_shifts(posting, shift_random):
                Shift.objects.create(posting=posting, weekday=weekday, start=start, end=end)

        create_demo_student(demo_password)

        self.stdout.write(self.style.SUCCESS(
            f"{NUM_POSTINGS} Stellen von {NUM_COMPANIES} Firmen angelegt "
            f"({len(fairs)} Messen, {len(tags)} Tags), Demo-Login: {DEMO_EMAIL}."
        ))
