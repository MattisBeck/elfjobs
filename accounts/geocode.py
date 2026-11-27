"""Wohnort in Koordinaten umrechnen (#53) mit Nominatim von OpenStreetMap (ohne Key).

Nominatim-Regeln: höchstens eine Anfrage pro Sekunde und ein eigener User-Agent.
Wir fragen nur beim Speichern des Profils, und nur wenn sich der Wohnort geändert hat.
"""

import json
import logging
from http.client import HTTPException
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)


def geocode(place):
    """(lat, lon) für einen Ort wie „Potsdam, Babelsberg“, sonst None. Wirft nie."""
    params = {"q": place, "format": "json", "limit": 1, "countrycodes": "de"}
    url = settings.GEOCODE_API_URL.rstrip("/") + "/search?" + urlencode(params)
    request = Request(url, headers={"User-Agent": "elfjobs-prototype"})
    try:
        with urlopen(request, timeout=settings.TRAVEL_API_TIMEOUT) as response:
            results = json.loads(response.read())
        if not results:
            return None
        return (float(results[0]["lat"]), float(results[0]["lon"]))
    except (URLError, HTTPException, TimeoutError, OSError, ValueError, KeyError) as error:
        logger.warning("Geocoding fehlgeschlagen für %r: %s", place, error)
        return None
