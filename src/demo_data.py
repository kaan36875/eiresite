"""Generate synthetic demo data for Ireland site assessment.

Grid convention: yy=0 maps to NORTH (low row index = northern points via
_sample_raster row-flip), yy=1 maps to SOUTH. xx=0 is west, xx=1 is east.
"""

import warnings
import numpy as np
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon, MultiPolygon, LineString, box
from shapely.ops import unary_union
from scipy.ndimage import gaussian_filter

from config import CRS_WGS84, CRS_ITM


def _get_ireland_boundary() -> gpd.GeoDataFrame:
    """Republic of Ireland boundary only (excludes Northern Ireland)."""
    from pathlib import Path
    boundary_file = Path(__file__).resolve().parent.parent / "data" / "roi_boundary.geojson"
    if boundary_file.exists():
        gdf = gpd.read_file(boundary_file)
        if gdf.crs != CRS_WGS84:
            gdf = gdf.to_crs(CRS_WGS84)
        return gdf[["geometry"]]

    # Simplified Republic of Ireland coastline + NI border
    # Clockwise from southeast coast, tracing coast, then NI border
    coords = [
        # SE coast (Wexford → Dublin)
        (-6.21, 52.24), (-5.97, 52.78), (-6.13, 53.20),
        # Dublin coast → Dundalk
        (-6.10, 53.35), (-6.05, 53.55), (-6.18, 54.04),
        # NI border (Carlingford → Lough Foyle)
        (-6.33, 54.10), (-6.60, 54.15), (-6.88, 54.18),
        (-7.15, 54.15), (-7.35, 54.22), (-7.50, 54.33),
        (-7.45, 54.45), (-7.40, 54.65), (-7.32, 54.83),
        (-7.05, 54.98),
        # Inishowen peninsula (Donegal, Republic)
        (-6.95, 55.15), (-7.20, 55.30), (-7.55, 55.38),
        # Donegal west coast
        (-7.90, 55.20), (-8.30, 55.17), (-8.62, 54.47),
        # West coast (Mayo → Galway → Clare → Kerry)
        (-9.90, 54.18), (-9.63, 53.88), (-10.11, 53.54),
        (-9.98, 53.27), (-9.85, 52.75), (-9.72, 52.35),
        (-10.22, 52.05), (-10.35, 51.80),
        # South coast (Kerry → Cork → Waterford)
        (-9.77, 51.47), (-9.41, 51.42), (-8.15, 51.59),
        (-7.58, 51.80), (-6.96, 52.26),
        (-6.21, 52.24),  # close
    ]
    poly = Polygon(coords)
    return gpd.GeoDataFrame(geometry=[poly], crs=CRS_WGS84)


def _random_polygons_within(boundary_geom, n, avg_radius_m, rng):
    minx, miny, maxx, maxy = boundary_geom.bounds
    polys = []
    attempts = 0
    while len(polys) < n and attempts < n * 20:
        attempts += 1
        cx = rng.uniform(minx, maxx)
        cy = rng.uniform(miny, maxy)
        r = rng.uniform(avg_radius_m * 0.3, avg_radius_m * 1.7)
        n_verts = rng.integers(5, 12)
        angles = np.sort(rng.uniform(0, 2 * np.pi, n_verts))
        radii = r * rng.uniform(0.6, 1.0, n_verts)
        pts = [(cx + ri * np.cos(a), cy + ri * np.sin(a))
               for a, ri in zip(angles, radii)]
        pts.append(pts[0])
        p = Polygon(pts)
        if p.is_valid and boundary_geom.contains(p.centroid):
            polys.append(p)
    return polys


def _random_points_within(boundary_geom, n, rng):
    minx, miny, maxx, maxy = boundary_geom.bounds
    pts = []
    while len(pts) < n:
        x = rng.uniform(minx, maxx)
        y = rng.uniform(miny, maxy)
        p = Point(x, y)
        if boundary_geom.contains(p):
            pts.append(p)
    return pts


def generate_ireland_boundary() -> gpd.GeoDataFrame:
    gdf = _get_ireland_boundary()
    return gdf.to_crs(CRS_ITM)


