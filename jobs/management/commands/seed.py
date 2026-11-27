import math
import os
import random
from datetime import date, time
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from faker import Faker

from accounts.models import ProfileSkill, StudentProfile
from companies.models import CompanyMember
from jobs.models import Company, Fair, JobPosting, Shift, Tag
from studies.curriculum import CURRICULUM
from studies.models import Course, StudyProgram
from timetable.models import LectureSlot

SEED = 42
NUM_COMPANIES = 20
NUM_POSTINGS = 200
NUM_STUDENTS = 500

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
    Auswahl behalten. Ein Modul wird wie bei import_lehrplan über sein Kürzel gefunden.
    Hat der Import es umbenannt (z. B. „Programmiertechnik 1“), bleibt der Name aus dem
    Katalog. Ältere Datenbanken kennen manche Module noch unter einem alten Kürzel
    (z. B. MOD1 statt MO), die findet der Seed über den Namen.
    """
    for name, abbreviation, university, standard_semesters, courses in CURRICULUM:
        program, _ = StudyProgram.objects.update_or_create(
            university=university,
            abbreviation=abbreviation,
            defaults={"name": name, "standard_semesters": standard_semesters},
        )
        for semester, short_name, course_name, skills in courses:
            course = (
                Course.objects.filter(program=program, short_name=short_name).first()
                or Course.objects.filter(program=program, name=course_name).first()
                or Course(program=program, name=course_name)
            )
            course.short_name = short_name
            course.semester = semester
            course.save()
            course.skills.set([Tag.objects.get_or_create(name=skill)[0] for skill in skills])


DEMO_EMAIL = "mia@student.hpi.uni-potsdam.de"
# Demo-Firmenkonto (#66) für die Firma aus docs/design.md, Login unter /firma/anmelden/.
DEMO_COMPANY_EMAIL = "weihmann@firma.elfjobs.local"
DEMO_COMPANY = "Weihmann GbR"


def create_demo_company_account(password):
    """Firmenkonto für Weihmann GbR mit DEMO_PASSWORD. Die Firma wird bei jedem Seed neu angelegt,
    das Konto bleibt und wird neu verknüpft."""
    user, _ = User.objects.get_or_create(username=DEMO_COMPANY_EMAIL)
    user.email = DEMO_COMPANY_EMAIL
    user.first_name = "Weihmann"
    user.set_password(password)
    user.save()
    CompanyMember.objects.update_or_create(user=user, defaults={"company": Company.objects.get(name=DEMO_COMPANY)})


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
    itse = StudyProgram.objects.get(university="HPI", abbreviation="ITSE")
    profile, _ = StudentProfile.objects.update_or_create(
        user=user,
        # Lebenslauf gewählt, aber noch nichts übernommen: In der Demo kann man „Übernehmen“ ausprobieren (#50).
        defaults={
            "study_program": itse,
            "semester": 1,
            "home_town": "Potsdam",
            # Feste Koordinaten (Potsdam Hbf), kein Geocoding im Seed (#53).
            "home_latitude": Decimal("52.392000"),
            "home_longitude": Decimal("13.067000"),
            "cv_sample": StudentProfile.CvSample.MIA,
        },
    )
    profile.skills.set(
        Tag.objects.filter(name__in=["Python", "Englisch", "Informatik"]),
        through_defaults={"source": ProfileSkill.Source.PROFILE},
    )
    profile.courses.set(itse.courses.filter(short_name__in=["PT1", "MA1"]))
    # Mia geht zur Jobmesse Potsdam (#33), damit „Meine Messen“ im Profil etwas zeigt.
    user.fairs.set(Fair.objects.filter(name="Jobmesse Potsdam 2027"))

    # Mias Stundenplan aus docs/design.md, bei jedem Seed neu.
    profile.lectures.all().delete()
    for weekday, start, end, title in DEMO_LECTURES:
        LectureSlot.objects.create(profile=profile, weekday=weekday, start=start, end=end, title=title)

# Demo-Studierende (#79): studi-001@… bis studi-500@…, alle mit DEMO_PASSWORD.
STUDENT_EMAIL = "studi-{number:03d}@student.hpi.uni-potsdam.de"
# Gewicht je Studiengang in der Reihenfolge von CURRICULUM: ITSE etwa 40 %, der Rest verteilt sich.
PROGRAM_WEIGHTS = [40, 15, 15, 15, 15]
HOME_TOWNS = [
    "Potsdam", "Potsdam", "Potsdam", "Berlin-Kreuzberg", "Berlin-Neukölln",
    "Berlin-Friedrichshain", "Berlin-Prenzlauer Berg", "Berlin-Mitte", "Berlin-Charlottenburg",
    "Teltow", "Falkensee",
]
# Zeitraster wie am HPI: fünf Blöcke pro Tag, Mo–Fr.
TIME_GRID = [
    (time(9, 15), time(10, 45)),
    (time(11, 0), time(12, 30)),
    (time(13, 30), time(15, 0)),
    (time(15, 15), time(16, 45)),
    (time(17, 0), time(18, 30)),
]
GRID_CELLS = [(weekday, block) for weekday in range(5) for block in range(len(TIME_GRID))]
SLOTS_PER_COURSE = 2  # Vorlesung + Übung
ELECTIVE_TITLES = ["Wahlpflichtmodul", "Seminar", "Sprachkurs Englisch", "Projektseminar"]
MIN_LECTURES, MAX_LECTURES = 4, 9
TAKES_COURSE_CHANCE = 0.9
# Nach `import_lehrplan` hat ein Semester viele Wahlpflichtmodule. Mehr als so viele
# belegt niemand, sonst wäre die Woche voll.
MAX_COURSES_PER_SEMESTER = 5


def assign_course_cells(courses, rng):
    """Feste Zeitraster-Felder je Modul: gleich für alle, ohne Überschneidung im selben Studiengang-Semester."""
    cells_by_course = {}
    free_by_group = {}
    for course in courses:
        group = (course.program_id, course.semester)
        if group not in free_by_group:
            free_by_group[group] = rng.sample(GRID_CELLS, len(GRID_CELLS))
        free = free_by_group[group]
        cells_by_course[course.id] = [free.pop() for _ in range(min(SLOTS_PER_COURSE, len(free)))]
    return cells_by_course


def make_student_lectures(profile_courses, cells_by_course, rng):
    """Termine einer Person als Liste von (Wochentag, Block, Titel): Module + Wahlmodule, ohne Überschneidung."""
    lectures = []
    taken = set()
    for course in profile_courses:
        if rng.random() < TAKES_COURSE_CHANCE:
            for cell in cells_by_course[course.id]:
                lectures.append((*cell, course.name))
                taken.add(cell)
    free = [cell for cell in GRID_CELLS if cell not in taken]
    rng.shuffle(free)
    wanted = max(rng.randint(MIN_LECTURES, MAX_LECTURES), 1)
    while len(lectures) < wanted and free:
        lectures.append((*free.pop(), rng.choice(ELECTIVE_TITLES)))
    return lectures


def create_demo_students(password):
    """500 Demo-Studierende mit Profil, Modulen, Skills und Stundenplan (#79).

    Eigener Zufallsgenerator und eigener Faker, damit Stellen und Firmen gleich bleiben.
    Ein Passwort-Hash für alle, weil 500-mal Hashen zu langsam wäre. Alles per bulk_create.
    """
    rng = random.Random(SEED + 79)
    fake = Faker("de_DE")
    fake.seed_instance(SEED + 79)

    # Alte Demo-Studierende löschen, Mia und alle anderen Konten bleiben.
    User.objects.filter(
        username__startswith="studi-", username__endswith="@student.hpi.uni-potsdam.de"
    ).delete()

    programs = [
        StudyProgram.objects.get(university=university, abbreviation=abbreviation)
        for _, abbreviation, university, _, _ in CURRICULUM
    ]
    courses = list(Course.objects.filter(program__in=programs).order_by("program_id", "semester", "id"))
    courses_by_program = {program.id: [] for program in programs}
    for course in courses:
        courses_by_program[course.program_id].append(course)
    # Feste Termine nur für Module im Lehrplan-Semester; jedes Modul bekommt sie einmal.
    cells_by_course = assign_course_cells(courses, rng)
    tags = list(Tag.objects.filter(name__in=TAGS).order_by("name"))

    password_hash = make_password(password)
    users, details = [], []
    for number in range(1, NUM_STUDENTS + 1):
        email = STUDENT_EMAIL.format(number=number)
        users.append(User(
            username=email, email=email, password=password_hash,
            first_name=fake.first_name(), last_name=fake.last_name(),
        ))
        details.append((rng.choices(programs, weights=PROGRAM_WEIGHTS)[0], rng.randint(1, 6)))
    User.objects.bulk_create(users)

    profiles = [
        StudentProfile(user=user, study_program=program, semester=semester, home_town=rng.choice(HOME_TOWNS))
        for user, (program, semester) in zip(users, details)
    ]
    StudentProfile.objects.bulk_create(profiles)

    through = StudentProfile.courses.through
    course_links, skills, lecture_slots = [], [], []
    for profile, (program, semester) in zip(profiles, details):
        done = [c for c in courses_by_program[program.id] if c.semester <= semester]
        course_links += [through(studentprofile_id=profile.id, course_id=c.id) for c in done]
        for tag in rng.sample(tags, rng.randint(0, 3)):
            skills.append(ProfileSkill(profile=profile, tag=tag, source=ProfileSkill.Source.PROFILE))
        current = [c for c in done if c.semester == semester]
        current = rng.sample(current, min(len(current), MAX_COURSES_PER_SEMESTER))
        for weekday, block, title in make_student_lectures(current, cells_by_course, rng):
            start, end = TIME_GRID[block]
            lecture_slots.append(LectureSlot(profile=profile, weekday=weekday, start=start, end=end, title=title))
    through.objects.bulk_create(course_links)
    ProfileSkill.objects.bulk_create(skills)
    LectureSlot.objects.bulk_create(lecture_slots)


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
        create_demo_students(demo_password)
        create_demo_company_account(demo_password)

        self.stdout.write(self.style.SUCCESS(
            f"{NUM_POSTINGS} Stellen von {NUM_COMPANIES} Firmen angelegt "
            f"({len(fairs)} Messen, {Tag.objects.count()} Tags, "
            f"{StudyProgram.objects.count()} Studiengänge mit {Course.objects.count()} Modulen), "
            f"{NUM_STUDENTS} Demo-Studierende, Demo-Login: {DEMO_EMAIL}, Firma: {DEMO_COMPANY_EMAIL}."
        ))
