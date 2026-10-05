r"""Build search/us_places.csv, the offline list of U.S. city coordinates used to check
that hybrid and on-site jobs are within each city's radius (no geocoding service).

Source: the U.S. Census Bureau's Gazetteer place file (public domain), for example
https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_place_national.zip

    .venv\Scripts\python scripts\build_places.py path\to\2025_Gaz_place_national.txt
"""

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "search" / "us_places.csv"

# Census names end in the place type: "Knoxville city", "Abanda CDP".
TYPE = re.compile(r"\s+(city and borough|unified government|consolidated government|metropolitan government|"
                  r"metro government|urban county|zona urbana|comunidad|municipality|corporation|borough|"
                  r"village|town|city|CDP)$", re.I)
# Combined city-county governments are also found by their first name:
# "Nashville-Davidson metropolitan government (balance)" -> "Nashville".
COMBINED = re.compile(r"government|urban county", re.I)
ALIASES = {("HI", "Urban Honolulu"): "Honolulu"}


def clean(name: str) -> str:
    name = re.sub(r"\s*\(balance\)$", "", name.strip())
    return TYPE.sub("", name).strip()


def main(source: Path) -> None:
    best: dict[tuple[str, str], tuple[int, int, str, str, str]] = {}
    with source.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="|"):
            state, raw = row["USPS"].strip(), row["NAME"].strip()
            names = {clean(raw)}
            if alt := re.match(r"(.+?)\s*\((.+)\)$", clean(raw)):  # "San Buenaventura (Ventura)"
                names = {alt[1], alt[2]}
            if COMBINED.search(raw):
                names.add(re.split(r"[-/,]", clean(raw))[0].strip())
            if (state, clean(raw)) in ALIASES:
                names.add(ALIASES[(state, clean(raw))])
            # Prefer incorporated places over census-designated ones, then the larger area.
            rank = (0 if raw.endswith(" CDP") else 1, int(row["ALAND"]))
            lat, lon = row["INTPTLAT"].strip(), row["INTPTLONG"].strip()
            for name in names:
                key = (state, name.lower())
                if key not in best or rank > best[key][:2]:
                    best[key] = (*rank, name, lat, lon)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["state", "name", "lat", "lon"])
        for (state, _), (_, _, name, lat, lon) in sorted(best.items()):
            writer.writerow([state, name, lat, lon])
    print(f"Wrote {len(best)} places to {OUT}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
