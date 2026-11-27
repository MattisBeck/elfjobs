import math

# Startpunkt der Karte, wenn keiner gewählt ist: Berlin-Mitte (Breitengrad, Längengrad).
BERLIN_MITTE = (52.5200, 13.4050)

# Mittlerer Erdradius in Kilometern
EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2):
    """Luftlinie zwischen zwei Punkten in Kilometern (Haversine-Formel, Grad als float)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def parse_start(lat, lon):
    """Startpunkt aus den GET-Parametern lat/lon, oder None, wenn sie fehlen oder ungültig sind."""
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    # Schließt auch nan und inf aus, weil jeder Vergleich damit False ergibt.
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon
