"""City coordinates and distances, offline (spec: hybrid and on-site jobs must be within
one of your cities' radius).

Adzuna's `distance` parameter is approximate, so city-query results are checked again
against the job's latitude and longitude. City coordinates come from us_places.csv,
built from the Census Bureau's Gazetteer by scripts/build_places.py; no geocoding
service is called.
"""

import csv
import math
import re
from functools import cache
from pathlib import Path

PLACES_PATH = Path(__file__).resolve().parent / "us_places.csv"
EARTH_RADIUS_MILES = 3958.8

STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "district of columbia": "DC", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD", "massachusetts": "MA",
    "michigan": "MI", "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT",
    "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "puerto rico": "PR", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
ABBREVIATIONS = {"saint": "st", "ste": "st", "sainte": "st", "ft": "fort", "mt": "mount"}


def _key(name: str) -> str:
    words = re.sub(r"[^a-z0-9]+", " ", name.lower()).split()
    return " ".join(ABBREVIATIONS.get(w, w) for w in words)


def _state(text: str) -> str | None:
    text = text.strip().strip(".").lower()
    if len(text) == 2 and text.upper() in STATES.values():
        return text.upper()
    return STATES.get(text)


@cache
def _places() -> dict[tuple[str, str], tuple[float, float]]:
    with PLACES_PATH.open(encoding="utf-8", newline="") as f:
        return {(r["state"], _key(r["name"])): (float(r["lat"]), float(r["lon"])) for r in csv.DictReader(f)}


def lookup(city: str) -> tuple[float, float] | None:
    """Coordinates for "Nashville, TN" or "Nashville, Tennessee"; None if not found."""
    name, _, state = city.rpartition(",")
    code = _state(state)
    if not name.strip() or not code:
        return None
    return _places().get((code, _key(name)))


def miles_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in miles."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(h))
