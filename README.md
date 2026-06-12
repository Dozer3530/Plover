<div align="center"><img src="assets/piping-plover-removebg-preview.png" alt="Plover" width="240"></div>

# Plover

Boundary-aware Traveling Salesperson routing for QGIS. Give it a point layer and a polygon boundary, get back the shortest tour that visits every point while staying inside the field and routing around any holes (sloughs, exclusion zones). The boundary is optional — leave it out and Plover solves a plain straight-line TSP through your points.

A companion to [Perch](https://github.com/Dozer3530/Perch) and [Lapwing](https://github.com/Dozer3530/Lapwing) — Perch lands your drone imagery, Lapwing watches from above, Plover walks the ground between your sample points.

AI assistance was used to make this plugin possible.

---

## Install

Grab the latest `plover-vX.Y.Z.zip` from the [Releases](https://github.com/Dozer3530/Plover/releases) page, then in QGIS:

**Plugins → Manage and Install Plugins → Install from ZIP** → select the file → **Install Plugin**.

Compatible with QGIS 3.22+ and QGIS 4.x (Qt5 and Qt6).

## What it does

Given a point layer (waypoints) and a polygon boundary, Plover:

1. Builds a visibility graph between waypoints and the boundary's *turn vertices* — only concave field corners and hole corners can ever bend a shortest path, so convex corners and straight-line vertices are skipped entirely (a rectangular field contributes zero graph nodes).
2. Computes obstacle-aware shortest paths between every pair of waypoints — one Dijkstra per waypoint, with GEOS prepared-geometry predicates doing the visibility tests.
3. Optimizes the visiting order with multi-start nearest-neighbour construction polished by alternating **2-opt** and **Or-opt** local search.
4. Stitches the optimized order back into a continuous polyline using the cached shortest paths.
5. Adds the route (styled with direction arrows) plus an optional **numbered visit-order layer** to your project.

Everything runs in a **background task** — QGIS stays responsive and long runs are cancellable.

The output respects:

- The outer field boundary
- Interior rings (sloughs, rock piles, fenced exclusions modelled as polygon holes)
- Boundary features fully enclosed by another feature (auto-treated as exclusion zones)
- A buffer tolerance that genuinely lets the route hug the field edge — points sitting exactly on the boundary line are routable

## Use case

Built for field scouting and ground-truth sampling on Smart Farm research plots — you pick the points you need to visit, Plover plans the walking order that minimizes distance without crossing into the slough you weren't supposed to drive through.

Also useful for:

- Soil sampling routes
- Pest/disease scouting transects
- Manual sensor verification routes
- Any "visit N points in a constrained area" problem

## Usage (dialog)

1. Load a point layer. A polygon boundary layer is **optional** — add one to keep the route inside a field and around sloughs, or skip it for a plain straight-line route. Use a **projected CRS** (UTM, NAD83, …) — Plover refuses geographic CRS and auto-reprojects the points to the working CRS if they differ.
2. Open Plover from the **Plugins** menu or the toolbar icon.
3. Pick the point layer, and a boundary layer if you want one (leave **Boundary layer** empty for no boundary — the dropdowns track your project automatically).
4. Optionally tick **Use only selected points**.
5. Pick the **start point** with the feature picker.
6. *(boundary only)* Set the **boundary buffer** (default 0.5 map units) — how far the route may stray outside the strict boundary or into exclusion zones.
7. *(boundary only)* Choose what happens to **points outside the boundary**: *Fail if any point is outside* (the default — good when every point should be in-field) or *Skip points outside the boundary* (route only the points inside; handy when one big point layer spans many fields and you only want this field's points).
8. Untick **Return to start** if you want a one-way path instead of a round trip.
9. Click **Run**. Progress is live and the run is cancellable.
10. **Save Route…** exports to GeoPackage, Shapefile, GeoJSON, **GPX track** or **KML** (GPX/KML are auto-reprojected to WGS84 — load the GPX straight onto a handheld or phone).

With a boundary in **fail** mode, if any points fall outside the buffered boundary Plover refuses to run, selects the offending features on the layer, and logs their distances (**View → Panels → Log Messages → Plover**). In **skip** mode those points are dropped and only the in-boundary ones are routed (the count is reported). Points unreachable from the start (cut off by a hole or a pinched boundary) are reported by number instead of being silently straight-lined. With no boundary every point is reachable from every other, so these checks don't apply.

## Usage (Processing)

Plover also registers a Processing algorithm — **Processing Toolbox → Plover → Boundary-aware TSP route** (`plover:tsproute`) — so you can use it in the **Model Designer**, **batch mode**, or from PyQGIS:

```python
import processing
result = processing.run("plover:tsproute", {
    "POINTS": points_layer,
    "BOUNDARY": boundary_layer,  # optional — omit or pass None for a straight-line TSP
    "BUFFER": 0.5,
    "START_INDEX": 0,
    "ROUND_TRIP": True,
    "ON_OUTSIDE": 0,  # 0 = fail if any point is outside, 1 = skip outside points
    "OUTPUT_ROUTE": "memory:route",
    "OUTPUT_ORDER": "memory:visit_order",
})
```

## Performance

v3.0.0 reworked the whole pipeline (reflex-vertex graph reduction, prepared geometries, single-source Dijkstra, Or-opt). On a synthetic 100-point field with an 80-vertex boundary and two sloughs, against v2.7.0:

| | v2.7.0 | v3.0.0 |
|---|---|---|
| Wall time | 2.9 s | 0.26 s (**11× faster**) |
| Tour length | 6749 m | 6405 m (**5% shorter**) |

The advantage grows with point count and boundary complexity — and since v3.0.0 runs in a background task, QGIS no longer freezes either way.

## Known limitations

- The solver is heuristic (multi-start NN + 2-opt + Or-opt), not exact. Tours are typically within a few percent of optimal but not provably optimal.
- With a boundary, points outside it are either reported (fail mode) or skipped (skip mode) — Plover never guesses a route to a point it can't legally reach. Without a boundary, the route is straight-line and obstacle-unaware by design.
- Geographic CRS (EPSG:4326 etc.) is rejected — reproject to a projected CRS first.
- The route follows straight visibility lines between graph vertices; it does not account for terrain, row direction, or machinery turning radii.

## Why "Plover"

Piping Plovers are small, endangered shorebirds that nest on Alberta's prairie shorelines. They walk fast, in tight efficient zig-zags between feeding points, and famously avoid the obstacles in their path. Fitting for a TSP plugin.

## Project layout

```
Plover/
  assets/                            # logo
  tsp_route_generator/               # QGIS plugin folder (name fixed for plugin identity)
    __init__.py                      # classFactory entry point
    metadata.txt
    icon.png
    tsp_route_generator.py           # plugin shell: menu/toolbar + Processing registration
    tsp_route_generator_dialog.py    # dialog UI (UI only — no algorithm code)
    route_task.py                    # compute_route pipeline + QgsTask wrapper
    geometry_utils.py                # visibility graph, boundary handling (QGIS API)
    tsp_core.py                      # pure-Python solver: Dijkstra, NN, 2-opt, Or-opt
    processing_provider.py           # Processing algorithm (plover:tsproute)
    test/                            # unit + headless integration tests
  build_zip.ps1                      # builds the release zip
  README.md / LICENSE / .gitignore
```

The QGIS plugin folder stays named `tsp_route_generator/` because QGIS identifies installed plugins by folder name on disk. Renaming it would orphan existing installs.

## Development

The solver core has no QGIS dependency, so its tests run with any Python:

```powershell
python -m unittest tsp_route_generator.test.test_tsp_core -v
```

The integration and dialog tests run headless against the real QGIS API:

```powershell
& "C:\Program Files\QGIS 4.0.1\bin\python-qgis.bat" -m unittest discover -s tsp_route_generator/test -t . -v
```

Build a release zip (reads the version from `metadata.txt`):

```powershell
.\build_zip.ps1
```

## License

MIT — see [LICENSE](LICENSE).

## Author

Zachary Komarnisky — Digital Agriculture program, Olds College of Agriculture & Technology.
