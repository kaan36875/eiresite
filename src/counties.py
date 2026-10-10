"""Approximate county lookup for Republic of Ireland using nearest centroid."""

import numpy as np
from pyproj import Transformer

_transformer = Transformer.from_crs("EPSG:4326", "EPSG:2157", always_xy=True)

# County centroids (lon, lat) → projected to ITM at import time
_COUNTIES_WGS84 = {
    "Carlow": (-6.93, 52.84),
    "Cavan": (-7.36, 53.99),
    "Clare": (-8.98, 52.84),
    "Cork": (-8.49, 51.90),
    "Donegal": (-7.95, 54.83),
    "Dublin": (-6.26, 53.35),
    "Galway": (-8.86, 53.27),
    "Kerry": (-9.85, 52.07),
    "Kildare": (-6.91, 53.16),
    "Kilkenny": (-7.25, 52.65),
    "Laois": (-7.56, 53.03),
    "Leitrim": (-8.00, 54.12),
    "Limerick": (-8.62, 52.60),
    "Longford": (-7.79, 53.73),
    "Louth": (-6.49, 53.92),
    "Mayo": (-9.54, 53.76),
    "Meath": (-6.66, 53.61),
    "Monaghan": (-6.97, 54.25),
    "Offaly": (-7.59, 53.23),
    "Roscommon": (-8.27, 53.76),
    "Sligo": (-8.47, 54.15),
    "Tipperary": (-7.83, 52.67),
    "Waterford": (-7.11, 52.26),
    "Westmeath": (-7.42, 53.53),
    "Wexford": (-6.58, 52.47),
    "Wicklow": (-6.37, 52.98),
}

_county_names = list(_COUNTIES_WGS84.keys())
_county_coords_itm = []
for name, (lon, lat) in _COUNTIES_WGS84.items():
    x, y = _transformer.transform(lon, lat)
    _county_coords_itm.append((x, y))
_county_arr = np.array(_county_coords_itm)


def get_county(centroid_x: float, centroid_y: float) -> str:
    dists = np.sqrt((_county_arr[:, 0] - centroid_x)**2 + (_county_arr[:, 1] - centroid_y)**2)
    return _county_names[np.argmin(dists)]


def get_counties_bulk(xs, ys) -> list[str]:
    xs = np.asarray(xs)
    ys = np.asarray(ys)
    results = []
    for x, y in zip(xs, ys):
        dists = np.sqrt((_county_arr[:, 0] - x)**2 + (_county_arr[:, 1] - y)**2)
        results.append(_county_names[np.argmin(dists)])
    return results
