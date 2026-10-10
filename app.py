"""Ireland Renewable Energy Site Suitability Assessment — Streamlit Dashboard."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
import folium
import geopandas as gpd
import numpy as np
import pandas as pd
from branca.colormap import LinearColormap
from streamlit_folium import st_folium

from config import (
    DEFAULT_WEIGHTS,
    ENERGY_TYPES,
    GRID_RESOLUTION_KM,
    DATA_SOURCES,
    CRS_WGS84,
    CARTO_TILE_URL,
)
from src.data_loader import load_data
from src.analysis import create_analysis_grid, run_analysis, select_top_diverse
from src.counties import get_counties_bulk

st.set_page_config(
    page_title="ÉireSite",
    page_icon="🗺️",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1rem; }
    .demo-banner {
        background: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 8px;
        padding: 0.6rem 1rem;
        margin-bottom: 1rem;
        font-size: 0.9rem;
        color: #856404;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("ÉireSite")
st.caption("Renewable Energy Site Screening for Ireland — two-phase multi-criteria geospatial analysis")

with st.sidebar:
    st.header("Analysis Parameters")

    energy_type = st.selectbox(
        "Energy Type",
        options=list(ENERGY_TYPES.keys()),
        format_func=lambda x: ENERGY_TYPES[x]["label"],
    )

    st.subheader("Criterion Weights")
    st.caption("Phase 2 scoring weights. Protected areas and high flood risk are hard exclusions in Phase 1.")

    resource_label = "Wind Speed" if energy_type == "wind" else "Solar Irradiance"
    w_resource = st.slider(resource_label, 0, 100, int(DEFAULT_WEIGHTS["resource"] * 100))
    w_grid = st.slider("Grid Proximity", 0, 100, int(DEFAULT_WEIGHTS["grid_distance"] * 100))
    w_road = st.slider("Road Access", 0, 100, int(DEFAULT_WEIGHTS["road_distance"] * 100))
    w_slope = st.slider("Terrain Slope", 0, 100, int(DEFAULT_WEIGHTS["slope"] * 100))
    w_settlement = st.slider("Settlement Distance", 0, 100, int(DEFAULT_WEIGHTS["settlement_distance"] * 100))

    weights = {
        "resource": w_resource,
        "grid_distance": w_grid,
        "road_distance": w_road,
        "slope": w_slope,
        "settlement_distance": w_settlement,
    }

    total_w = sum(weights.values())
    if total_w > 0:
        norm_labels = [f"{k.replace('_', ' ').title()}: {v/total_w*100:.0f}%" for k, v in weights.items()]
        st.caption("Normalised: " + " · ".join(norm_labels))

    st.divider()
    resolution = st.select_slider(
        "Grid Resolution (km)",
        options=[2, 3, 5, 8, 10],
        value=GRID_RESOLUTION_KM,
    )

    use_demo = st.checkbox("Use demo data", value=True)

    run_btn = st.button("Run Analysis", type="primary", use_container_width=True)


@st.cache_data(show_spinner="Loading geospatial data...")
def cached_load_data(_use_demo):
    return load_data(use_demo=_use_demo)


@st.cache_data(show_spinner="Building analysis grid...")
def cached_create_grid(_boundary_wkt, resolution_km):
    import geopandas as gpd
    from shapely import wkt
    from config import CRS_ITM
    boundary = gpd.GeoDataFrame(
        geometry=[wkt.loads(_boundary_wkt)], crs=CRS_ITM
    )
    return create_analysis_grid(boundary, resolution_km)


if run_btn or "results" in st.session_state:
    data = cached_load_data(use_demo)
    boundary_wkt = data["boundary"].union_all().wkt
    grid = cached_create_grid(boundary_wkt, resolution)

    if use_demo:
        st.markdown(
            '<div class="demo-banner">'
            '⚠️ <b>DEMO DATA</b> — Synthetic data for demonstration only. '
            'Spatial patterns are approximate. Uncheck "Use demo data" and download '
            'real datasets for production analysis.'
            '</div>',
            unsafe_allow_html=True,
        )

    if run_btn:
        results = run_analysis(grid, data, weights, energy_type)
        st.session_state["results"] = results
        st.session_state["data"] = data
        st.session_state["weights"] = weights
        st.session_state["energy_type"] = energy_type

    results = st.session_state.get("results")
    data = st.session_state.get("data", data)
    current_energy = st.session_state.get("energy_type", energy_type)

    if results is not None:
        excluded = results[results["excluded"]]
        viable = results[~results["excluded"]]

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total Cells", f"{len(results):,}")
        with col2:
            st.metric("Excluded", f"{len(excluded):,}", delta=f"-{len(excluded)/len(results)*100:.0f}%", delta_color="off")
        with col3:
            st.metric("Viable", f"{len(viable):,}")
        with col4:
            if not viable.empty:
                high_pct = (viable["suitability"] >= 70).sum() / len(viable) * 100
                st.metric("High Suitability", f"{high_pct:.0f}%")
            else:
                st.metric("High Suitability", "N/A")
        with col5:
            if not viable.empty:
                st.metric("Best Score", f"{viable['suitability'].max():.0f}")
            else:
                st.metric("Best Score", "N/A")

        # Exclusion summary
        if not excluded.empty:
            with st.expander(f"Phase 1 — Constraint Screening: {len(excluded)} cells excluded", expanded=False):
                reasons = excluded["exclusion_reason"].str.split("; ").explode().value_counts()
                reason_df = pd.DataFrame({"Reason": reasons.index, "Cells": reasons.values})
                st.dataframe(reason_df, hide_index=True, use_container_width=True)
                st.caption("Cells may be excluded for multiple reasons. SAC/SPA overlap, high flood risk, excessive slope, and settlement proximity are hard constraints.")

        # Prepare coordinate transformer once
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:2157", "EPSG:4326", always_xy=True)

        map_col, chart_col = st.columns([3, 1])

        with map_col:
            st.subheader("Suitability Map")

            center_y = results["centroid_y"].mean()
            center_x = results["centroid_x"].mean()
            center_lon, center_lat = transformer.transform(center_x, center_y)

            m = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=7,
                tiles=CARTO_TILE_URL,
                attr="&copy; CARTO &copy; OpenStreetMap contributors",
            )

            colormap = LinearColormap(
                colors=["#d73027", "#fc8d59", "#fee08b", "#d9ef8b", "#1a9850"],
                vmin=0,
                vmax=100,
                caption="Suitability Score (0–100)",
            )

            centroids_all = gpd.GeoDataFrame(
                geometry=gpd.points_from_xy(results["centroid_x"], results["centroid_y"]),
                crs="EPSG:2157",
            ).to_crs(CRS_WGS84)

            # Draw excluded cells (grey, no popup for performance)
            for idx in excluded.index:
                cpt = centroids_all.geometry.iloc[idx]
                folium.CircleMarker(
                    location=[cpt.y, cpt.x],
                    radius=max(2, resolution * 0.6),
                    color="#999999",
                    fill=True,
                    fill_color="#cccccc",
                    fill_opacity=0.4,
                    weight=0.3,
                ).add_to(m)

            # Draw viable cells (coloured, popup only for top cells)
            top10_df = select_top_diverse(results, n=10, min_distance_km=15) if not viable.empty else pd.DataFrame()
            top10_indices = set(top10_df.index.tolist())

            for idx in viable.index:
                row = results.iloc[idx]
                score = row["suitability"]
                color = colormap(score)
                cpt = centroids_all.geometry.iloc[idx]

                marker_kwargs = dict(
                    location=[cpt.y, cpt.x],
                    radius=max(3, resolution * 0.8),
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.7,
                    weight=0.5,
                )

                if idx in top10_indices:
                    rank = sorted(top10_indices, key=lambda i: -results.iloc[i]["suitability"]).index(idx) + 1
                    lon, lat = cpt.x, cpt.y
                    marker_kwargs["popup"] = folium.Popup(
                        f"<b>#{rank}</b> — Score: {score:.0f}<br>"
                        f"Lat: {lat:.3f}, Lon: {lon:.3f}<br>"
                        f"Resource: {row['resource_score']:.0f} · "
                        f"Slope: {row['slope_score']:.0f}<br>"
                        f"Grid: {row['grid_dist_score']:.0f} · "
                        f"Road: {row['road_dist_score']:.0f}",
                        max_width=220,
                    )
                    marker_kwargs["radius"] = max(5, resolution * 1.2)
                    marker_kwargs["weight"] = 2

                folium.CircleMarker(**marker_kwargs).add_to(m)

            # Number markers for top 10
            if not viable.empty:
                for rank_i, idx in enumerate(sorted(top10_indices, key=lambda i: -results.iloc[i]["suitability"])):
                    cpt = centroids_all.geometry.iloc[idx]
                    folium.Marker(
                        location=[cpt.y, cpt.x],
                        icon=folium.DivIcon(
                            html=f'<div style="font-size:11px;font-weight:bold;color:#fff;'
                                 f'background:#1a1a2e;border-radius:50%;width:20px;height:20px;'
                                 f'text-align:center;line-height:20px;">{rank_i+1}</div>',
                            icon_size=(20, 20),
                            icon_anchor=(10, 10),
                        ),
                    ).add_to(m)

            colormap.add_to(m)
            st_folium(m, use_container_width=True, height=550, returned_objects=[])

        with chart_col:
            st.subheader("Score Distribution")

            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use("Agg")

            fig, ax = plt.subplots(figsize=(4, 4.5))
            cats = ["Excluded", "Very Low", "Low", "Medium", "High", "Very High"]
            colors_hist = ["#999999", "#d73027", "#fc8d59", "#fee08b", "#d9ef8b", "#1a9850"]
            counts = [len(excluded)]
            if not viable.empty:
                bins = [0, 20, 40, 60, 80, 100]
                hist_counts, _ = np.histogram(viable["suitability"], bins=bins)
                counts.extend(hist_counts.tolist())
            else:
                counts.extend([0, 0, 0, 0, 0])

            bars = ax.barh(cats, counts, color=colors_hist)
            ax.set_xlabel("Number of cells")
            ax.set_title("Suitability Categories", fontsize=11, fontweight="bold")
            for bar, count in zip(bars, counts):
                if count > 0:
                    ax.text(bar.get_width() + max(counts) * 0.02, bar.get_y() + bar.get_height() / 2,
                            str(count), va="center", fontsize=9)
            for spine in ["top", "right"]:
                ax.spines[spine].set_visible(False)
            fig.tight_layout()
            st.pyplot(fig)

            st.subheader("Criterion Scores")
            if not viable.empty:
                resource_name = "Wind Speed" if current_energy == "wind" else "Solar GHI"
                score_means = {
                    resource_name: viable["resource_score"].mean(),
                    "Flood Risk": viable["flood_score"].mean(),
                    "Grid Dist": viable["grid_dist_score"].mean(),
                    "Road Dist": viable["road_dist_score"].mean(),
                    "Slope": viable["slope_score"].mean(),
                    "Settlement": viable["settlement_score"].mean(),
                }
                score_df = pd.DataFrame(
                    {"Criterion": score_means.keys(), "Mean Score": [f"{v:.0f}" for v in score_means.values()]}
                )
                st.dataframe(score_df, hide_index=True, use_container_width=True)

        # Top scoring areas — spatially diversified (min 15 km apart)
        if not viable.empty:
            st.subheader("Top 10 Candidate Zones")
            st.caption("Spatially diversified: minimum 15 km between candidates to identify distinct areas.")
            top = top10_df.copy()
            top_lons, top_lats = transformer.transform(
                top["centroid_x"].values, top["centroid_y"].values
            )
            counties = get_counties_bulk(top["centroid_x"].values, top["centroid_y"].values)
            top_display = pd.DataFrame({
                "#": range(1, len(top) + 1),
                "Score": top["suitability"].round(0).astype(int).values,
                "County": counties,
                "Lat": [f"{lat:.3f}" for lat in top_lats],
                "Lon": [f"{lon:.3f}" for lon in top_lons],
                "Resource": top["resource_score"].round(0).astype(int).values,
                "Flood": top["flood_score"].round(0).astype(int).values,
                "Grid": top["grid_dist_score"].round(0).astype(int).values,
                "Road": top["road_dist_score"].round(0).astype(int).values,
                "Slope": top["slope_score"].round(0).astype(int).values,
                "Settlement": top["settlement_score"].round(0).astype(int).values,
            })
            st.dataframe(top_display, hide_index=True, use_container_width=True)

        # Sensitivity analysis
        if not viable.empty:
            with st.expander("Sensitivity Analysis", expanded=True):
                st.caption("How do the top 10 areas change when each weight is increased by 50%?")

                current_weights = st.session_state.get("weights", weights)
                base_top10 = set(top10_df.index.tolist())

                sensitivity_rows = []
                for key in current_weights:
                    perturbed = current_weights.copy()
                    perturbed[key] = int(perturbed[key] * 1.5)
                    perturbed_results = run_analysis(grid, data, perturbed, current_energy)
                    perturbed_viable = perturbed_results[~perturbed_results["excluded"]]
                    if not perturbed_viable.empty:
                        new_top10_df = select_top_diverse(perturbed_results, n=10, min_distance_km=15)
                        new_top10 = set(new_top10_df.index.tolist())
                        overlap = len(base_top10 & new_top10)
                        stability = overlap / 10 * 100
                    else:
                        stability = 0
                    label = key.replace("_", " ").title()
                    sensitivity_rows.append({"Criterion": label, "Weight +50%": f"{perturbed[key]}", "Top-10 Stability": f"{stability:.0f}%"})

                sens_df = pd.DataFrame(sensitivity_rows)
                st.dataframe(sens_df, hide_index=True, use_container_width=True)
                st.caption("Stability shows what % of the original top-10 cells remain in the top-10 after perturbation. Lower values indicate the ranking is sensitive to that criterion.")

        # Download
        csv = results.drop(columns=["geometry"]).to_csv(index=False)
        st.download_button(
            "Download Results (CSV)",
            csv,
            "suitability_results.csv",
            "text/csv",
        )

else:
    st.info("Configure parameters in the sidebar and click **Run Analysis** to start.")

    tab_method, tab_sources, tab_limits = st.tabs(["Methodology", "Data Sources", "Limitations"])

    with tab_method:
        st.markdown(
            """
            ### Two-Phase Multi-Criteria Analysis

            This tool implements a constraint-based screening approach followed by
            weighted multi-criteria evaluation, consistent with standard GIS-MCDA
            practice in renewable energy site assessment.

            **Phase 1 — Hard Constraints (Exclusion)**

            Cells that fail any of these checks are eliminated before scoring:

            | Constraint | Rule | Rationale |
            |---|---|---|
            | Protected Areas | SAC/SPA overlap → excluded | EU Habitats & Birds Directives |
            | Flood Risk | High-probability flood zone → excluded | OPW NIFM classification |
            | Slope | Above energy-type maximum → excluded | Solar: >15°, Wind: >30° |
            | Settlement Proximity | Below minimum distance → excluded | Wind: 1500m, Solar: 500m |

            **Phase 2 — Weighted Scoring (0–100)**

            Viable cells are scored across five criteria. Users can adjust weights
            to reflect project priorities.

            | Criterion | Method | Source |
            |---|---|---|
            | Resource Potential | Wind: mean speed at 100m; Solar: GHI | Global Wind Atlas / PVGIS |
            | Grid Proximity | Distance to nearest substation/wind farm (cKDTree) | SEAI Wind Farms dataset (proxy for grid connection points) |
            | Road Access | Distance to nearest road (line sampling + cKDTree) | OSi National 250k roads |
            | Terrain Slope | Pre-computed slope grid, scored by ideal range | Derived from DEM |
            | Settlement Buffer | Distance beyond minimum exclusion zone | Synthetic (demo) / OSM places (production) |

            **Score Combination:**
            Weighted linear combination with user-defined weights, normalised to sum to 1.

            **Classification:**
            Final scores are binned: Very Low (0–20), Low (20–40), Medium (40–60),
            High (60–80), Very High (80–100).
            """
        )

    with tab_sources:
        st.caption("This tool uses the following Irish open datasets:")
        for key, source in DATA_SOURCES.items():
            st.markdown(
                f"- **{source['name']}** — {source['provider']} · {source['format']} · {source['license']}  \n"
                f"  [{source['url']}]({source['url']})"
            )

    with tab_limits:
        st.markdown(
            """
            ### Known Limitations

            - **Demo data:** Default mode uses synthetic data for demonstration.
              Real datasets should be downloaded for production use.
            - **Republic of Ireland only:** Boundary covers the 26-county Republic.
              Northern Ireland (UK jurisdiction) has different planning, grid, and
              environmental datasets and is excluded.
            - **Peatland/bog risk:** Not yet included as a constraint. Relevant for
              wind projects in western Ireland (landslide and ecological sensitivity).
            - **Grid capacity:** Grid proximity uses existing wind farms as a proxy
              for connection points; actual substation locations and available
              capacity are not modelled. EirGrid queue data would improve this.
            - **Cumulative visual impact:** Not modelled. Planning authorities may
              refuse projects in areas with existing turbine clusters.
            - **Resolution:** Analysis grid cells (2–10 km) are coarse for final
              site selection. This tool identifies candidate zones for detailed study.
            - **NHA sites:** Natural Heritage Areas are not hard-excluded (unlike
              SAC/SPA) as development may be permissible with appropriate assessment.
            """
        )
