"""Download helper for Irish open geospatial datasets.

Some datasets require manual download (login, CAPTCHA, or license acceptance).
This script automates what it can and prints instructions for the rest.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import RAW_DIR, DATA_SOURCES


def print_instructions():
    print("=" * 70)
    print("IRELAND SITE ASSESSMENT — DATA DOWNLOAD GUIDE")
    print("=" * 70)
    print()
    print(f"Download each dataset and extract into: {RAW_DIR}")
    print()

    instructions = [
        {
            "name": "NIFM Flood Extents (Current Scenario)",
            "url": "https://data.gov.ie/dataset/nifm-river-flood-extents-current-scenario",
            "steps": [
                "Visit the URL above",
                "Click the shapefile download link",
                "Extract the ZIP into data/raw/NIFM_Current/",
            ],
            "crs": "ITM (EPSG:2157)",
        },
        {
            "name": "NPWS Protected Areas (SAC, SPA, NHA)",
            "url": "https://npws.ie/node/11948",
            "steps": [
                "Visit the URL above",
                "Download SAC_ITM_2024_01.zip, SPA_ITM_2024_01.zip, NHA_ITM_2019_06.zip",
                "Extract each into data/raw/SAC/, data/raw/SPA/, data/raw/NHA/",
            ],
            "crs": "ITM (EPSG:2157)",
        },
        {
            "name": "Wind Farms in Ireland (substation proxy)",
            "url": "https://data.gov.ie/dataset/wind-farms-in-ireland",
            "steps": [
                "Direct download: https://seaiopendata.blob.core.windows.net/wind/WindFarmsJune2022_ITM.zip",
                "Extract into data/raw/WindFarms/",
            ],
            "crs": "ITM (EPSG:2157)",
        },
        {
            "name": "Roads — National 250k Map of Ireland",
            "url": "https://data.gov.ie/dataset/roads-national-250k-map-of-ireland1",
            "steps": [
                "Visit the URL above and click the shapefile download",
                "Extract into data/raw/roads/",
            ],
            "crs": "ITM (EPSG:2157)",
        },
        {
            "name": "SRTM Digital Elevation Model",
            "url": "https://earthexplorer.usgs.gov/",
            "steps": [
                "Create a free USGS EarthExplorer account",
                "Search for SRTM 1 Arc-Second tiles covering Ireland",
                "  (approx. tiles: N51W011 to N55W006)",
                "Download .hgt files and place in data/raw/DEM/",
                "Note: rasterio is needed to process these tiles",
            ],
            "crs": "WGS84 (EPSG:4326), heights in metres",
        },
    ]

    for i, item in enumerate(instructions, 1):
        print(f"  {i}. {item['name']}")
        print(f"     URL: {item['url']}")
        print(f"     CRS: {item['crs']}")
        for step in item["steps"]:
            print(f"     - {step}")
        print()

    print("=" * 70)
    print("After downloading, run the app with 'Use demo data' unchecked.")
    print("The app will automatically detect and load real datasets.")
    print("=" * 70)


if __name__ == "__main__":
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print_instructions()