def generate_flood_zones(boundary_itm: gpd.GeoDataFrame, seed=42) -> gpd.GeoDataFrame:
    rng = np.random.default_rng(seed)
    boundary_geom = boundary_itm.union_all()
    polys = _random_polygons_within(boundary_geom, n=150, avg_radius_m=4000, rng=rng)
    probabilities = rng.choice(["High", "Medium", "Low"], size=len(polys), p=[0.3, 0.4, 0.3])
    return gpd.GeoDataFrame(
        {"probability": probabilities, "geometry": polys},
        crs=CRS_ITM,
    )


def generate_protected_areas(boundary_itm: gpd.GeoDataFrame, seed=43) -> gpd.GeoDataFrame:
    rng = np.random.default_rng(seed)
    boundary_geom = boundary_itm.union_all()
    polys = _random_polygons_within(boundary_geom, n=120, avg_radius_m=6000, rng=rng)
    types = rng.choice(["SAC", "SPA", "NHA"], size=len(polys), p=[0.4, 0.35, 0.25])
    names = [f"Demo {t} {i+1}" for i, t in enumerate(types)]
    return gpd.GeoDataFrame(
        {"designation": types, "site_name": names, "geometry": polys},
        crs=CRS_ITM,
    )


def generate_substations(boundary_itm: gpd.GeoDataFrame, seed=44) -> gpd.GeoDataFrame:
    rng = np.random.default_rng(seed)
    boundary_geom = boundary_itm.union_all()
    pts = _random_points_within(boundary_geom, n=45, rng=rng)
    voltages = rng.choice(["400kV", "220kV", "110kV"], size=len(pts), p=[0.1, 0.3, 0.6])
    names = [f"Substation {i+1}" for i in range(len(pts))]
    return gpd.GeoDataFrame(
        {"name": names, "voltage": voltages, "geometry": pts},
        crs=CRS_ITM,
    )


def generate_settlements(boundary_itm: gpd.GeoDataFrame, seed=50) -> gpd.GeoDataFrame:
    rng = np.random.default_rng(seed)
    boundary_geom = boundary_itm.union_all()
    pts = _random_points_within(boundary_geom, n=200, rng=rng)
    pop = rng.choice(
        ["City", "Town", "Village"],
        size=len(pts),
        p=[0.05, 0.25, 0.70],
    )
    names = [f"{t} {i+1}" for i, t in enumerate(pop)]
    return gpd.GeoDataFrame(
        {"name": names, "settlement_type": pop, "geometry": pts},
        crs=CRS_ITM,
    )


def generate_roads(boundary_itm: gpd.GeoDataFrame, seed=45) -> gpd.GeoDataFrame:
    rng = np.random.default_rng(seed)
    boundary_geom = boundary_itm.union_all()
    minx, miny, maxx, maxy = boundary_geom.bounds

    lines = []
    road_types = []

    n_horizontal = 12
    for i in range(n_horizontal):
        y = miny + (maxy - miny) * (i + 1) / (n_horizontal + 1)
        n_pts = rng.integers(8, 15)
        xs = np.sort(rng.uniform(minx, maxx, n_pts))
        ys = y + rng.normal(0, 3000, n_pts)
        coords = list(zip(xs, ys))
        line = LineString(coords).intersection(boundary_geom)
        if not line.is_empty:
            if line.geom_type == "MultiLineString":
                for part in line.geoms:
                    if part.length > 5000:
                        lines.append(part)
                        road_types.append(rng.choice(["Motorway", "National", "Regional"]))
            elif line.length > 5000:
                lines.append(line)
                road_types.append(rng.choice(["Motorway", "National", "Regional"]))

    n_vertical = 8
    for i in range(n_vertical):
        x = minx + (maxx - minx) * (i + 1) / (n_vertical + 1)
        n_pts = rng.integers(8, 15)
        ys = np.sort(rng.uniform(miny, maxy, n_pts))
        xs = x + rng.normal(0, 3000, n_pts)
        coords = list(zip(xs, ys))
        line = LineString(coords).intersection(boundary_geom)
        if not line.is_empty:
            if line.geom_type == "MultiLineString":
                for part in line.geoms:
                    if part.length > 5000:
                        lines.append(part)
                        road_types.append(rng.choice(["Motorway", "National", "Regional"]))
            elif line.length > 5000:
                lines.append(line)
                road_types.append(rng.choice(["Motorway", "National", "Regional"]))

    return gpd.GeoDataFrame(
        {"road_type": road_types[:len(lines)], "geometry": lines},
        crs=CRS_ITM,
    )


