import pytest
from httpx import AsyncClient, ASGITransport
import main as main_module
from main import app

SAMPLE_CELLS = ["8f2830828052d25", "8f2830828052d2d", "8f2830828052c25"]

SAVE_PAYLOAD = {
    "georegion_id": "bangalore",
    "cell_ids": SAMPLE_CELLS,
    "resolution": 9,
    "metadata": {"sr_category_id": 2, "demand_type": "FTL", "offering": "P2P_LOCAL"},
}


@pytest.fixture(autouse=True)
def reset_store():
    """Reset in-memory store between tests to prevent state bleed."""
    VALID_ENTITY_TYPES = {"outskirt", "outstation_short", "outstation_long", "drop_coverage"}
    main_module._store.clear()
    for t in VALID_ENTITY_TYPES:
        main_module._store[t] = {}
    yield
    main_module._store.clear()
    for t in VALID_ENTITY_TYPES:
        main_module._store[t] = {}


@pytest.mark.anyio
async def test_save_boundary_returns_draft_status():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/boundaries/drop_coverage", json=SAVE_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "DRAFT"
    assert data["cell_count"] == len(SAMPLE_CELLS)
    assert "id" in data


@pytest.mark.anyio
async def test_fetch_boundary_after_save():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/boundaries/drop_coverage", json=SAVE_PAYLOAD)
        resp = await client.get("/api/boundaries/drop_coverage/bangalore")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["records"]) >= 1
    record = data["records"][0]
    assert set(record["cell_ids"]) == set(SAMPLE_CELLS)
    assert "geojson" in record


@pytest.mark.anyio
async def test_save_unknown_entity_type_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/boundaries/invalid_type", json=SAVE_PAYLOAD)
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_save_empty_cell_list_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/boundaries/outskirt", json={**SAVE_PAYLOAD, "cell_ids": []})
    assert resp.status_code == 422
