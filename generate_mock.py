"""
Run once locally to generate mock H3 data for 3 cities.
Usage: cd geo-sidecar && python generate_mock.py
Output: mock_data_generated.json (commit this file)

NOTE: h3 4.1.0 uses h3.LatLngPoly instead of h3.H3Polygon.
      polygon_to_cells is an alias for h3shape_to_cells.
"""
import h3
import json

CITIES = {
    "bangalore": {
        "display_name": "Bengaluru",
        "center": [12.9716, 77.5946],
        # Rough bounding box for POC — not precise OSM boundary
        "polygon": [
            [12.83, 77.46], [12.83, 77.75],
            [13.14, 77.75], [13.14, 77.46],
            [12.83, 77.46],
        ],
        "resolution": 9,
    },
    "mumbai": {
        "display_name": "Mumbai",
        "center": [19.0760, 72.8777],
        "polygon": [
            [18.90, 72.78], [18.90, 72.98],
            [19.27, 72.98], [19.27, 72.78],
            [18.90, 72.78],
        ],
        "resolution": 9,
    },
    "delhi": {
        "display_name": "Delhi NCR",
        "center": [28.6139, 77.2090],
        "polygon": [
            [28.40, 76.85], [28.40, 77.55],
            [28.88, 77.55], [28.88, 76.85],
            [28.40, 76.85],
        ],
        "resolution": 9,
    },
}


def main():
    output = {}
    for code, cfg in CITIES.items():
        # h3 4.1.0: use h3.LatLngPoly (not h3.H3Polygon which does not exist in 4.x)
        # LatLngPoly expects (lat, lng) tuples — same coordinate order as H3Polygon
        outer = [(p[0], p[1]) for p in cfg["polygon"]]
        h3poly = h3.LatLngPoly(outer)
        cells = list(h3.polygon_to_cells(h3poly, cfg["resolution"]))
        centre_cell = h3.latlng_to_cell(cfg["center"][0], cfg["center"][1], cfg["resolution"])
        output[code] = {
            "id": code,
            "code": code,
            "display_name": cfg["display_name"],
            "center": cfg["center"],
            "h3_cells": cells,
            "h3_resolution": cfg["resolution"],
            "city_centre_cell": centre_cell,
            "cell_count": len(cells),
        }
        print(f"{code}: {len(cells)} cells at res {cfg['resolution']}")

    with open("/Users/praksha.chaudhary/geo-coverage-poc/geo-sidecar/mock_data_generated.json", "w") as f:
        json.dump(output, f, separators=(",", ":"))  # compact — file can be large
    print("Written: mock_data_generated.json")


if __name__ == "__main__":
    main()
