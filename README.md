# TSP Route Generator

A QGIS plugin that generates an optimized Traveling Salesman Problem (TSP) route through a point layer, constrained to stay within a polygon boundary.

Compatible with QGIS 3.x and QGIS 4.x.

## What it does

Given a point layer (waypoints) and a polygon layer (boundary), the plugin:

1. Builds a visibility graph between points and boundary vertices, rejecting edges that cross the boundary.
2. Solves an approximate TSP using a nearest-neighbour heuristic over the graph (Dijkstra for shortest paths between waypoints).
3. Applies 2-opt optimization to the resulting tour.
4. Adds the route as a new line layer in the project, with an option to save as Shapefile or GeoJSON.

A buffer distance allows routes to follow paths slightly outside the strict boundary (useful when boundary geometry is tight to your waypoints).

## Requirements

- QGIS 3.0 or newer (tested on 3.x and 4.x)
- Both input layers must share the same CRS
- The point layer must contain `Point` or `MultiPoint` features
- The boundary layer must contain at least one valid polygon feature

## Installation

### From this repository (current method)

1. Clone or download this repository.
2. Copy the `tsp_route_generator/` folder (the subfolder, not the repo root) into your QGIS plugins directory:
   - **Linux:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - **Windows:** `C:\Users\<you>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - **macOS:** `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
3. Restart QGIS, then enable **TSP Route Generator** under **Plugins → Manage and Install Plugins → Installed**.

### From a packaged ZIP

If a release ZIP is published on the [Releases](https://github.com/Dozer3530/TSP_QGIS/releases) page:

1. In QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**.
2. Select the ZIP and click **Install Plugin**.

## Usage

1. Load a point layer and a polygon boundary layer into your QGIS project. Both must be in the same CRS.
2. Open the plugin from the **Plugins** menu or the toolbar icon.
3. Select the point layer (Poi) and boundary layer.
4. Set a buffer distance (in map units) — `0.1` is a sensible starting value.
5. Set the start point index (`0` for the first feature).
6. Click **Run**.
7. Once the route appears in the project, click **Save Route** to export.

Diagnostic messages are written to **View → Panels → Log Messages** under the `TSP Route Generator` tab.

## Known limitations

- The TSP solver is heuristic, not exact. For large point sets (>~50 points) results are good but not optimal.
- All points must lie within the buffered boundary. The plugin will refuse to run otherwise and report which points are out.
- Geographic CRS (e.g. EPSG:4326) will produce nonsensical distances. Reproject to a projected CRS before running.

## License

GPL v2 or later (per the source file headers).

## Author

Zachary Komarnisky — Digital Agriculture program, Olds College of Agriculture & Technology.
