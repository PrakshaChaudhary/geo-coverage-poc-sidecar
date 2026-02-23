# geo-sidecar/mock_data.py
# Loads pre-generated H3 cell data for mock cities.
# The JSON file is committed alongside this file.
import json
import pathlib

_raw: dict = json.loads(
    (pathlib.Path(__file__).parent / "mock_data_generated.json").read_text()
)

GEOREGIONS: dict[str, dict] = _raw

# Set per city for O(1) containment checks in clip_to_city logic
CITY_CELL_SETS: dict[str, set[str]] = {
    code: set(data["h3_cells"]) for code, data in GEOREGIONS.items()
}
