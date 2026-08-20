## Appendix A. Quick Reference

### A.1 Dialog settings at a glance

| Control | Default | Remembered? | Notes |
|---|---|---|---|
| Points to visit | *(first point layer)* | No | Required |
| Use only selected points | Off | No | Needs an active selection |
| Boundary layer | *(first polygon layer)* | No | **Optional** — leave empty for a straight-line tour |
| Start at point | *(first feature)* | No | Falls back to the first point if unresolved |
| Boundary buffer | `0.50` map units | Yes | Disabled when no boundary is chosen |
| Points outside boundary | Fail if any point is outside | Yes | Disabled when no boundary is chosen |
| Return to start (round trip) | On | Yes | Off gives a one-way path |
| Also create a numbered visit-order layer | On | Yes | — |

Remembered settings are stored under the `plover/` prefix in QGIS settings and persist between sessions.

### A.2 Processing parameters at a glance

| Key | Type | Optional | Default |
|---|---|---|---|
| `POINTS` | Point feature source | No | — |
| `BOUNDARY` | Polygon feature source | **Yes** | *(unset)* |
| `BUFFER` | Distance | No | `0.5` |
| `START_INDEX` | Integer | No | `0` |
| `ROUND_TRIP` | Boolean | No | `True` |
| `ON_OUTSIDE` | Enum: `0` fail, `1` skip | No | `0` |
| `OUTPUT_ROUTE` | Line sink | No | — |
| `OUTPUT_ORDER` | Point sink | Yes | created by default |

Algorithm id: **`plover:tsproute`**

### A.3 Output fields

**Route layer** — `length` (double), `stops` (integer), `round_trip` (string, `yes` or `no`).

**Visit order layer** — `visit_order` (integer, from 1), `source_fid` (integer), `leg_length` (double).

### A.4 Export formats

| Format | Extension | Reprojected to WGS84 |
|---|---|---|
| GeoPackage | `.gpkg` | No |
| Shapefile | `.shp` | No |
| GeoJSON | `.geojson` | No |
| GPX track | `.gpx` | **Yes** |
| KML | `.kml` | **Yes** |

### A.5 Decision guide

| Situation | What to do |
|---|---|
| Points must all be in this field | Leave **Points outside boundary** on *Fail* |
| One point layer covers many fields | Set it to *Skip points outside the boundary* |
| Points sit right on the field edge | Increase **Boundary buffer** to a few metres |
| You only want a visiting order, no obstacle avoidance | Leave **Boundary layer** empty |
| You finish at a different gate than you started | Untick **Return to start** |
| You only want to route part of the layer | Select those features, tick **Use only selected points** |
| Route must start at the field entrance | Add the gate as a point and set it as **Start at point** |

---

## Appendix B. Glossary

**2-opt** — An improvement step that reverses a section of the tour when doing so shortens it. Removes self-crossings.

**Boundary buffer** — How far outside the strict boundary, and into exclusion zones, the route is permitted to stray. Also absorbs GPS error on points digitized near the field edge.

**Closed tour / round trip** — A route that returns to its starting point.

**CRS (Coordinate Reference System)** — How coordinates map to positions on the earth. Plover requires a *projected* CRS, whose units are linear (usually metres), not a *geographic* one measured in degrees.

**Dijkstra's algorithm** — The shortest-path algorithm Plover runs once per waypoint to find true travel distances through the visibility graph.

**Euclidean TSP** — The plain straight-line version of the problem, with no obstacles. What Plover solves when no boundary is supplied.

**Exclusion zone** — Any area inside the field the route must avoid: slough, wetland, dugout, bush, rock pile, yard site. Represented as a hole in the boundary polygon, or as a polygon fully enclosed by another.

**Feature id (fid)** — QGIS's internal identifier for a feature. Recorded in the visit-order layer's `source_fid` field so you can join results back to the original points.

**Heuristic** — A method that finds a very good answer quickly without proving it is the best possible. Plover's solver is heuristic.

**Hole / interior ring** — A ring inside a polygon's outline that is *not* part of the polygon. How sloughs are normally represented.

**Leg** — One segment of the tour, from one stop to the next.

**Memory layer / scratch layer** — A layer that exists only in the current QGIS session. Plover's outputs are memory layers and are lost unless you save them.

**Nearest-neighbour construction** — Building an initial tour by repeatedly hopping to the closest unvisited point. Fast but rough; Plover then improves it.

**Open path / one-way** — A route that ends at its last stop rather than returning to the start.

**Or-opt** — An improvement step that relocates a short run of one to three stops to a better place in the tour.

**Prepared geometry** — A form of a geometry optimised once so that many repeated tests against it run quickly. Used for the visibility graph's containment tests.

**Reflex vertex / turn vertex** — A corner that juts into the open space, where a taut shortest path can bend. Only these are kept when building the visibility graph.

**Round trip** — See *closed tour*.

**Slough** — A prairie wetland or pothole. The archetypal obstacle Plover was written to route around.

**TSP (Travelling Salesperson Problem)** — Given a set of stops and the distances between them, find the shortest route visiting them all.

**Visibility graph** — A graph connecting every pair of nodes that can "see" each other, meaning the straight line between them stays inside the permitted region.

**Waypoint** — One point from the input layer, as used by the router.

**Working CRS** — The CRS routing happens in: the boundary layer's if a boundary is supplied, otherwise the point layer's. Outputs use this CRS.
