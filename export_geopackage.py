"""Export analysis results to GeoPackage (SQLite-based spatial database).

Demonstrates spatial SQL queries on site suitability data.
Can be consumed by QGIS, Power BI, or any SQLite-capable tool.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import geopandas as gpd

from config import PROCESSED_DIR, DEFAULT_WEIGHTS
from src.data_loader import load_data
from src.analysis import create_analysis_grid, run_analysis


def export(energy_type: str = "solar", resolution_km: float = 5):
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    gpkg_path = PROCESSED_DIR / "ireland_site_assessment.gpkg"

    print("Loading data...")
    data = load_data(use_demo=True)

    print(f"Creating {resolution_km}km grid...")
    grid = create_analysis_grid(data["boundary"], resolution_km)

    print(f"Running {energy_type} analysis...")
    results = run_analysis(grid, data, DEFAULT_WEIGHTS, energy_type)

    print(f"Writing GeoPackage to {gpkg_path}")
    results.to_file(gpkg_path, layer="suitability_grid", driver="GPKG")
    data["flood_zones"].to_file(gpkg_path, layer="flood_zones", driver="GPKG")
    data["protected_areas"].to_file(gpkg_path, layer="protected_areas", driver="GPKG")
    data["substations"].to_file(gpkg_path, layer="substations", driver="GPKG")
    data["settlements"].to_file(gpkg_path, layer="settlements", driver="GPKG")
    data["roads"].to_file(gpkg_path, layer="roads", driver="GPKG")
    data["boundary"].to_file(gpkg_path, layer="boundary", driver="GPKG")

    excluded = results[results["excluded"]]
    viable = results[~results["excluded"]]
    print(f"\nResults: {len(results)} total, {len(excluded)} excluded, {len(viable)} viable")

    print()
    print("GeoPackage created. Example SQL queries:")
    print()
    print("-- Top 10 most suitable viable cells")
    print("SELECT suitability, category, resource_score, flood_score,")
    print("       grid_dist_score, road_dist_score, slope_score, settlement_score")
    print("FROM suitability_grid")
    print("WHERE excluded = 0")
    print("ORDER BY suitability DESC LIMIT 10;")
    print()
    print("-- Exclusion reason breakdown")
    print("SELECT exclusion_reason, COUNT(*) as n")
    print("FROM suitability_grid")
    print("WHERE excluded = 1")
    print("GROUP BY exclusion_reason ORDER BY n DESC;")
    print()
    print(f"Open in QGIS, Power BI, or DB Browser for SQLite: {gpkg_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Export site assessment to GeoPackage")
    parser.add_argument("--energy", choices=["solar", "wind"], default="solar")
    parser.add_argument("--resolution", type=float, default=5)
    args = parser.parse_args()
    export(args.energy, args.resolution)
