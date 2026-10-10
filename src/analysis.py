"""Two-phase multi-criteria site suitability analysis engine.

Phase 1 — Hard constraints: protected areas (SAC/SPA), high flood risk,
          excessive slope, and minimum settlement distance eliminate cells.
Phase 2 — Weighted scoring: remaining cells scored on resource potential,
          grid proximity, road access, slope quality, and settlement buffer.
"""

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box, Point
from scipy.spatial import cKDTree

from config import (
    CRS_ITM,
    MAX_GRID_DISTANCE_KM,
    MAX_ROAD_DISTANCE_KM,
    MAX_SETTLEMENT_DISTANCE_KM,
    ENERGY_TYPES,
)


def create_analysis_grid(
    boundary: gpd.GeoDataFrame, resolution_km: float = 5
) -> gpd.GeoDataFrame:
    res = resolution_km * 1000
    boundary_geom = boundary.to_crs(CRS_ITM).union_all()
    minx, miny, maxx, maxy = boundary_geom.bounds

    xs = np.arange(minx, maxx, res)
    ys = np.arange(miny, maxy, res)

    centroids = []
    cells = []
    land_fractions = []
    for x in xs:
        for y in ys:
            cx, cy = x + res / 2, y + res / 2
            pt = Point(cx, cy)
            cell = box(x, y, x + res, y + res)
            if boundary_geom.contains(pt):
                land_area = cell.intersection(boundary_geom).area
                land_frac = land_area / cell.area
                if land_frac >= 0.5:
                    centroids.append(pt)
                    cells.append(cell)
                    land_fractions.append(round(land_frac, 2))

    grid = gpd.GeoDataFrame(
        {"centroid_x": [c.x for c in centroids],
         "centroid_y": [c.y for c in centroids],
         "land_fraction": land_fractions,
         "geometry": cells},
        crs=CRS_ITM,
    )
    return grid


# ---------------------------------------------------------------------------
# Phase 1 — Hard constraint checks (return boolean masks)
# ---------------------------------------------------------------------------

def check_protected_areas(
    grid: gpd.GeoDataFrame, protected: gpd.GeoDataFrame
) -> np.ndarray:
    """True = excluded (overlaps SAC or SPA)."""
    excluded = np.zeros(len(grid), dtype=bool)
    if protected.empty:
        return excluded

    statutory = protected[protected["designation"].isin(["SAC", "SPA"])]
    if statutory.empty:
        return excluded

    joined = gpd.sjoin(grid, statutory, how="left", predicate="intersects")
    hit_indices = joined.dropna(subset=["index_right"]).index.unique()
    excluded[grid.index.isin(hit_indices)] = True
    return excluded


def check_flood_exclusion(
    grid: gpd.GeoDataFrame, flood_zones: gpd.GeoDataFrame
) -> np.ndarray:
    """True = excluded (overlaps high-probability flood zone)."""
    excluded = np.zeros(len(grid), dtype=bool)
    if flood_zones.empty:
        return excluded

    high_flood = flood_zones[flood_zones["probability"] == "High"]
    if high_flood.empty:
        return excluded

    joined = gpd.sjoin(grid, high_flood, how="left", predicate="intersects")
    hit_indices = joined.dropna(subset=["index_right"]).index.unique()
    excluded[grid.index.isin(hit_indices)] = True
    return excluded


def check_slope_exclusion(
    grid: gpd.GeoDataFrame,
    data: dict,
    energy_type: str,
) -> np.ndarray:
    """True = excluded (slope exceeds absolute maximum for energy type)."""
    slopes = _compute_cell_slopes(grid, data)
    max_slope = ENERGY_TYPES[energy_type]["max_slope"]
    return slopes > max_slope


