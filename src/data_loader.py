"""Load real or demo geospatial data for Ireland site assessment."""

import geopandas as gpd
import numpy as np
import pandas as pd
from pathlib import Path

from config import RAW_DIR, CRS_ITM
from src.demo_data import generate_all_demo_data


def _try_load_shapefile(directory: Path, pattern: str) -> gpd.GeoDataFrame | None:
    matches = list(directory.glob(pattern))
    if not matches:
        return None
    gdf = gpd.read_file(matches[0])
    if gdf.crs and gdf.crs != CRS_ITM:
        gdf = gdf.to_crs(CRS_ITM)
    return gdf


def load_data(use_demo: bool = True) -> dict:
    if not use_demo and RAW_DIR.exists():
        return _load_real_data()
    return generate_all_demo_data()


def _load_real_data() -> dict:
    demo = generate_all_demo_data()
    data = {}

    data["boundary"] = demo["boundary"]

    flood = _try_load_shapefile(RAW_DIR, "**/NIFM*Current*/*.shp")
    data["flood_zones"] = flood if flood is not None else demo["flood_zones"]

    sac = _try_load_shapefile(RAW_DIR, "**/SAC*/*.shp")
    spa = _try_load_shapefile(RAW_DIR, "**/SPA*/*.shp")
    nha = _try_load_shapefile(RAW_DIR, "**/NHA*/*.shp")

    parts = []
    for gdf, designation in [(sac, "SAC"), (spa, "SPA"), (nha, "NHA")]:
        if gdf is not None:
            gdf = gdf.copy()
            gdf["designation"] = designation
            if "SITE_NAME" in gdf.columns:
                gdf = gdf.rename(columns={"SITE_NAME": "site_name"})
            elif "site_name" not in gdf.columns:
                gdf["site_name"] = designation
            parts.append(gdf[["designation", "site_name", "geometry"]])

    data["protected_areas"] = (
        gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=CRS_ITM)
        if parts else demo["protected_areas"]
    )

    wind = _try_load_shapefile(RAW_DIR, "**/WindFarm*/*.shp")
    if wind is not None:
        wind = wind.copy()
        if "Name" in wind.columns:
            wind = wind.rename(columns={"Name": "name"})
        wind["voltage"] = "110kV"
        data["substations"] = wind[["name", "voltage", "geometry"]]
    else:
        data["substations"] = demo["substations"]

    roads = _try_load_shapefile(RAW_DIR, "**/road*/*.shp")
    if roads is not None:
        roads = roads.copy()
        if "ROAD_CLASS" in roads.columns:
            roads = roads.rename(columns={"ROAD_CLASS": "road_type"})
        elif "road_type" not in roads.columns:
            roads["road_type"] = "National"
        data["roads"] = roads[["road_type", "geometry"]]
    else:
        data["roads"] = demo["roads"]

    data["settlements"] = demo["settlements"]
    data["elevation"] = demo["elevation"]
    data["elevation_info"] = demo["elevation_info"]
    data["wind_speed"] = demo["wind_speed"]
    data["wind_info"] = demo["wind_info"]
    data["solar_ghi"] = demo["solar_ghi"]
    data["solar_info"] = demo["solar_info"]

    return data