def _make_grid_info(boundary_itm, resolution_m):
    boundary_geom = boundary_itm.union_all()
    minx, miny, maxx, maxy = boundary_geom.bounds
    cols = int((maxx - minx) / resolution_m)
    rows = int((maxy - miny) / resolution_m)
    y_coords = np.linspace(0, 1, rows)
    x_coords = np.linspace(0, 1, cols)
    xx, yy = np.meshgrid(x_coords, y_coords)
    info = {
        "minx": minx, "miny": miny, "maxx": maxx, "maxy": maxy,
        "resolution": resolution_m, "rows": rows, "cols": cols,
    }
    return rows, cols, xx, yy, info


def generate_elevation_grid(
    boundary_itm: gpd.GeoDataFrame, resolution_m=1000, seed=46
) -> tuple[np.ndarray, dict]:
    rng = np.random.default_rng(seed)
    rows, cols, xx, yy, info = _make_grid_info(boundary_itm, resolution_m)

    # yy=0 → NORTH, yy=1 → SOUTH. xx=0 → WEST, xx=1 → EAST.
    base = rng.uniform(10, 40, (rows, cols))

    # MacGillycuddy's Reeks (Kerry, SW) — highest point ~1041m
    kerry = 900 * np.exp(-((xx - 0.18)**2 / 0.004 + (yy - 0.85)**2 / 0.006))
    # Connemara / Twelve Bens (W, mid-latitude)
    connemara = 600 * np.exp(-((xx - 0.12)**2 / 0.005 + (yy - 0.55)**2 / 0.005))
    # Wicklow Mountains (E, south of Dublin)
    wicklow = 700 * np.exp(-((xx - 0.72)**2 / 0.006 + (yy - 0.72)**2 / 0.008))
    # Donegal highlands (NW)
    donegal = 550 * np.exp(-((xx - 0.25)**2 / 0.005 + (yy - 0.18)**2 / 0.006))
    # Galtee Mountains (S central)
    galtee = 500 * np.exp(-((xx - 0.40)**2 / 0.004 + (yy - 0.80)**2 / 0.004))
    # Central lowlands depression
    central_low = -20 * np.exp(-((xx - 0.45)**2 / 0.10 + (yy - 0.50)**2 / 0.10))

    elevation = base + kerry + connemara + wicklow + donegal + galtee + central_low
    elevation = gaussian_filter(elevation, sigma=1.5)
    elevation = np.clip(elevation, 0, 1041)

    return elevation.astype(np.float32), info


def generate_slope_grid(
    boundary_itm: gpd.GeoDataFrame, resolution_m=1000, seed=49
) -> tuple[np.ndarray, dict]:
    """Pre-computed slope in degrees, matching elevation terrain."""
    rng = np.random.default_rng(seed)
    rows, cols, xx, yy, info = _make_grid_info(boundary_itm, resolution_m)

    # Central lowlands: mostly flat (1-4 degrees)
    base = rng.uniform(1, 4, (rows, cols))

    # Mountain areas: steep slopes (15-35 degrees) — same positions as elevation
    kerry = 25 * np.exp(-((xx - 0.18)**2 / 0.006 + (yy - 0.85)**2 / 0.008))
    connemara = 20 * np.exp(-((xx - 0.12)**2 / 0.007 + (yy - 0.55)**2 / 0.007))
    wicklow = 22 * np.exp(-((xx - 0.72)**2 / 0.008 + (yy - 0.72)**2 / 0.010))
    donegal = 18 * np.exp(-((xx - 0.25)**2 / 0.007 + (yy - 0.18)**2 / 0.008))
    galtee = 16 * np.exp(-((xx - 0.40)**2 / 0.006 + (yy - 0.80)**2 / 0.006))

    # Hilly areas along west coast
    west_hills = 8 * np.exp(-((xx - 0.05)**2 / 0.02))
    east_coast = 3 * np.exp(-((xx - 0.85)**2 / 0.02))

    slope = base + kerry + connemara + wicklow + donegal + galtee + west_hills + east_coast
    slope = gaussian_filter(slope, sigma=1.5)
    slope = np.clip(slope, 0, 45).astype(np.float32)

    return slope, info


