from time import monotonic, sleep

from django.core.management.base import BaseCommand

from jobs.models import JobPosting
from jobs.travel import (
    START_POINTS,
    cached_travel_times,
    fetch_minutes,
    posting_destination,
    save_minutes,
    travel_start,
)

# Pause zwischen zwei Anfragen in Sekunden. transport.rest erlaubt etwa 100 Anfragen
# pro Minute; mit der Pause bleiben wir darunter.
PAUSE_SECONDS = 0.6

# Nach so vielen Fehlern hintereinander aufhören, statt bei hängender API
# jedes Ziel bis zum Timeout abzuwarten.
MAX_ERRORS_IN_A_ROW = 5


class Command(BaseCommand):
    help = (
        "Fragt die Anreisedauer von festen Startpunkten (jobs/travel.py: START_POINTS) "
        "zu allen Stellen mit Ort ab und speichert sie (#74). Frische Einträge werden "
        "übersprungen. Abbrechen mit Strg+C, bis dahin Gespeichertes bleibt."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--startpunkt",
            choices=sorted(START_POINTS),
            help="Nur diesen Startpunkt abfragen (Standard: alle).",
        )

    def handle(self, *args, **options):
        keys = [options["startpunkt"]] if options["startpunkt"] else list(START_POINTS)
        postings = list(JobPosting.objects.filter(latitude__isnull=False, longitude__isnull=False))
        began = monotonic()
        saved = errors = errors_in_a_row = 0
        try:
            for key in keys:
                label, point = START_POINTS[key]
                start = travel_start(point)
                known = cached_travel_times(start, postings)
                # Jedes Ziel nur einmal, auch wenn dort mehrere Stellen liegen.
                destinations = sorted({posting_destination(p) for p in postings if p.id not in known})
                self.stdout.write(
                    f"{label}: {len(destinations)} Ziele offen, {len(known)} Stellen schon gespeichert."
                )
                for number, destination in enumerate(destinations, start=1):
                    minutes, ok = fetch_minutes(start, destination)
                    if ok:
                        save_minutes(start, destination, minutes)
                        saved += 1
                        errors_in_a_row = 0
                    else:
                        errors += 1
                        errors_in_a_row += 1
                        if errors_in_a_row >= MAX_ERRORS_IN_A_ROW:
                            break
                    if number % 10 == 0 or number == len(destinations):
                        self.stdout.write(f"  {number}/{len(destinations)}")
                    sleep(PAUSE_SECONDS)
                if errors_in_a_row >= MAX_ERRORS_IN_A_ROW:
                    self.stdout.write(self.style.ERROR(
                        f"{MAX_ERRORS_IN_A_ROW} Fehler hintereinander, die API antwortet wohl nicht. Später noch einmal."
                    ))
                    break
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Abgebrochen."))
        self.stdout.write(self.style.SUCCESS(
            f"{saved} Anreisezeiten gespeichert, {errors} Fehler, {monotonic() - began:.0f} s."
        ))
