"""Anreisedauer mit ÖPNV über die VBB-API von transport.rest (ohne Key).

Die API kennt Berlin und Brandenburg. Antwortet sie nicht, geben die
Funktionen None bzw. weniger Einträge zurück; der Aufrufer bleibt dann
bei der Luftlinie.
"""

import json
import logging
from datetime import datetime
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Höchstens so viele Stellen pro Aufruf von travel_times abfragen,
# damit die Anfragegrenze der API hält.
MAX_TRAVEL_REQUESTS = 20

CACHE_SECONDS = 24 * 60 * 60  # gefundene Verbindungen: 1 Tag
NO_CONNECTION_CACHE_SECONDS = 60 * 60  # "keine Verbindung": 1 Stunde

# Unterscheidet "nicht im Cache" von einem gecachten None ("keine Verbindung").
NOT_CACHED = object()


def _cache_key(start, destination):
    """Schlüssel aus Koordinaten, gerundet auf 3 Nachkommastellen (etwa 100 m)."""
    return "travel:{:.3f},{:.3f}:{:.3f},{:.3f}".format(
        start[0], start[1], destination[0], destination[1]
    )


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


def _lookup(start, destination, ask_api=True):
    """Anreise in Minuten plus Angabe, ob die API geantwortet hat: (Minuten, ok).

    ok ist False bei Timeout oder API-Fehler, nicht bei "keine Verbindung".
    Mit ask_api=False wird nur im Cache nachgesehen.
    """
    key = _cache_key(start, destination)
    cached = cache.get(key, NOT_CACHED)
    if cached is not NOT_CACHED:
        return cached, True
    if not ask_api:
        return None, False

    try:
        journeys = _fetch_journeys(start, destination)
        if not journeys:
            cache.set(key, None, NO_CONNECTION_CACHE_SECONDS)
            return None, True
        minutes = _journey_minutes(journeys[0])
    except (URLError, OSError, ValueError, KeyError, IndexError, TypeError) as error:
        # Timeout, HTTP-Fehler, kaputtes JSON oder unerwartetes Format.
        # Nicht cachen, beim nächsten Mal noch einmal versuchen.
        logger.warning("Anreise-API nicht erreichbar: %s", error)
        return None, False

    cache.set(key, minutes, CACHE_SECONDS)
    return minutes, True


def travel_minutes(start, destination):
    """Anreise in ganzen Minuten von start nach destination, je (lat, lon).

    Gibt None zurück, wenn es keine Verbindung gibt oder die API nicht
    antwortet. Wirft nie eine Exception.
    """
    minutes, _ok = _lookup(start, destination)
    return minutes


def travel_times(start, postings, limit=MAX_TRAVEL_REQUESTS):
    """Anreise in Minuten für die ersten `limit` Stellen mit Ort.

    Der Aufrufer übergibt die Stellen nach Luftlinie sortiert. Ergebnis:
    {posting.id: Minuten}. Stellen ohne Ergebnis fehlen im dict.

    Nach dem ersten Fehler oder Timeout wird die API nicht mehr gefragt,
    damit die Seite bei hängender API nicht `limit` Timeouts lang wartet.
    Ergebnisse aus dem Cache werden weiter genutzt.
    """
    times = {}
    asked = 0
    api_ok = True
    for posting in postings:
        if asked >= limit:
            break
        if not posting.has_location:
            continue
        asked += 1
        destination = (float(posting.latitude), float(posting.longitude))
        minutes, ok = _lookup(start, destination, ask_api=api_ok)
        if not ok:
            api_ok = False
        if minutes is not None:
            times[posting.id] = minutes
    return times
