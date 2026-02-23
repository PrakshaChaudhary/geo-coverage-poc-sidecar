import pytest
from httpx import AsyncClient, ASGITransport
from main import app

# Small test polygon inside Bangalore (approx 1km² around Koramangala)
# GeoJSON coordinates are [lng, lat]
SMALL_POLYGON = {
    "type": "Polygon",
    "coordinates": [[
        [77.59, 12.97],
        [77.60, 12.97],
        [77.60, 12.98],
        [77.59, 12.98],
        [77.59, 12.97],
    ]]
}

# Large polygon that crosses Bangalore boundary (extends well outside)
LARGE_POLYGON_CROSSING_BOUNDARY = {
    "type": "Polygon",
    "coordinates": [[
        [77.00, 12.50],
        [78.50, 12.50],
        [78.50, 13.50],
        [77.00, 13.50],
        [77.00, 12.50],
    ]]
}


@pytest.mark.anyio
async def test_polyfill_returns_cells():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/polyfill", json={
            "geojson": SMALL_POLYGON,
            "resolution": 9,
            "entity_type": "drop_coverage",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "cell_ids" in data
    assert len(data["cell_ids"]) > 0
    assert "cell_count" in data
    assert data["cell_count"] == len(data["cell_ids"])


@pytest.mark.anyio
async def test_polyfill_with_clip_excludes_cells_outside_city():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/polyfill", json={
            "geojson": LARGE_POLYGON_CROSSING_BOUNDARY,
            "resolution": 9,
            "entity_type": "drop_coverage",
            "city_id": "bangalore",
            "clip_to_city": True,
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "original_count" in data
    assert "clipped_count" in data
    assert len(data["cell_ids"]) <= data["original_count"]
    # The large polygon extends outside Bangalore, so clipped_count must be > 0
    assert data["clipped_count"] > 0


@pytest.mark.anyio
async def test_polyfill_returns_geojson_preview():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/polyfill", json={
            "geojson": SMALL_POLYGON,
            "resolution": 9,
            "entity_type": "outskirt",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "geojson" in data
    assert data["geojson"]["type"] == "FeatureCollection"
    assert len(data["geojson"]["features"]) > 0


@pytest.mark.anyio
async def test_polyfill_invalid_resolution_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/polyfill", json={
            "geojson": SMALL_POLYGON,
            "resolution": 13,  # above max (allowed: 7-12)
            "entity_type": "outskirt",
        })
    assert resp.status_code == 422