def check_settlement_exclusion(
    grid: gpd.GeoDataFrame,
    settlements: gpd.GeoDataFrame,
    energy_type: str,
) -> np.ndarray:
    """True = excluded (too close to settlements)."""
    excluded = np.zeros(len(grid), dtype=bool)
    if settlements.empty:
        return excluded

    min_dist = ENERGY_TYPES[energy_type]["min_settlement_m"]
    grid_coords = np.column_stack([grid["centroid_x"], grid["centroid_y"]])
    pt_coords = np.column_stack([settlements.geometry.x, settlements.geometry.y])
    tree = cKDTree(pt_coords)
    distances, _ = tree.query(grid_coords, k=1)
    excluded = distances < min_dist
    return excluded


# ---------------------------------------------------------------------------
# Phase 2 — Scoring functions (0–100, higher = more suitable)
# ---------------------------------------------------------------------------

def _sample_raster(grid: gpd.GeoDataFrame, raster: np.ndarray, info: dict) -> np.ndarray:
    res = info["resolution"]
    minx, miny = info["minx"], info["miny"]
    rows, cols = raster.shape
    col_idx = np.clip(((grid["centroid_x"].values - minx) / res).astype(int), 0, cols - 1)
    row_idx = np.clip(((grid["centroid_y"].values - miny) / res).astype(int), 0, rows - 1)
    row_idx = np.clip(rows - 1 - row_idx, 0, rows - 1)
    return raster[row_idx, col_idx]


def _compute_cell_slopes(
    grid: gpd.GeoDataFrame, data: dict
) -> np.ndarray:
    if "slope" in data:
        return _sample_raster(grid, data["slope"], data["slope_info"])
    elevation = data["elevation"]
    elev_info = data["elevation_info"]
    res = elev_info["resolution"]
    dy, dx = np.gradient(elevation, res)
    slope_deg = np.degrees(np.arctan(np.sqrt(dx**2 + dy**2)))
    return _sample_raster(grid, slope_deg, elev_info)


def score_resource(
    grid: gpd.GeoDataFrame,
    data: dict,
    energy_type: str,
) -> np.ndarray:
    """Score based on wind speed or solar irradiance."""
    if energy_type == "wind":
        wind = data["wind_speed"]
        info = data["wind_info"]
        values = _sample_raster(grid, wind, info)
        # 5 m/s = below viable (0), 7.5 m/s = good (50), 10 m/s = excellent (100)
        scores = np.clip((values - 5.0) / 5.0, 0, 1) * 100
    else:
        ghi = data["solar_ghi"]
        info = data["solar_info"]
        values = _sample_raster(grid, ghi, info)
        # 900 kWh = poor (0), 1000 = acceptable (50), 1100+ = excellent (100)
        scores = np.clip((values - 900) / 200, 0, 1) * 100
    return scores


def score_flood_risk(
    grid: gpd.GeoDataFrame, flood_zones: gpd.GeoDataFrame
) -> np.ndarray:
    """Score medium/low flood risk (high already excluded in Phase 1)."""
    scores = np.full(len(grid), 100.0)
    if flood_zones.empty:
        return scores

    non_high = flood_zones[flood_zones["probability"] != "High"]
    if non_high.empty:
        return scores

    joined = gpd.sjoin(grid, non_high, how="left", predicate="intersects")
    penalty = {"Medium": 40, "Low": 15}
    hit = joined.dropna(subset=["index_right"])
    if hit.empty:
        return scores

    worst = (
        hit.assign(pen=hit["probability"].map(penalty).fillna(20))
        .groupby(hit.index)["pen"]
        .max()
    )
    scores[worst.index] = np.clip(100 - worst.values, 0, 100)
    return scores


def score_distance_to_points(
    grid: gpd.GeoDataFrame,
    points: gpd.GeoDataFrame,
    max_distance_km: float,
) -> np.ndarray:
    if points.empty:
        return np.full(len(grid), 50.0)

    max_dist = max_distance_km * 1000
    grid_coords = np.column_stack([grid["centroid_x"], grid["centroid_y"]])
    pt_coords = np.column_stack([points.geometry.x, points.geometry.y])
    tree = cKDTree(pt_coords)
    distances, _ = tree.query(grid_coords, k=1)
    scores = np.clip(1.0 - distances / max_dist, 0, 1) * 100
    return scores


