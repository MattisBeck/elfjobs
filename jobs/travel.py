"""Anreisedauer mit ÖPNV über die VBB-API von transport.rest (ohne Key).

Die API kennt Berlin und Brandenburg. Ergebnisse liegen im Model TravelTime
(Datenbank, 7 Tage gültig). Die Kartenseite liest nur daraus; fehlende Zeiten
holt der JSON-Endpunkt mit fetch_travel_times nach (#74). Antwortet die API
nicht, fehlen die Einträge, und der Aufrufer bleibt bei der Luftlinie.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timedelta
from decimal import Decimal
from http.client import HTTPException
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone

from .geo import BERLIN_MITTE, haversine_km
from .models import TravelTime

logger = logging.getLogger(__name__)

# Höchstens so viele Stellen pro Aufruf des JSON-Endpunkts abfragen (die nächsten nach
# Luftlinie), damit die Anfragegrenze der API hält.
MAX_TRAVEL_REQUESTS = 20

# Gesamtbudget für einen Aufruf von fetch_travel_times in Sekunden. Was bis dahin
# nicht da ist, kommt beim nächsten Mal.
TRAVEL_BUDGET_SECONDS = 3

# So viele Anfragen laufen gleichzeitig.
TRAVEL_WORKERS = 5

# Gespeicherte Zeiten gelten so lange, Fahrpläne ändern sich selten.
TRAVEL_CACHE_DAYS = 7

# Feste Startpunkte für warm_travel_cache. Klicks bis SNAP_KM daneben rasten hier ein,
# damit der vorgewärmte Cache auch für ungenaue Klicks greift.
START_POINTS = {
    "hpi": ("HPI / Griebnitzsee", (52.394, 13.132)),
    "potsdam-hbf": ("Potsdam Hbf", (52.392, 13.067)),
    "berlin-hbf": ("Berlin Hbf", (52.525, 13.369)),
    "alexanderplatz": ("Alexanderplatz", (52.522, 13.413)),
    "mitte": ("Berlin-Mitte (Standard der Karte)", BERLIN_MITTE),
}
SNAP_KM = 0.3


def _rounded(value):
    """Koordinate auf 3 Nachkommastellen (etwa 100 m) als Decimal."""
    return round(Decimal(str(value)), 3)


def travel_start(start):
    """Startpunkt für Anfragen und Cache: ein fester Startpunkt in der Nähe, sonst gerundet."""
    for _label, point in START_POINTS.values():
        if haversine_km(start[0], start[1], point[0], point[1]) <= SNAP_KM:
            start = point
            break
    return float(_rounded(start[0])), float(_rounded(start[1]))


def posting_destination(posting):
    """Ort der Stelle, gerundet wie im Cache."""
    return float(_rounded(posting.latitude)), float(_rounded(posting.longitude))


def _fetch_journeys(start, destination):
    """Fragt die API nach einer Verbindung und gibt die Liste "journeys" zurück."""
    params = {
        "from.latitude": start[0],
        "from.longitude": start[1],
        "from.address": "Start",
        "to.latitude": destination[0],
        "to.longitude": destination[1],
        "to.address": "Ziel",
        "results": 1,
        "stopovers": "false",
        "remarks": "false",
    }
    url = settings.TRAVEL_API_URL.rstrip("/") + "/journeys?" + urlencode(params)
    request = Request(url, headers={"User-Agent": "elfjobs-prototype"})
    with urlopen(request, timeout=settings.TRAVEL_API_TIMEOUT) as response:
        body = response.read()
    return json.loads(body)["journeys"]


def _journey_minutes(journey):
    """Dauer einer Verbindung: Ankunft der letzten minus Abfahrt der ersten Etappe."""
    first_leg = journey["legs"][0]
    last_leg = journey["legs"][-1]
    # Bei Ausfällen fehlt die Echtzeit, dann gilt der Fahrplan.
    departure = first_leg["departure"] or first_leg["plannedDeparture"]
    arrival = last_leg["arrival"] or last_leg["plannedArrival"]
    duration = datetime.fromisoformat(arrival) - datetime.fromisoformat(departure)
    return round(duration.total_seconds() / 60)


def fetch_minutes(start, destination):
    """Fragt die API, ohne Cache: (Minuten, ok). Wirft nie eine Exception.

    ok ist False bei Timeout oder API-Fehler, nicht bei "keine Verbindung"
    (dann (None, True)). Fasst die Datenbank nicht an, läuft daher auch in Threads.
    """
    try:
        journeys = _fetch_journeys(start, destination)
        if not journeys:
            return None, True
        return _journey_minutes(journeys[0]), True
    except (
        URLError, OSError, HTTPException, ValueError, KeyError, IndexError, TypeError, AttributeError
    ) as error:
        # Timeout, HTTP-Fehler, abgebrochene Antwort, kaputtes JSON oder unerwartetes Format.
        # Nicht speichern, beim nächsten Mal noch einmal versuchen.
        logger.warning("Anreise-API nicht erreichbar: %s", error)
        return None, False


def save_minutes(start, destination, minutes):
    """Speichert eine Antwort der API (auch None = keine Verbindung) in TravelTime."""
    TravelTime.objects.update_or_create(
        start_lat=_rounded(start[0]),
        start_lon=_rounded(start[1]),
        dest_lat=_rounded(destination[0]),
        dest_lon=_rounded(destination[1]),
        defaults={"minutes": minutes, "fetched_at": timezone.now()},
    )


def _fresh_entries(start):
    """Gültige Einträge ab start: {(ziel_lat, ziel_lon): Minuten oder None}. Eine Abfrage."""
    start = travel_start(start)
    entries = TravelTime.objects.filter(
        start_lat=_rounded(start[0]),
        start_lon=_rounded(start[1]),
        fetched_at__gte=timezone.now() - timedelta(days=TRAVEL_CACHE_DAYS),
    )
    return {(float(e.dest_lat), float(e.dest_lon)): e.minutes for e in entries}


def cached_travel_times(start, postings):
    """Bekannte Anreisezeiten aus der Datenbank, ohne API: {posting.id: Minuten oder None}.

    None heißt "keine Verbindung". Stellen, die noch nicht (oder nicht mehr gültig)
    gespeichert sind, fehlen im dict.
    """
    entries = _fresh_entries(start)
    times = {}
    for posting in postings:
        if posting.has_location and posting_destination(posting) in entries:
            times[posting.id] = entries[posting_destination(posting)]
    return times


def travel_minutes(start, destination):
    """Anreise in ganzen Minuten von start nach destination, je (lat, lon).

    Erst aus der Datenbank, sonst fragt die API (und speichert). Gibt None zurück,
    wenn es keine Verbindung gibt oder die API nicht antwortet. Wirft nie.
    """
    start = travel_start(start)
    destination = (float(_rounded(destination[0])), float(_rounded(destination[1])))
    entries = _fresh_entries(start)
    if destination in entries:
        return entries[destination]
    minutes, ok = fetch_minutes(start, destination)
    if ok:
        save_minutes(start, destination, minutes)
    return minutes


def fetch_travel_times(start, postings, budget=None):
    """Anreise für die übergebenen Stellen, fehlende parallel von der API.

    Höchstens TRAVEL_WORKERS Anfragen gleichzeitig. Nach `budget` Sekunden
    (Standard TRAVEL_BUDGET_SECONDS) wird nicht mehr gewartet: Was bis dahin
    da ist, wird gespeichert und zurückgegeben (Teilergebnis), der Rest fehlt.
    Ergebnis wie cached_travel_times: {posting.id: Minuten oder None}.
    """
    if budget is None:
        budget = TRAVEL_BUDGET_SECONDS
    start = travel_start(start)
    times = cached_travel_times(start, postings)

    # Fehlende Ziele, jedes nur einmal (mehrere Stellen können am selben Ort sein).
    missing = {}
    for posting in postings:
        if posting.has_location and posting.id not in times:
            missing.setdefault(posting_destination(posting), []).append(posting.id)
    if not missing:
        return times

    executor = ThreadPoolExecutor(max_workers=TRAVEL_WORKERS)
    futures = {executor.submit(fetch_minutes, start, destination): destination for destination in missing}
    done, _not_done = wait(futures, timeout=budget)
    # Nicht auf hängende Anfragen warten; noch nicht gestartete werden abgesagt.
    executor.shutdown(wait=False, cancel_futures=True)

    # Speichern erst hier im Haupt-Thread, die Threads fassen die Datenbank nicht an.
    for future in done:
        minutes, ok = future.result()
        if not ok:
            continue
        destination = futures[future]
        save_minutes(start, destination, minutes)
        for posting_id in missing[destination]:
            times[posting_id] = minutes
    return times
