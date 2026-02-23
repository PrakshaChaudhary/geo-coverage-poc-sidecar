import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.anyio
async def test_list_georegions_returns_three_cities():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/mock/georegions")
    assert resp.status_code == 200
    data = resp.json()
    assert "georegions" in data
    codes = {g["code"] for g in data["georegions"]}
    assert codes == {"bangalore", "mumbai", "delhi"}


@pytest.mark.anyio
async def test_georegion_has_required_fields():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/mock/georegions")
    blr = next(g for g in resp.json()["georegions"] if g["code"] == "bangalore")
    assert "h3_cells" in blr
    assert len(blr["h3_cells"]) > 100
    assert "center" in blr
    assert "city_centre_cell" in blr
    assert "cell_count" in blr
    assert blr["cell_count"] == len(blr["h3_cells"])
