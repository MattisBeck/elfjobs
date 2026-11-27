"""Lehrpläne für den Seed: Studiengänge mit ihren Modulen und den Skills, die sie vermitteln.

Stark vereinfacht und nur „angelehnt an“ die echten Studienordnungen (ITSE grob am
HPI-Bachelor, Semester 1 bis 3). Es geht um Skills, die für Nebenjobs zählen, nicht um
jedes Modul. Jeder Skill ist ein Tag aus jobs.Tag, fehlende Tags legt der Seed an.
Später kommt der Lehrplan per Import aus dem Modulkatalog (#40).

Aufbau: (Name, Kürzel, Hochschule, Regelstudienzeit, [(Semester, Kurzname, Modul, [Skills]), ...])
"""

CURRICULUM = [
    ("IT-Systems Engineering", "ITSE", "HPI", 6, [
        (1, "PT1", "Programmiertechnik I", ["C-Grundlagen", "Memory Management", "Git"]),
        (1, "MA1", "Mathematik I", ["Lineare Algebra", "Logik"]),
        (1, "DS", "Digitale Systeme", ["Digitale Systeme", "Boolesche Algebra"]),
        (1, "MOD1", "Modellierung I", ["UML", "Datenmodellierung"]),
        (1, "WG", "Wirtschaftliche Grundlagen", ["BWL"]),
        (2, "PT2", "Programmiertechnik II", ["Java", "Objektorientierte Programmierung"]),
        (2, "MA2", "Mathematik II", ["Analysis", "Statistik"]),
        (2, "TI1", "Theoretische Informatik I", ["Theoretische Informatik"]),
        (2, "RA", "Rechnerarchitektur", ["Rechnerarchitektur", "Assembler"]),
        (3, "DBS1", "Datenbanksysteme I", ["SQL", "Datenmodellierung"]),
        (3, "SWT1", "Softwaretechnik I", ["Softwaretechnik", "Scrum", "Testen"]),
        (3, "BS1", "Betriebssysteme I", ["Linux", "Nebenläufigkeit"]),
        (3, "WWW", "Internet- und WWW-Technologien", ["HTML/CSS", "JavaScript", "Netzwerke"]),
    ]),
    ("Wirtschaftsinformatik", "WI", "Uni Potsdam", 6, [
        (1, "EWI", "Einführung in die Wirtschaftsinformatik", ["Excel", "BWL"]),
        (1, "PROG", "Programmierung", ["Python"]),
        (2, "DB", "Datenbanken", ["SQL", "Datenmodellierung"]),
        (3, "GPM", "Geschäftsprozessmanagement", ["Prozessmodellierung", "Projektmanagement"]),
    ]),
    ("Betriebswirtschaftslehre", "BWL", "Uni Potsdam", 6, [
        (1, "ABWL", "Allgemeine BWL", ["BWL", "Excel"]),
        (1, "BUF", "Buchführung", ["Buchhaltung"]),
        (2, "KLR", "Kosten- und Leistungsrechnung", ["Kostenrechnung", "Controlling"]),
        (3, "MARK", "Marketing", ["Marketing", "Präsentieren"]),
    ]),
    ("Psychologie", "Psy", "Uni Potsdam", 6, [
        (1, "STAT1", "Statistik I", ["Statistik", "SPSS"]),
        (1, "WA", "Wissenschaftliches Arbeiten", ["Wissenschaftliches Arbeiten", "Englisch"]),
        (2, "MET", "Forschungsmethoden", ["Umfragen", "Interviewführung"]),
        (3, "AOW", "Arbeits- und Organisationspsychologie", ["Psychologie", "Personalmanagement"]),
    ]),
    ("Medien- und Kommunikationswissenschaft", "MuK", "Uni Potsdam", 6, [
        (1, "EMK", "Einführung in die Medienwissenschaft", ["Kommunikation", "Social Media"]),
        (2, "JOUR", "Journalistisches Schreiben", ["Texten", "Redaktion"]),
        (3, "MP", "Medienpraxis", ["Videoschnitt", "Content-Erstellung", "Design"]),
    ]),
]