def score_distance_to_lines(
    grid: gpd.GeoDataFrame,
    lines: gpd.GeoDataFrame,
    max_distance_km: float,
    sample_interval_m: float = 2000,
) -> np.ndarray:
    if lines.empty:
        return np.full(len(grid), 50.0)

    max_dist = max_distance_km * 1000

    sample_points = []
    for geom in lines.geometry:
        if geom is None or geom.is_empty:
            continue
        length = geom.length
        n_samples = max(2, int(length / sample_interval_m))
        for frac in np.linspace(0, 1, n_samples):
            pt = geom.interpolate(frac, normalized=True)
            sample_points.append([pt.x, pt.y])

    if not sample_points:
        return np.full(len(grid), 50.0)

    sample_arr = np.array(sample_points)
    grid_coords = np.column_stack([grid["centroid_x"], grid["centroid_y"]])
    tree = cKDTree(sample_arr)
    distances, _ = tree.query(grid_coords, k=1)
    scores = np.clip(1.0 - distances / max_dist, 0, 1) * 100
    return scores


def score_slope(
    grid: gpd.GeoDataFrame,
    data: dict,
    energy_type: str = "solar",
) -> np.ndarray:
    config = ENERGY_TYPES[energy_type]
    ideal_min = config["ideal_slope_min"]
    ideal_max = config["ideal_slope_max"]
    max_slope = config["max_slope"]

    cell_slopes = _compute_cell_slopes(grid, data)

    scores = np.zeros(len(grid))
    in_ideal = (cell_slopes >= ideal_min) & (cell_slopes <= ideal_max)
    scores[in_ideal] = 100.0

    above_ideal = (cell_slopes > ideal_max) & (cell_slopes <= max_slope)
    if above_ideal.any():
        scores[above_ideal] = 100 * (1 - (cell_slopes[above_ideal] - ideal_max) / (max_slope - ideal_max))

    scores[cell_slopes > max_slope] = 0.0
    return np.clip(scores, 0, 100)


def score_settlement_distance(
    grid: gpd.GeoDataFrame,
    settlements: gpd.GeoDataFrame,
    energy_type: str,
) -> np.ndarray:
    """Further from settlements = better (above the minimum exclusion distance)."""
    if settlements.empty:
        return np.full(len(grid), 50.0)

    min_dist = ENERGY_TYPES[energy_type]["min_settlement_m"]
    max_dist = MAX_SETTLEMENT_DISTANCE_KM * 1000

    grid_coords = np.column_stack([grid["centroid_x"], grid["centroid_y"]])
    pt_coords = np.column_stack([settlements.geometry.x, settlements.geometry.y])
    tree = cKDTree(pt_coords)
    distances, _ = tree.query(grid_coords, k=1)

    # Score: at min_dist → 50 (acceptable), further → higher, very far → diminishing
    normed = np.clip((distances - min_dist) / (max_dist - min_dist), 0, 1)
    scores = 50 + 50 * normed
    return np.clip(scores, 0, 100)


# ---------------------------------------------------------------------------
# Main analysis pipeline
# ---------------------------------------------------------------------------

