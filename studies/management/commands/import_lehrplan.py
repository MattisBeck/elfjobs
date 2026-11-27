"""Liest den öffentlichen Modulkatalog eines Studiengangs und legt die Module als Course an.

Bisher gibt es nur ITSE am HPI. Der Modulkatalog liegt in PULS (Uni Potsdam) und wird von
https://hpi.de/studium/it-systems-engineering-bsc/ als „Übersicht aller Module“ verlinkt.
Er nennt Kürzel und Titel jedes Moduls, aber kein Semester. Das Semester kommt deshalb aus
dem Musterstudienverlaufsplan des HPI (siehe SEMESTER_BY_CODE).
"""

import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from jobs.models import Tag
from studies.models import Course, StudyProgram

TIMEOUT_SECONDS = 10

PROGRAMS = {
    "itse": {
        "name": "IT-Systems Engineering",
        "abbreviation": "ITSE",
        "university": "HPI",
        "standard_semesters": 6,
        "url": (
            "https://puls.uni-potsdam.de/qisserver/rds?state=verpublish&publishContainer=ModulbaumAnzeigen"
            "&modulkatalog.mk_id=388&menuid=&topitem=modulbeschreibung&subitem="
        ),
    },
}

# Empfohlenes Semester je Modulkürzel, abgelesen aus dem Musterstudienverlaufsplan
# (Bild auf https://hpi.de/studium/it-systems-engineering-bsc/, abgerufen 2026-11-27).
# Steht ein Modul dort in zwei Semestern (RG, EW, SB), zählt das frühere.
SEMESTER_BY_CODE = {
    "HPI-PT1": 1, "HPI-MO": 1, "HPI-DS": 1, "HPI-MA1": 1, "HPI-RG": 1, "HPI-EW": 1,
    "HPI-PT2": 2, "HPI-MA2": 2,
    "HPI-BS": 3, "HPI-TI1": 3, "HPI-SWA": 3, "HPI-MA3": 3,
    "HPI-SWT": 4, "HPI-TI2": 4, "HPI-PSK": 4, "HPI-DTH": 4,
    "HPI-PEM": 5, "HPI-SP1": 5,
    "HPI-SP2": 6,
}
# Module, die im Plan nur als Gruppe stehen:
# Softwarebasis-Wahlpflichtmodule HPI-SB1 … HPI-SB5 („HPI-SB Wahlpflichtmodul“) ab dem 2. Semester,
# Vertiefungsgebiete „… - Grundlagen“ (Kürzel endet auf -G) im 4., „… - Vertiefung“ (-V) im 5. Semester.
SOFTWARE_BASICS_SEMESTER = 2
SPECIALIZATION_SEMESTER = {"-G": 4, "-V": 5}

# Stichwort im Modultitel → Skills (Tag-Namen wie in studies/curriculum.py).
# Ein Modul bekommt die Skills aller Stichwörter, die in seinem Titel vorkommen.
SKILLS_BY_KEYWORD = {
    "Programmiertechnik 1": ["C-Grundlagen", "Memory Management", "Git"],
    "Programmiertechnik 2": ["Java", "Objektorientierte Programmierung"],
    "Mathematik 1": ["Lineare Algebra", "Logik"],
    "Mathematik 2": ["Analysis", "Statistik"],
    "Digitale Systeme": ["Digitale Systeme", "Boolesche Algebra"],
    "Modellierung": ["UML", "Datenmodellierung"],
    "Theoretische Informatik": ["Theoretische Informatik"],
    "Datenbank": ["SQL", "Datenmodellierung"],
    "Softwaretechnik": ["Softwaretechnik", "Scrum", "Testen"],
    "Betriebssysteme": ["Linux", "Nebenläufigkeit"],
    "Vernetzte Systeme": ["Netzwerke"],
    "Prozessorientierte": ["Prozessmodellierung"],
    "Teammanagement": ["Projektmanagement"],
    "Wirtschaft": ["BWL"],
    "Professional Skills": ["Präsentieren"],
}


