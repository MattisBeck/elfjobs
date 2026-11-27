"""Suchfilter für Stellenliste, Stellendetail und Karte (#71).

Die Werte kommen als GET-Parameter, damit man eine Suche teilen kann:
min_lohn (€ pro Stunde, effektiv), max_anreise (Minuten, einfach),
min_stunden und max_stunden (pro Woche) und auf der Karte max_km (Luftlinie).
Ungültige Werte (Text, negativ, zu groß) werden ignoriert, ebenso Werte
auf der „egal“-Stellung der Schieberegler (siehe SLIDERS). Werte werden auf
zwei Nachkommastellen gerundet, ein Minimum von 0 ist also kein Filter.
"""

from decimal import Decimal, InvalidOperation

from .models import JobPosting

FILTER_FIELDS = ["min_lohn", "max_anreise", "min_stunden", "max_stunden"]
# Die Entfernung gibt es nur auf der Karte, weil sie einen Startpunkt braucht.
MAP_FILTER_FIELDS = FILTER_FIELDS + ["max_km"]

# Größere Zahlen ergeben keinen Sinn und werden ignoriert.
MAX_VALUE = Decimal(10000)
# Auf zwei Nachkommastellen runden, damit z. B. 1e-50 nicht als Chip mit 50 Stellen erscheint.
CENT = Decimal("0.01")

# Schieberegler im Filterformular: Spanne, Schrittweite und die „egal“-Stellung.
# Als Text, damit Django im Template kein deutsches Komma daraus macht ("0,5").
# Die „egal“-Stellung filtert nicht: bei min_* alles bis dahin, bei max_* alles ab dort.
# Werte außerhalb der Spanne (z. B. ?min_lohn=40) bleiben gültige Filter.
SLIDERS = {
    "min_lohn": {"min": "0", "max": "25", "step": "0.5", "neutral": "0"},
    "max_anreise": {"min": "0", "max": "60", "step": "5", "neutral": "60"},
    "max_km": {"min": "1", "max": "30", "step": "1", "neutral": "30"},
    "min_stunden": {"min": "0", "max": "40", "step": "1", "neutral": "0"},
    "max_stunden": {"min": "0", "max": "40", "step": "1", "neutral": "40"},
}


def is_neutral(name, number):
    """Steht der Wert auf (oder hinter) der „egal“-Stellung des Reglers?"""
    neutral = Decimal(SLIDERS[name]["neutral"])
    if name.startswith("min_"):
        return number <= neutral
    return number >= neutral


def parse_number(value):
    """Zahl >= 0 mit zwei Nachkommastellen aus einem GET-Wert ("15", "15,50", "15.5"), sonst None."""
    try:
        number = Decimal(value.strip().replace(",", "."))
    except (AttributeError, InvalidOperation):
        return None
    if not number.is_finite() or number < 0 or number > MAX_VALUE:
        return None
    number = number.quantize(CENT)
    # "-0" wäre sonst ein Chip „max. -0 min“.
    if number == 0:
        return Decimal("0.00")
    return number


def parse_filters(get, fields=FILTER_FIELDS):
    """Gültige Filter aus request.GET als dict, z. B. {"min_lohn": Decimal("15")}."""
    filters = {}
    for name in fields:
        number = parse_number(get.get(name, ""))
        # „egal“ filtert nicht, z. B. "ab 0 €". Bei max_* heißt 0 dagegen etwas (z. B. nur remote).
        if number is not None and not is_neutral(name, number):
            filters[name] = number
    # "von 20 bis 10 Stunden" passt zu keiner Stelle, also beide ignorieren.
    if "min_stunden" in filters and "max_stunden" in filters:
        if filters["max_stunden"] < filters["min_stunden"]:
            del filters["min_stunden"]
            del filters["max_stunden"]
    return filters


def format_number(number, separator=","):
    """Decimal ohne überflüssige Nullen: 15.50 -> "15,5", 20 -> "20"."""
    return f"{number.normalize():f}".replace(".", separator)


def filter_number_params(filters):
    """Filter als (Name, Wert)-Paare für Links, in fester Reihenfolge."""
    return [(name, format_number(filters[name], ".")) for name in MAP_FILTER_FIELDS if name in filters]


def slider_settings(filters):
    """Einstellungen je Regler mit Startwert: aktiver Filter (am Rand der Spanne), sonst „egal“."""
    sliders = {}
    for name, spec in SLIDERS.items():
        value = filters.get(name, Decimal(spec["neutral"]))
        value = min(max(value, Decimal(spec["min"])), Decimal(spec["max"]))
        sliders[name] = {**spec, "value": format_number(value, ".")}
    return sliders


def commute_minutes(posting):
    """Einfache Fahrzeit zur Stelle in Minuten, remote zählt als 0.

    Vorerst die Annahme der Firma (Company.commute_minutes).
    Wird mit #53 durch die Fahrzeit vom Wohnort ersetzt.
    """
    if posting.workplace == JobPosting.Workplace.REMOTE:
        return 0
    return posting.company.commute_minutes


def matches(posting, filters):
    """Passt die Stelle zu den Filtern? max_km prüft die Karte selbst (braucht den Startpunkt)."""
    if "min_lohn" in filters and posting.effective_wage < filters["min_lohn"]:
        return False
    if "max_anreise" in filters and commute_minutes(posting) > filters["max_anreise"]:
        return False
    if "min_stunden" in filters and posting.hours_per_week < filters["min_stunden"]:
        return False
    if "max_stunden" in filters and posting.hours_per_week > filters["max_stunden"]:
        return False
    return True


def apply_filters(postings, filters):
    """Nur die Stellen, die zu den Filtern passen. Läuft in Python, weil der effektive Lohn dort berechnet wird."""
    return [posting for posting in postings if matches(posting, filters)]


def filter_labels(filters):
    """Texte für die aktiven Filter und welche Parameter ein Klick auf ✕ entfernt."""
    labels = []
    if "min_lohn" in filters:
        labels.append((f"ab {format_number(filters['min_lohn'])} €", ["min_lohn"]))
    if "max_anreise" in filters:
        labels.append((f"max. {format_number(filters['max_anreise'])} min Anreise", ["max_anreise"]))
    if "max_km" in filters:
        labels.append((f"max. {format_number(filters['max_km'])} km", ["max_km"]))
    low, high = filters.get("min_stunden"), filters.get("max_stunden")
    if low is not None and high is not None:
        labels.append((f"{format_number(low)}–{format_number(high)} h/Woche", ["min_stunden", "max_stunden"]))
    elif low is not None:
        labels.append((f"ab {format_number(low)} h/Woche", ["min_stunden"]))
    elif high is not None:
        labels.append((f"bis {format_number(high)} h/Woche", ["max_stunden"]))
    return labels
