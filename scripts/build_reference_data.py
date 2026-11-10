"""
Generate the static reference data shipped in custom_components/urban_weather/data/.

Run rarely (when the city publishes a new metadata catalogue or many new stations):

    uv run --no-project --with openpyxl --with rasterio \
        python scripts/build_reference_data.py [--sensors-file sensors.json]

Outputs:
- catalog.json    station siting metadata (Smart City Mannheim metadata catalogue)
- lcz_grid.json   Local Climate Zone raster around Mannheim (Demuzere et al.)
- districts.json  district name per station location (OpenStreetMap / Nominatim)
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import importlib.util
import io
import json
import time
import urllib.parse
import urllib.request
import zlib
from pathlib import Path
from typing import Any

import openpyxl
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = ROOT / "custom_components" / "urban_weather"
DATA_DIR = PACKAGE_DIR / "data"
DEFAULT_CACHE_DIR = ROOT / ".cache" / "reference-build"

USER_AGENT = (
    "ha-urban-weather-build/0.1 (+https://github.com/CodeBrauer/ha-urban-weather)"
)
HTTP_TIMEOUT_S = 60

CATALOG_URL = (
    "https://opendata.smartmannheim.de/dataset/23c48b6a-42b6-44f1-8756-5e83340a6a0a/"
    "resource/6ecbb67f-6564-4a46-9c26-a99e6ad5a0c2/download/metadatenkatalog_ma_klimamessnetz.xlsx"
)
CATALOG_DATASET_URL = (
    "https://opendata.smartmannheim.de/dataset/metadaten-stadtklimamessnetze-mannheim"
)
CATALOG_LICENSE = "dl-de/by-2-0 (Datenlizenz Deutschland - Namensnennung - Version 2.0)"
CATALOG_HEADER_ROWS = 2  # column names + a row with table references
CATALOG_UNKNOWN_HEIGHT = 99
CATALOG_LCZ_FIELD_LEN = 2

LCZ_URL = "https://zenodo.org/records/6364594/files/lcz_filter_v1.tif"
LCZ_DATASET_URL = "https://doi.org/10.5281/zenodo.6364594"
LCZ_LICENSE = "CC BY 4.0"
LCZ_CITATION = (
    "Demuzere, M., Kittner, J., Martilli, A., Mills, G., Moede, C., Stewart, I. D., "
    "van Vliet, J., and Bechtel, B.: A global map of local climate zones to support "
    "earth system modelling and urban-scale environmental science, "
    "Earth Syst. Sci. Data, 14, 3835-3873, 2022"
)
# Network extent plus ~5 km so homes in neighbouring towns are covered.
LCZ_BOUNDS = {"west": 8.36, "south": 49.37, "east": 8.66, "north": 49.63}

SENSORS_URL = "https://api.smartmannheim.de/climate/sensors"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_LICENSE = "ODbL 1.0, (c) OpenStreetMap contributors"
NOMINATIM_SPACING_S = 1.1  # usage policy: max. 1 request per second
NOMINATIM_ZOOM = 14
DISTRICT_ADDRESS_KEYS = (
    "suburb",
    "city_district",
    "quarter",
    "village",
    "town",
    "city",
)
STATION_CLUSTER_RADIUS_M = 15


def _load_geo() -> Any:
    spec = importlib.util.spec_from_file_location("geo", PACKAGE_DIR / "geo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


geo = _load_geo()


def _http_get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as response:  # noqa: S310
        return response.read()


def _source(**fields: str) -> dict[str, str]:
    return {**fields, "generated": dt.datetime.now(dt.UTC).date().isoformat()}


def _write(name: str, payload: dict[str, Any]) -> None:
    path = DATA_DIR / name
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    )
    print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB)")


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def _lcz_main_class(value: Any) -> int | None:
    """Parse '06/09' (main class / sub class) to 6."""
    text = str(value or "").strip()
    if len(text) < CATALOG_LCZ_FIELD_LEN:
        return None
    lcz = _int_or_none(text[:CATALOG_LCZ_FIELD_LEN])
    return lcz or None


def build_catalog() -> None:
    """Extract the siting metadata needed for station suitability."""
    workbook = openpyxl.load_workbook(
        io.BytesIO(_http_get(CATALOG_URL)), read_only=True, data_only=True
    )
    rows = list(workbook.worksheets[0].iter_rows(values_only=True))
    header = [str(cell).strip() if cell else "" for cell in rows[0]]
    stations = []
    for row in rows[CATALOG_HEADER_ROWS:]:
        record = dict(zip(header, row, strict=False))
        code_string = str(record.get("Code_String") or "")
        lat = _int_or_none(record.get("Lat Geog. Breite"))
        lon = _int_or_none(record.get("Lon Geog. Länge"))
        if not code_string or lat is None or lon is None:
            continue
        temperature_height = _int_or_none(record.get("TT Messhöhe"))
        zone = _int_or_none(record.get("Z Vertikale Zonierung"))
        stations.append(
            {
                "code": code_string[:11],
                "hardware": str(record.get("Stationsname") or "").strip() or None,
                "network": record.get("Messnetz Nummer"),
                # Coordinates are stored without the decimal point (Tab. 9).
                "lat": lat / 1e6,
                "lon": lon / 1e6,
                "height_above_ground": _int_or_none(
                    record.get("Station Höhe über Grund SFC")
                ),
                "temperature_height": None
                if temperature_height in (None, 0, CATALOG_UNKNOWN_HEIGHT)
                else temperature_height,
                "zone": zone or None,
                "quality": _int_or_none(record.get("Stationsqualität SQ")),
                "lcz": _lcz_main_class(record.get("LCZ")),
            }
        )
    _write(
        "catalog.json",
        {
            "source": _source(
                title="Metadatenkatalog Stadtklimamessnetze Mannheim",
                url=CATALOG_DATASET_URL,
                publisher="Smart City Mannheim GmbH",
                license=CATALOG_LICENSE,
            ),
            "stations": stations,
        },
    )


def build_lcz_grid() -> None:
    """Cut the Mannheim window out of the global LCZ map (windowed HTTP reads)."""
    with (
        rasterio.Env(
            GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
            CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
        ),
        rasterio.open(f"/vsicurl/{LCZ_URL}") as dataset,
    ):
        window = (
            from_bounds(
                LCZ_BOUNDS["west"],
                LCZ_BOUNDS["south"],
                LCZ_BOUNDS["east"],
                LCZ_BOUNDS["north"],
                dataset.transform,
            )
            .round_offsets()
            .round_lengths()
        )
        grid = dataset.read(1, window=window)
        transform = dataset.window_transform(window)
    rows, cols = grid.shape
    _write(
        "lcz_grid.json",
        {
            "source": _source(
                title="Global map of Local Climate Zones (lcz_filter_v1)",
                url=LCZ_DATASET_URL,
                citation=LCZ_CITATION,
                license=LCZ_LICENSE,
            ),
            "north": transform.f,
            "west": transform.c,
            "step_lat": -transform.e,
            "step_lon": transform.a,
            "rows": rows,
            "cols": cols,
            # uint8 LCZ classes 1-17 (0 = no data), row-major from north-west.
            "data": base64.b64encode(zlib.compress(grid.tobytes(), 9)).decode(),
        },
    )


def _load_sensors(sensors_file: Path | None) -> list[tuple[float, float]]:
    raw = sensors_file.read_bytes() if sensors_file else _http_get(SENSORS_URL)
    points = []
    for sensor in json.loads(raw).get("sensors", []):
        position = sensor.get("position") or []
        if len(position) != 2:  # noqa: PLR2004
            continue
        lon, lat = position
        if lat < lon:  # a few sensors have swapped coordinates
            lat, lon = lon, lat
        points.append((lat, lon))
    return points


def _reverse_geocode(lat: float, lon: float, cache_dir: Path) -> str | None:
    cache_file = cache_dir / f"{lat:.5f}_{lon:.5f}.json"
    if cache_file.exists():
        payload = json.loads(cache_file.read_text())
    else:
        query = urllib.parse.urlencode(
            {
                "format": "jsonv2",
                "lat": f"{lat:.5f}",
                "lon": f"{lon:.5f}",
                "zoom": NOMINATIM_ZOOM,
                "addressdetails": 1,
                "accept-language": "de",
            }
        )
        payload = json.loads(_http_get(f"{NOMINATIM_URL}?{query}"))
        cache_file.write_text(json.dumps(payload))
        time.sleep(NOMINATIM_SPACING_S)
    address = payload.get("address") or {}
    return next((address[key] for key in DISTRICT_ADDRESS_KEYS if key in address), None)


def build_districts(sensors_file: Path | None, cache_dir: Path) -> None:
    """Name the district of every current station location."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    points = _load_sensors(sensors_file)
    clusters = geo.cluster_points(points, STATION_CLUSTER_RADIUS_M)
    districts = []
    for number, cluster in enumerate(clusters, start=1):
        lat, lon = points[cluster[0]]
        name = _reverse_geocode(lat, lon, cache_dir)
        if name:
            districts.append({"lat": round(lat, 5), "lon": round(lon, 5), "name": name})
        if number % 50 == 0:
            print(f"  geocoded {number}/{len(clusters)}")
    _write(
        "districts.json",
        {
            "source": _source(
                title="District names via Nominatim reverse geocoding",
                url="https://nominatim.openstreetmap.org/",
                license=NOMINATIM_LICENSE,
            ),
            "districts": districts,
        },
    )


def main() -> None:
    """Build all reference files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sensors-file", type=Path, help="reuse a saved /sensors response"
    )
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument(
        "--only", choices=("catalog", "lcz", "districts"), help="build a single file"
    )
    args = parser.parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if args.only in (None, "catalog"):
        build_catalog()
    if args.only in (None, "lcz"):
        build_lcz_grid()
    if args.only in (None, "districts"):
        build_districts(args.sensors_file, args.cache_dir)


if __name__ == "__main__":
    main()