class ModuleListParser(HTMLParser):
    """Sammelt (Kürzel, Titel) aus den <summary>-Zeilen der PULS-Modulliste.

    Eine Modulzeile sieht so aus:
    <summary><span> HPI-PT1 </span><span> - <strong>Programmiertechnik 1</strong> …</span></summary>
    """

    def __init__(self):
        super().__init__()
        self.modules = []
        self.in_summary = False
        self.in_strong = False
        self.span_count = 0
        self.code = ""
        self.title = ""

    def handle_starttag(self, tag, attrs):
        if tag == "summary":
            self.in_summary = True
            self.span_count = 0
            self.code = ""
            self.title = ""
        elif tag == "span" and self.in_summary:
            self.span_count += 1
        elif tag == "strong" and self.in_summary:
            self.in_strong = True

    def handle_endtag(self, tag):
        if tag == "strong":
            self.in_strong = False
        elif tag == "summary" and self.in_summary:
            self.in_summary = False
            code = self.code.strip()
            title = " ".join(self.title.split())
            if re.fullmatch(r"HPI-[A-Z0-9-]+", code) and title:
                self.modules.append((code, title))

    def handle_data(self, data):
        if not self.in_summary:
            return
        if self.in_strong:
            self.title += data
        elif self.span_count == 1:
            self.code += data


def semester_for(code):
    """Empfohlenes Semester für ein Modulkürzel, oder None, wenn der Plan es nicht nennt."""
    if code in SEMESTER_BY_CODE:
        return SEMESTER_BY_CODE[code]
    if re.fullmatch(r"HPI-SB\d", code):
        return SOFTWARE_BASICS_SEMESTER
    for suffix, semester in SPECIALIZATION_SEMESTER.items():
        if code.endswith(suffix):
            return semester
    return None


def skills_for(title):
    """Alle Tag-Namen, deren Stichwort im Titel vorkommt (ohne Groß-/Kleinschreibung)."""
    names = []
    for keyword, skills in SKILLS_BY_KEYWORD.items():
        if keyword.lower() in title.lower():
            for name in skills:
                if name not in names:
                    names.append(name)
    return names


class Command(BaseCommand):
    help = "Liest den öffentlichen Modulkatalog eines Studiengangs ein (braucht Internet, außer mit --datei)."

    def add_arguments(self, parser):
        parser.add_argument("studiengang", choices=sorted(PROGRAMS), help="Kürzel des Studiengangs, z. B. itse")
        parser.add_argument("--datei", help="Lokale HTML-Datei statt der Seite im Internet lesen")

    def handle(self, *args, **options):
        config = PROGRAMS[options["studiengang"]]
        if options["datei"]:
            page = self.read_file(options["datei"])
        else:
            page = self.download(config["url"])

        parser = ModuleListParser()
        parser.feed(page)
        if not parser.modules:
            raise CommandError(
                "Im Modulkatalog wurden keine Module gefunden. Hat sich die Seite geändert?"
            )

        with transaction.atomic():
            program, _ = StudyProgram.objects.get_or_create(
                university=config["university"],
                abbreviation=config["abbreviation"],
                defaults={"name": config["name"], "standard_semesters": config["standard_semesters"]},
            )
            imported, without_skills, without_semester = [], [], []
            for code, title in parser.modules:
                semester = semester_for(code)
                if semester is None:
                    without_semester.append(code)
                    continue
                short_name = code.removeprefix("HPI-")
                course, _ = Course.objects.update_or_create(
                    program=program,
                    short_name=short_name,
                    defaults={"name": title, "semester": semester},
                )
                skill_names = skills_for(title)
                course.skills.set([Tag.objects.get_or_create(name=name)[0] for name in skill_names])
                imported.append(course)
                if not skill_names:
                    without_skills.append(f"{short_name} {title}")

        self.stdout.write(self.style.SUCCESS(f"{len(imported)} Module für {program} importiert."))
        for semester in sorted({course.semester for course in imported}):
            count = sum(1 for course in imported if course.semester == semester)
            self.stdout.write(f"  {semester}. Semester: {count} Module")
        if without_skills:
            self.stdout.write("Ohne Skills (kein Stichwort bekannt):")
            for name in without_skills:
                self.stdout.write(f"  - {name}")
        if without_semester:
            self.stdout.write("Übersprungen, kein Semester im Studienverlaufsplan:")
            for code in without_semester:
                self.stdout.write(f"  - {code}")

    def read_file(self, path):
        try:
            return Path(path).read_text(encoding="utf-8")
        except OSError as error:
            raise CommandError(f"Die Datei {path} lässt sich nicht lesen: {error}")

    def download(self, url):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except (urllib.error.URLError, TimeoutError) as error:
            raise CommandError(
                f"Der Modulkatalog ist nicht erreichbar ({error}). Besteht eine Internetverbindung?"
            )
        except OSError as error:
            raise CommandError(f"Der Modulkatalog ließ sich nicht vollständig laden ({error}).")
