# Geo Coverage POC

Tool for business teams to configure geographic service coverage using interactive maps, embedded in **ToolJet** via an IFrame.

**Live demo:** https://app.tooljet.com/applications/e0d8e681-dc87-4cc5-acef-3120e65208a3

---

## How it works

```
ToolJet Cloud
└── IFrame → map_widget.html (hosted on Railway)
              ├── Leaflet.js  (map rendering + polygon draw)
              ├── h3-js       (hex grid in browser)
              └── FastAPI     (polygon → H3 conversion, save)
```

The map widget can also run standalone (without ToolJet):
https://geo-coverage-poc-sidecar-production.up.railway.app/static/map_widget.html

---

## What it does

Draw coverage boundaries for services (pickup zones, drop zones, outstation boundaries) using two modes:

- **✏ Polygon Draw** — Draw a polygon on the map → auto-converts to H3 hexagonal cells
- **⬡ Hex Select** — Zoom in and click individual hex cells to select/deselect

Both modes output the same format: an array of H3 cell IDs — the production storage format for Availability Engine.

---

## Run locally

```bash
git clone https://github.com/PrakshaChaudhary/geo-coverage-poc-sidecar.git
cd geo-coverage-poc-sidecar
pip install -r requirements-dev.txt
uvicorn main:app --reload --port 8000
```

Open: `https://geo-coverage-poc-sidecar-production.up.railway.app/static/map_widget.html`

---

## Stack

- **ToolJet** — UI platform (IFrame host + data source management)
- **FastAPI** — API + static file serving
- **h3 (Python)** — server-side polygon → H3 cell conversion
- **h3-js** — client-side viewport hex grid rendering
- **Leaflet.js + Leaflet.draw** — interactive map and polygon drawing
---

## Output format

Saving a coverage returns both the original polygon and the H3 cell array:

```json
{
  "status": "DRAFT",
  "cell_count": 183,
  "cell_ids": ["8960145b40bffff", "8960145b417ffff", "..."],
  "polygon": { "type": "Polygon", "coordinates": [[...]] }
}
```