def generate_wind_speed_grid(
    boundary_itm: gpd.GeoDataFrame, resolution_m=1000, seed=47
) -> tuple[np.ndarray, dict]:
    """Mean wind speed at 100m height (m/s). Ireland range: ~5-10 m/s."""
    rng = np.random.default_rng(seed)
    rows, cols, xx, yy, info = _make_grid_info(boundary_itm, resolution_m)

    # West coast / Atlantic exposure = high wind
    west_gradient = 2.5 * np.exp(-((xx - 0.0)**2 / 0.12))
    # Northwest coast strongest (Donegal, Mayo)
    nw_boost = 1.5 * np.exp(-((xx - 0.10)**2 / 0.04 + (yy - 0.20)**2 / 0.06))
    # Hilltop boost (correlated with elevation areas)
    hill_boost = 1.0 * np.exp(-((xx - 0.18)**2 / 0.01 + (yy - 0.85)**2 / 0.01))
    # Midlands sheltered
    midlands_dip = -1.5 * np.exp(-((xx - 0.50)**2 / 0.06 + (yy - 0.55)**2 / 0.06))
    noise = rng.normal(0, 0.3, (rows, cols))

    wind = 6.5 + west_gradient + nw_boost + hill_boost + midlands_dip + noise
    wind = gaussian_filter(wind, sigma=2)
    wind = np.clip(wind, 4.5, 10.5).astype(np.float32)

    return wind, info


def generate_solar_irradiance_grid(
    boundary_itm: gpd.GeoDataFrame, resolution_m=1000, seed=48
) -> tuple[np.ndarray, dict]:
    """Global horizontal irradiance (kWh/m2/year). Ireland range: ~900-1100."""
    rng = np.random.default_rng(seed)
    rows, cols, xx, yy, info = _make_grid_info(boundary_itm, resolution_m)

    # South gets more sun (yy=1 is south → high yy = more sun)
    latitude_effect = 120 * (yy - 0.5)
    # Southeast best (Wexford/Waterford area)
    se_boost = 60 * np.exp(-((xx - 0.75)**2 / 0.06 + (yy - 0.82)**2 / 0.04))
    # West coast cloudier
    west_cloud = -50 * np.exp(-((xx - 0.0)**2 / 0.08))
    noise = rng.normal(0, 10, (rows, cols))

    ghi = 1000 + latitude_effect + se_boost + west_cloud + noise
    ghi = gaussian_filter(ghi, sigma=2)
    ghi = np.clip(ghi, 850, 1150).astype(np.float32)

    return ghi, info


def generate_all_demo_data() -> dict:
    boundary = generate_ireland_boundary()
    elevation, elev_info = generate_elevation_grid(boundary, resolution_m=1000)
    slope, slope_info = generate_slope_grid(boundary, resolution_m=1000)
    wind_speed, wind_info = generate_wind_speed_grid(boundary, resolution_m=1000)
    solar_ghi, solar_info = generate_solar_irradiance_grid(boundary, resolution_m=1000)
    return {
        "boundary": boundary,
        "flood_zones": generate_flood_zones(boundary),
        "protected_areas": generate_protected_areas(boundary),
        "substations": generate_substations(boundary),
        "settlements": generate_settlements(boundary),
        "roads": generate_roads(boundary),
        "elevation": elevation,
        "elevation_info": elev_info,
        "slope": slope,
        "slope_info": slope_info,
        "wind_speed": wind_speed,
        "wind_info": wind_info,
        "solar_ghi": solar_ghi,
        "solar_info": solar_info,
    }
