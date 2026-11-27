"""Erzeugt die Beispiel-Lebensläufe in diesem Ordner (#50).

Alle Personen, Adressen und Mails sind erfunden. Aufruf im Container:

    docker compose exec backend uv run python accounts/sample_cvs/make_sample_cvs.py

Die PDFs liegen im Repo, das Skript braucht man nur, wenn sich ein Lebenslauf ändert.
Die Kenntnisse sind absichtlich mit Synonymen geschrieben („MS Excel“, „Python 3“,
„English“), damit die Synonymliste in accounts/cv.py gebraucht wird.
"""

from datetime import datetime, timezone
from pathlib import Path

from fpdf import FPDF

FOLDER = Path(__file__).resolve().parent

# Feste Zeit, damit jede Erzeugung dieselben Dateien liefert.
CREATED = datetime(2026, 11, 27, tzinfo=timezone.utc)

# Dateiname ohne .pdf: (Name, Kontakt, [(Abschnitt, [Zeilen]), ...])
SAMPLE_CVS = {
    "mia-itse": ("Mia Sommer", "Lindenallee 4, 14469 Potsdam · mia.sommer@example.com", [
        ("Studium", ["seit 10/2026 IT-Systems Engineering (B.Sc.), HPI Potsdam, 1. Semester"]),
        ("Kenntnisse", [
            "Programmieren: Python 3, JavaScript, HTML/CSS",
            "Werkzeuge: Git, Linux (Ubuntu), MS Excel",
        ]),
        ("Sprachen", ["Deutsch (Muttersprache), Englisch (C1)"]),
        ("Engagement", ["Mentorin im Schul-Robotik-Kurs, Arbeit im Team mit 6 Leuten"]),
    ]),
    "julia-politik": ("Julia Brandt", "Am Kanal 21, 14467 Potsdam · julia.brandt@example.com", [
        ("Studium", ["seit 10/2026 Politikwissenschaft (B.A.), Uni Potsdam, 1. Semester"]),
        ("Kenntnisse", [
            "Office: MS Word, MS Excel",
            "Social Media: Instagram und TikTok für die Schülerzeitung betreut",
        ]),
        ("Sprachen", ["Deutsch (Muttersprache), English (B2)"]),
        ("Nebenjobs", ["Aushilfe im Café, 2 Jahre, Wochenenden"]),
    ]),
    "justus-bwl": ("Justus Albrecht", "Zeppelinstraße 9, 14471 Potsdam · justus.albrecht@example.com", [
        ("Studium", ["seit 10/2026 Betriebswirtschaftslehre (BWL, B.Sc.), Uni Potsdam, 1. Semester"]),
        ("Kenntnisse", [
            "Microsoft Excel (Pivot-Tabellen, SVERWEIS), PowerPoint",
            "Vertrieb: Ferienjob im Autohaus, Buchführung im Familienbetrieb",
        ]),
        ("Sprachen", ["Deutsch (Muttersprache), Englisch (B2), Französisch (A2)"]),
    ]),
    "paula-psychologie": ("Paula Wendt", "Breite Straße 30, 14467 Potsdam · paula.wendt@example.com", [
        ("Studium", ["seit 10/2025 Psychologie (B.Sc.), Uni Potsdam, 3. Semester"]),
        ("Kenntnisse", [
            "Auswertung: SPSS, Statistik (Regression, t-Test)",
            "Erhebung: Online-Umfragen mit LimeSurvey",
        ]),
        ("Sprachen", ["Deutsch (Muttersprache), Englisch (C1)"]),
        ("Nebenjobs", ["Studentische Hilfskraft am Lehrstuhl für Sozialpsychologie"]),
    ]),
    "jonas-wirtschaftsinformatik": (
        "Jonas Petersen", "Gutenbergstraße 2, 14467 Potsdam · jonas.petersen@example.com", [
            ("Studium", ["seit 10/2025 Wirtschaftsinformatik (B.Sc.), Uni Potsdam, 3. Semester"]),
            ("Kenntnisse", [
                "Datenbanken: PostgreSQL, MySQL",
                "Programmieren: Java, Python3",
                "Projektmanagement mit Scrum im Uni-Projekt",
            ]),
            ("Sprachen", ["Deutsch (Muttersprache), English (C1)"]),
        ],
    ),
}


def make_cv(name, contact, sections):
    pdf = FPDF()
    pdf.set_creation_date(CREATED)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, name, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, contact, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Lebenslauf (Beispiel für elfjobs, erfundene Person)", new_x="LMARGIN", new_y="NEXT")
    for title, lines in sections:
        pdf.ln(6)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        for line in lines:
            pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
    return pdf


def make_scan():
    """Ein „eingescannter“ Lebenslauf: nur Grafik, kein Text. Ergibt keine Vorschläge."""
    pdf = FPDF()
    pdf.set_creation_date(CREATED)
    pdf.add_page()
    pdf.set_fill_color(225, 228, 233)
    pdf.rect(20, 20, 90, 12, style="F")
    for row in range(12):
        pdf.rect(20, 50 + row * 10, 170 - (row % 3) * 30, 4, style="F")
    return pdf


def main():
    for filename, (name, contact, sections) in SAMPLE_CVS.items():
        make_cv(name, contact, sections).output(str(FOLDER / f"{filename}.pdf"))
    make_scan().output(str(FOLDER / "scan-ohne-text.pdf"))


if __name__ == "__main__":
    main()
