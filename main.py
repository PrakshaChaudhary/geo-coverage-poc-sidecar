# geo-sidecar/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Any, Optional
import pathlib

import h3

from mock_data import GEOREGIONS, CITY_CELL_SETS

app = FastAPI(title="Geo Coverage Sidecar", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # POC only
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (map_widget.html) — dir created later in Task 7
_static_dir = pathlib.Path(__file__).parent / "static"
_static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return RedirectResponse(url="/static/map_widget.html")


@app.get("/api/mock/georegions")
def list_georegions():
    return {
        "georegions": [
            {
                "id": g["id"],
                "code": g["code"],
                "display_name": g["display_name"],
                "center": g["center"],
                "city_centre_cell": g["city_centre_cell"],
                "h3_cells": g["h3_cells"],
                "h3_resolution": g["h3_resolution"],
                "cell_count": g["cell_count"],
            }
            for g in GEOREGIONS.values()
        ]
    }


class PolyfillRequest(BaseModel):
    geojson: dict[str, Any]
    resolution: int = Field(ge=7, le=12)
    entity_type: str
    city_id: Optional[str] = None
    clip_to_city: bool = False


def _geojson_polygon_to_h3_cells(geojson: dict, resolution: int) -> list[str]:
    """Convert a GeoJSON Polygon to H3 cell IDs using overlapping containment.

    GeoJSON coordinates are [lng, lat].
    h3.LatLngPoly expects [(lat, lng), ...] tuples.

    Uses overlapping containment so that cells whose area overlaps the polygon
    boundary are included, not just cells whose centre point falls inside.
    h3 4.1.0 does not expose CONTAINMENT_OVERLAPPING via a flag argument, so
    we implement it manually: polyfill with centre containment, find the border
    ring, collect all grid-disk-1 neighbours of border cells and add them.
    """
    geo_type = geojson.get("type")
    if geo_type == "FeatureCollection":
        coords = geojson["features"][0]["geometry"]["coordinates"]
    elif geo_type == "Feature":
        coords = geojson["geometry"]["coordinates"]
    elif geo_type == "Polygon":
        coords = geojson["coordinates"]
    else:
        raise ValueError(f"Unsupported GeoJSON type: {geo_type}")

    # coords[0] is the outer ring: [[lng, lat], [lng, lat], ...]
    # Convert to (lat, lng) tuples for h3.LatLngPoly
    outer = [(lat_lng[1], lat_lng[0]) for lat_lng in coords[0]]
    h3poly = h3.LatLngPoly(outer)

    # Try overlapping containment flags first (works if a future h3 version adds them)
    for kwargs in [
        {"flags": getattr(h3, "CONTAINMENT_OVERLAPPING", None)},
        {"flags": 2},  # CONTAINMENT_OVERLAPPING numeric value in h3 C library
    ]:
        flag_val = kwargs.get("flags")
        if flag_val is None:
            continue
        try:
            cells = list(h3.polygon_to_cells(h3poly, resolution, flags=flag_val))
            return cells
        except (TypeError, AttributeError):
            continue

    # Fallback: centre-point polyfill + border-neighbour expansion
    inner_cells: set[str] = set(h3.polygon_to_cells(h3poly, resolution))
    if not inner_cells:
        return []

    # Identify border cells — those with at least one neighbour outside the set
    border: set[str] = {
        c for c in inner_cells
        if any(n not in inner_cells for n in h3.grid_disk(c, 1))
    }

    # Collect all k=1 neighbours of border cells and add them to the result
    # This adds the one-cell-wide ring that straddles the polygon boundary
    extra: set[str] = set()
    for c in border:
        extra.update(h3.grid_disk(c, 1))
    extra -= inner_cells  # keep only the truly new cells

    return list(inner_cells | extra)


def _cells_to_geojson(cell_ids: list[str]) -> dict:
    """Convert H3 cell IDs to a GeoJSON FeatureCollection."""
    features = []
    for cell in cell_ids:
        # cell_to_boundary returns [(lat, lng), ...] — convert to [lng, lat] for GeoJSON
        boundary = h3.cell_to_boundary(cell)
        coords = [[lng, lat] for lat, lng in boundary]
        coords.append(coords[0])  # close the ring
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [coords]},
            "properties": {"cell_id": cell},
        })
    return {"type": "FeatureCollection", "features": features}


@app.post("/api/polyfill")
def polyfill(req: PolyfillRequest):
    try:
        cells = _geojson_polygon_to_h3_cells(req.geojson, req.resolution)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    original_count = len(cells)
    clipped_count = 0

    if req.clip_to_city and req.city_id:
        city_cells = CITY_CELL_SETS.get(req.city_id)
        if city_cells is None:
            raise HTTPException(status_code=404, detail=f"City not found: {req.city_id}")
        clipped = [c for c in cells if c in city_cells]
        clipped_count = original_count - len(clipped)
        cells = clipped

    # Cap GeoJSON preview at 2000 features to avoid huge responses
    geojson_preview = _cells_to_geojson(cells[:2000])

    return {
        "cell_ids": cells,
        "cell_count": len(cells),
        "original_count": original_count,
        "clipped_count": clipped_count,
        "geojson": geojson_preview,
    }


import uuid

VALID_ENTITY_TYPES = {"outskirt", "outstation_short", "outstation_long", "drop_coverage"}

# In-memory store: { entity_type: { city_id: [record, ...] } }
_store: dict[str, dict[str, list]] = {t: {} for t in VALID_ENTITY_TYPES}


class BoundaryRequest(BaseModel):
    georegion_id: str
    cell_ids: list[str] = Field(min_length=1)
    resolution: int = Field(ge=7, le=12)
    metadata: dict[str, Any] = {}
    polygon: Optional[dict[str, Any]] = None  # original GeoJSON polygon if drawn


@app.post("/api/boundaries/{entity_type}")
def save_boundary(entity_type: str, req: BoundaryRequest):
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown entity type: {entity_type!r}. Valid: {sorted(VALID_ENTITY_TYPES)}",
        )
    record = {
        "id": str(uuid.uuid4()),
        "entity_type": entity_type,
        "georegion_id": req.georegion_id,
        "cell_ids": req.cell_ids,
        "cell_count": len(req.cell_ids),
        "resolution": req.resolution,
        "metadata": req.metadata,
        "polygon": req.polygon,  # original GeoJSON polygon (may be None for hex selection)
        "status": "DRAFT",
    }
    _store[entity_type].setdefault(req.georegion_id, []).append(record)
    return {"id": record["id"], "status": "DRAFT", "cell_count": len(req.cell_ids)}


@app.get("/api/boundaries/{entity_type}/{city_id}")
def get_boundaries(entity_type: str, city_id: str):
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown entity type: {entity_type!r}",
        )
    records = _store[entity_type].get(city_id, [])
    enriched = [
        {
            **r,
            "geojson": _cells_to_geojson(r["cell_ids"][:500]),  # cap GeoJSON preview
        }
        for r in records
    ]
    return {"entity_type": entity_type, "georegion_id": city_id, "records": enriched}
