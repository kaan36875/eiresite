import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

CRS_ITM = "EPSG:2157"
CRS_WGS84 = "EPSG:4326"
CRS_ANALYSIS = CRS_ITM

GRID_RESOLUTION_KM = 5

DEFAULT_WEIGHTS = {
    "resource": 0.30,
    "grid_distance": 0.25,
    "road_distance": 0.15,
    "slope": 0.15,
    "settlement_distance": 0.15,
}

ENERGY_TYPES = {
    "solar": {
        "label": "Solar PV",
        "ideal_slope_min": 0,
        "ideal_slope_max": 5,
        "max_slope": 15,
        "min_settlement_m": 500,
    },
    "wind": {
        "label": "Wind Farm",
        "ideal_slope_min": 0,
        "ideal_slope_max": 10,
        "max_slope": 30,
        "min_settlement_m": 1500,
    },
}

MAX_GRID_DISTANCE_KM = 50
MAX_ROAD_DISTANCE_KM = 20
MAX_SETTLEMENT_DISTANCE_KM = 30

CARTO_API_KEY = os.environ.get("CARTO_API_KEY", "")
CARTO_TILE_URL = (
    f"https://basemaps.cartocdn.com/rastertiles/voyager/{{z}}/{{x}}/{{y}}.png?key={CARTO_API_KEY}"
    if CARTO_API_KEY
    else "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png"
)

DATA_SOURCES = {
    "flood_nifm_current": {
        "name": "NIFM River Flood Extents - Current Scenario",
        "url": "https://data.gov.ie/dataset/nifm-river-flood-extents-current-scenario",
        "format": "Shapefile (ITM)",
        "license": "CC BY-NC-ND 4.0",
        "provider": "OPW",
    },
    "protected_sac": {
        "name": "Special Areas of Conservation",
        "url": "https://npws.ie/node/11948",
        "format": "Shapefile (ITM)",
        "license": "Government of Ireland",
        "provider": "NPWS",
    },
    "protected_spa": {
        "name": "Special Protection Areas",
        "url": "https://npws.ie/node/11948",
        "format": "Shapefile (ITM)",
        "license": "Government of Ireland",
        "provider": "NPWS",
    },
    "protected_nha": {
        "name": "Natural Heritage Areas",
        "url": "https://npws.ie/node/11948",
        "format": "Shapefile (ITM)",
        "license": "Government of Ireland",
        "provider": "NPWS",
    },
    "wind_resource": {
        "name": "Global Wind Atlas — Mean Wind Speed at 100m",
        "url": "https://globalwindatlas.info/",
        "format": "GeoTIFF / API",
        "license": "CC BY 4.0",
        "provider": "DTU / World Bank",
    },
    "solar_resource": {
        "name": "PVGIS — Global Horizontal Irradiance",
        "url": "https://re.jrc.ec.europa.eu/pvg_tools/en/",
        "format": "API / CSV",
        "license": "Open (EU JRC)",
        "provider": "EU Joint Research Centre",
    },
    "wind_farms": {
        "name": "Wind Farms in Ireland",
        "url": "https://data.gov.ie/dataset/wind-farms-in-ireland",
        "download": "https://seaiopendata.blob.core.windows.net/wind/WindFarmsJune2022_ITM.zip",
        "format": "Shapefile (ITM)",
        "license": "CC BY 4.0",
        "provider": "SEAI",
    },
    "roads_250k": {
        "name": "Roads - National 250k Map of Ireland",
        "url": "https://data.gov.ie/dataset/roads-national-250k-map-of-ireland1",
        "format": "Shapefile",
        "license": "CC BY 4.0",
        "provider": "Tailte Eireann / OSi",
    },
    "dem_srtm": {
        "name": "SRTM Digital Elevation Model",
        "url": "https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL1.003/",
        "format": "HGT (raster)",
        "license": "Public Domain",
        "provider": "NASA / USGS",
    },
    "settlements_osm": {
        "name": "OpenStreetMap — Populated Places",
        "url": "https://www.openstreetmap.org/",
        "format": "OSM / Overpass API",
        "license": "ODbL",
        "provider": "OpenStreetMap contributors",
    },
}