def run_analysis(
    grid: gpd.GeoDataFrame,
    data: dict,
    weights: dict,
    energy_type: str = "solar",
) -> gpd.GeoDataFrame:
    result = grid.copy()

    # Phase 1 — Hard exclusions
    excl_protected = check_protected_areas(grid, data["protected_areas"])
    excl_flood = check_flood_exclusion(grid, data["flood_zones"])
    excl_slope = check_slope_exclusion(grid, data, energy_type)
    excl_settlement = check_settlement_exclusion(
        grid, data["settlements"], energy_type
    )

    excluded = excl_protected | excl_flood | excl_slope | excl_settlement
    result["excluded"] = excluded

    reason = []
    for i in range(len(grid)):
        reasons = []
        if excl_protected[i]:
            reasons.append("Protected area")
        if excl_flood[i]:
            reasons.append("High flood risk")
        if excl_slope[i]:
            reasons.append("Excessive slope")
        if excl_settlement[i]:
            reasons.append("Too close to settlement")
        reason.append("; ".join(reasons) if reasons else "")
    result["exclusion_reason"] = reason

    # Phase 2 — Score only non-excluded cells
    viable_idx = grid.index[~excluded]
    viable = grid.loc[viable_idx].copy().reset_index(drop=True)

    if viable.empty:
        result["resource_score"] = 0.0
        result["flood_score"] = 0.0
        result["grid_dist_score"] = 0.0
        result["road_dist_score"] = 0.0
        result["slope_score"] = 0.0
        result["settlement_score"] = 0.0
        result["suitability"] = 0.0
        result["category"] = "Excluded"
        return result

    resource_scores = score_resource(viable, data, energy_type)
    flood_scores = score_flood_risk(viable, data["flood_zones"])
    grid_dist_scores = score_distance_to_points(
        viable, data["substations"], MAX_GRID_DISTANCE_KM
    )
    road_dist_scores = score_distance_to_lines(
        viable, data["roads"], MAX_ROAD_DISTANCE_KM
    )
    slope_scores = score_slope(viable, data, energy_type)
    settlement_scores = score_settlement_distance(
        viable, data["settlements"], energy_type
    )

    result["resource_score"] = 0.0
    result["flood_score"] = 0.0
    result["grid_dist_score"] = 0.0
    result["road_dist_score"] = 0.0
    result["slope_score"] = 0.0
    result["settlement_score"] = 0.0

    result.loc[viable_idx, "resource_score"] = resource_scores
    result.loc[viable_idx, "flood_score"] = flood_scores
    result.loc[viable_idx, "grid_dist_score"] = grid_dist_scores
    result.loc[viable_idx, "road_dist_score"] = road_dist_scores
    result.loc[viable_idx, "slope_score"] = slope_scores
    result.loc[viable_idx, "settlement_score"] = settlement_scores

    score_cols = {
        "resource": "resource_score",
        "grid_distance": "grid_dist_score",
        "road_distance": "road_dist_score",
        "slope": "slope_score",
        "settlement_distance": "settlement_score",
    }

    total_weight = sum(weights[k] for k in score_cols)
    result["suitability"] = 0.0
    if total_weight > 0:
        result.loc[viable_idx, "suitability"] = sum(
            (weights[k] / total_weight) * result.loc[viable_idx, col]
            for k, col in score_cols.items()
        ).round(1)

    bins = [-0.1, 20, 40, 60, 80, 100.1]
    labels = ["Very Low", "Low", "Medium", "High", "Very High"]
    result["category"] = ""
    result.loc[excluded, "category"] = "Excluded"
    if not viable.empty:
        result.loc[viable_idx, "category"] = pd.cut(
            result.loc[viable_idx, "suitability"],
            bins=bins,
            labels=labels,
        )

    return result


def select_top_diverse(
    results: gpd.GeoDataFrame, n: int = 10, min_distance_km: float = 15
) -> gpd.GeoDataFrame:
    """Select top-N areas with minimum spacing to avoid clustering."""
    viable = results[~results["excluded"]].copy()
    if viable.empty:
        return viable

    sorted_viable = viable.sort_values("suitability", ascending=False)
    min_dist_m = min_distance_km * 1000

    selected_indices = []
    selected_coords = []

    for idx, row in sorted_viable.iterrows():
        cx, cy = row["centroid_x"], row["centroid_y"]
        too_close = False
        for sx, sy in selected_coords:
            dist = np.sqrt((cx - sx)**2 + (cy - sy)**2)
            if dist < min_dist_m:
                too_close = True
                break
        if not too_close:
            selected_indices.append(idx)
            selected_coords.append((cx, cy))
            if len(selected_indices) >= n:
                break

    return results.loc[selected_indices]
