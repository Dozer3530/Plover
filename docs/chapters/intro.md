## 1. Introduction and Key Concepts

### 1.1 What Plover is

Plover is a QGIS plugin that works out the **shortest order in which to visit a set of points**, and draws the resulting route on the map. Optionally, it keeps that route **inside a field boundary** and **around holes** in it — sloughs, wetlands, bush, rock piles, fenced-off areas — instead of drawing straight lines through them.

The plugin's own one-line description, from `metadata.txt`, is:

> Boundary-aware Traveling Salesperson routing: shortest tour through your points, around your sloughs.

| Item | Value |
|---|---|
| Plugin name | Plover |
| Version documented here | 3.2.5 |
| Author | Zachary Komarnisky (`zkomarnisky@oldscollege.ca`) |
| Licence | MIT |
| QGIS versions | `qgisMinimumVersion=3.22`, `qgisMaximumVersion=4.99` |
| Qt 6 support | `supportsQt6=True` |
| Menu category | `category=Vector` |
| Processing provider | Yes (`hasProcessingProvider=yes`) |
| Repository / issue tracker | `https://github.com/Dozer3530/Plover` / `https://github.com/Dozer3530/Plover/issues` |
| Plugin folder on disk | `tsp_route_generator` |

> **Note on the folder name.** The installed folder is called `tsp_route_generator`, not `plover`. That is deliberate: QGIS identifies installed plugins by their folder name, and renaming the folder would orphan existing installations. If you go looking in your QGIS profile for the plugin files, look for `tsp_route_generator`.

### 1.2 The problem Plover solves

Field work generates lists of places you have to stand: soil sample sites, scouting stops, sensors to check, plots to photograph. There are usually more of them than you can order sensibly in your head, and the order you happen to have digitized them in is almost never a sensible walking or driving order.

Two things go wrong when the order is chosen by eye:

1. **Wasted distance.** Zig-zagging back and forth across a quarter section adds kilometres of walking or driving per visit, and the penalty grows quickly with the number of stops.
2. **Illegal or impossible legs.** A straight line between two sample points may run through a slough, a wetland, a bush patch, a dugout, or off the field entirely onto someone else's land. A route that ignores obstacles is a route you cannot actually follow, so somebody in the field improvises — and the "optimized" plan stops meaning anything.

Plover addresses both. It computes a short visiting order **and** it can guarantee that every leg of the drawn route stays inside a polygon you supply and outside the holes in that polygon.

[[FIGURE: workflow-diagram | The Plover pipeline: point layer and optional boundary in, visibility graph and distance matrix in the middle, optimized order and stitched route out.]]

### 1.3 Key concepts

This section defines the vocabulary used throughout the rest of the guide. If you are already comfortable with TSP solvers and visibility graphs, you can skim to section 1.4.

#### 1.3.1 The Travelling Salesperson problem (TSP)

The Travelling Salesperson problem is the classic question: *given a set of locations and the distance between each pair of them, what is the shortest route that visits every location exactly once?*

That is exactly the field-scouting question, with "locations" being your sample points and "distance" being how far you actually have to travel between them.

The problem is easy to state and famously hard to solve exactly. The number of possible orders grows factorially with the number of stops — a 20-point job already has more possible orders than you could enumerate in a lifetime. Practical software therefore uses **heuristics**: methods that reliably find a very good order quickly, without proving that no better order exists. Plover is one of these. See section 1.6 for what that honestly means for you.

Two variants matter here, and Plover supports both:

- **Closed tour (round trip)** — you finish where you started. Plover adds the final leg from the last stop back to the start point.
- **Open path (one-way)** — you start at a chosen point and finish wherever the last stop happens to be. No return leg is added.

#### 1.3.2 Waypoints

A **waypoint** in Plover is simply one point feature from your input point layer, converted to a coordinate for routing. Plover reads point geometries only; features whose geometry is empty or is not a point geometry are skipped and logged. A **multipart** point geometry is reduced to its **centroid** before routing.

The route visits every waypoint that survives that filtering (and, with a boundary in skip mode, every waypoint that falls inside the boundary).

#### 1.3.3 Boundary polygon

The **boundary** is a polygon layer describing the area the route is allowed to occupy — typically your field boundary. It is passed as the **`Boundary layer:`** dropdown in the dialog, or the **`Boundary polygon(s)`** parameter in Processing.

Points to understand about how Plover treats it:

- **All polygon features in the layer are merged into one routing region.** You do not need to pre-dissolve.
- Features are sorted by area, largest first. Any feature that is **wholly contained inside another feature** is **subtracted** — it becomes an exclusion zone. Everything else is unioned into the region. This exists because people commonly digitize a slough as a *separate polygon lying on top of* the field polygon rather than as a proper ring; Plover handles both. When this happens the plugin logs: `Treated a fully-enclosed boundary feature as an exclusion zone (hole).`
- **Invalid polygons are repaired where possible.** If a feature fails a GEOS validity check, Plover calls `makeValid()` and logs `Repaired an invalid boundary polygon with makeValid().` If the repair produces nothing usable, the feature is dropped with `Skipped an invalid boundary polygon that could not be repaired.`
- If the layer ends up contributing no usable polygons at all, the dialog reports `The boundary layer contains no usable polygons.` and Processing raises `Boundary layer contains no usable polygons.`

#### 1.3.4 Holes, interior rings and exclusion zones

A polygon in GIS has one **exterior ring** (the outline) and may have any number of **interior rings**, also called **holes**. A hole is a piece of the plane that is inside the outline but *not* part of the polygon.

In agronomic terms, an interior ring is the natural way to represent anything inside the field you must not drive through or walk across:

- sloughs, potholes and wetlands
- dugouts and water bodies
- bush, treed shelterbelts, riparian buffers
- rock piles, sinkholes, badly rutted ground
- yard sites, structures, fenced exclusions
- environmentally sensitive areas you are contractually or legally required to avoid

Throughout this guide these are referred to interchangeably as **holes**, **interior rings** or **exclusion zones**. Plover treats all three of the following identically:

1. A true interior ring digitized inside a field polygon.
2. A separate polygon feature that is fully enclosed by a larger polygon feature in the same layer (auto-subtracted, as described above).
3. Any combination of the two, across multiple features and multipart geometries.

Because a hole is not part of the polygon's interior, Plover's containment test naturally refuses any straight leg that would cross it. **You do not switch obstacle avoidance on** — it is a consequence of the geometry you supply.

#### 1.3.5 "Boundary-aware", and how it is achieved

**Boundary-aware** means the drawn route only ever consists of straight segments that lie inside the (buffered) boundary region. A leg between two waypoints is therefore not necessarily a straight line: if a straight line would leave the field or cross a slough, Plover bends the leg around the obstruction, and the *distance* it uses when optimizing the order is the length of that bent path, not the straight-line distance.

That last point is the important one agronomically. Two points on opposite sides of a large slough may be 200 m apart as the crow flies but 900 m apart as the quad drives. A plain straight-line optimizer will happily pair them as "neighbours" and produce an order that is terrible on the ground. Plover uses the real, obstacle-aware distance when it chooses the order, so the order it returns is optimized for the trip you will actually make.

Mechanically, Plover does this with a **visibility graph**:

1. **Nodes.** The waypoints, plus a small set of boundary vertices. Only vertices where a taut, shortest path could ever *turn* are kept — concave corners of the field outline and the corners of holes that stick into the field. Convex field corners and vertices that sit in a straight line along an edge can never appear on a shortest path, so they are discarded. A rectangular field with no holes contributes **zero** boundary nodes.
2. **Edges.** Two nodes are joined, with their straight-line distance as the weight, if and only if the straight segment between them lies inside the buffered region. Coincident nodes (a waypoint sitting exactly on a kept boundary vertex) are joined with a zero-cost hop.
3. **Distances.** Dijkstra's algorithm is run once from each waypoint over that graph, giving the true obstacle-aware shortest distance — and the actual path — between every pair of waypoints.
4. **Order.** The optimizer works on that distance matrix (section 1.6).
5. **Route.** The chosen order is expanded back into a continuous polyline using the cached paths, so every bend around every slough is preserved in the output line.


[[FIGURE: map-compare | The same twelve points routed with no boundary (straight lines crossing the slough) and with a boundary (legs bending around it). Note that the visiting order itself changes, not just the drawn lines.]]

#### 1.3.6 Buffer tolerance

The **boundary buffer** is a tolerance, in map units, around the boundary region. It answers the question: *how far outside the strict boundary is the route allowed to stray, and how far into an exclusion zone?*

The dialog exposes it as **`Boundary buffer:`**, a spin box with the suffix **` map units`**, two decimal places, a range of 0.00 to 1 000 000.00 and a default of **0.5**. Its tooltip reads:

> Tolerance around the boundary: the route may pass this far
> outside the field edge and this far into exclusion zones.

Processing exposes the same thing as the **`Boundary buffer`** distance parameter (`BUFFER`), default `0.5`, minimum `0.0`, with its distance units tied to the boundary layer.

Why a tolerance is needed at all:

- **Points on the edge.** GEOS's `contains` test excludes the polygon's own boundary line. With a buffer of exactly zero, a segment running precisely along the field edge would be rejected, and a sample point digitized exactly on the boundary line would be unreachable. Plover therefore always applies at least a microscopic whisker (`1e-6` map units) even if you set the buffer to 0. A realistic buffer such as the 0.5 default lets the route genuinely hug the field edge.
- **Digitizing slop.** Field boundaries and sample points frequently come from different sources — GPS walk-arounds, satellite tracing, a prescription file — and disagree by a metre or two. The buffer absorbs that disagreement instead of failing the run.
- **The containment check.** The buffer is also what the "points outside the boundary" check is measured against: a point is "outside" only if it is outside the *buffered* region. Raising the buffer is the usual first fix when Plover reports points outside the boundary.

The trade-off is direct: a larger buffer is more forgiving of data problems, but it also lets the route cut further into your sloughs and further outside your field. Set it to roughly the accuracy of your worst input dataset, not larger. In a metric projected CRS the units are metres, so `0.5` means half a metre.

The buffer applies **only when a boundary is supplied**. With the **`Boundary layer:`** dropdown left empty, the dialog disables the buffer spin box.

#### 1.3.7 Round trip versus one-way

- **Round trip (closed tour)** — the default. The dialog checkbox **`Return to start (round trip)`** is ticked by default; the Processing parameter is **`Return to start (round trip)`** (`ROUND_TRIP`, default `True`). The route ends with a leg from the last stop back to the start point, and the `round_trip` attribute on the output route is written as `yes`. Use this when you park the truck, walk or drive the points, and come back to the truck.
- **One-way (open path)** — untick the checkbox, or pass `ROUND_TRIP: False`. No return leg is added; the `round_trip` attribute is written as `no`. Use this when someone drops you at one end of the field and picks you up at the other, when the route ends at a gate or an approach on the far side, or when the route feeds into the next field's work.

The distinction changes more than just the last leg — it changes what "optimal" means, and Plover's optimizer accounts for it. A closed tour's length does not depend on where the cycle starts, so for round trips Plover is free to try several construction starting points and rotate the winning cycle back to your chosen start afterwards. An open path must genuinely begin at your chosen start, so that freedom does not exist.


#### 1.3.8 The boundary is optional

You may leave the boundary out entirely: leave **`Boundary layer:`** empty in the dialog, or omit / pass `None` for `BOUNDARY` in Processing.

What changes when you do:

| Behaviour | With a boundary | Without a boundary |
|---|---|---|
| Legs between waypoints | Bend around the field edge and holes | Always straight lines |
| Distances used for optimizing | Obstacle-aware shortest-path distance | Plain straight-line (Euclidean) distance |
| Graph built | Visibility graph over waypoints plus concave boundary/hole corners | Complete graph: every waypoint connected to every other |
| **`Boundary buffer:`** | Active | Disabled in the dialog; not applicable |
| **`Points outside boundary:`** | Active | Disabled in the dialog; no containment check runs |
| Unreachable-point check | Applies (a point can be cut off by a hole or a pinch) | Cannot occur — every point reaches every other |
| Working CRS | The **boundary** layer's CRS; points are reprojected to it | The **point** layer's CRS |
| Result | Boundary-aware TSP | Ordinary Euclidean TSP |

In short: without a boundary Plover is still a genuine TSP solver and still gives you a good visiting order and a numbered visit-order layer — it just has no idea what it is not allowed to drive across.


#### 1.3.9 Working CRS and why geographic coordinates are rejected

Plover measures distance with ordinary planar arithmetic, so its inputs must be in a **projected CRS** (UTM, a NAD83 provincial system, and so on) where one map unit is one linear unit on the ground.

- The **working CRS** is the boundary layer's CRS when a boundary is supplied, otherwise the point layer's CRS.
- The point layer is **automatically reprojected** to the working CRS if it differs. The dialog logs `Reprojecting points from … to … for routing.`
- If the working CRS is **geographic** (degrees — EPSG:4326 and similar) Plover refuses to run. The dialog reports that distances "would be meaningless" and asks you to reproject to a projected CRS such as UTM; Processing raises an equivalent `QgsProcessingException`.

All outputs are created in the working CRS. Only the GPX and KML exports are reprojected on the way out, to WGS84, because those formats require it.

#### 1.3.10 Terminology quick reference

| Term | Meaning in Plover |
|---|---|
| Waypoint | One point feature to be visited |
| Stop | A waypoint's position in the final visiting order (1, 2, 3 …) |
| Tour | A closed route that returns to the start |
| Path | An open, one-way route |
| Boundary / region | The merged polygon area the route must stay within |
| Hole / interior ring / exclusion zone | Area inside the boundary outline that the route must avoid |
| Buffer | Tolerance in map units around the boundary and exclusion zones |
| Visibility graph | Nodes (waypoints + turn vertices) joined where the straight line between them is legal |
| Turn vertex | A boundary corner where a shortest path could bend: concave field corners, hole corners |
| Leg | One segment of the route, from one stop to the next |
| Working CRS | The projected CRS all routing maths is done in |
| Map units | The linear unit of the working CRS — metres in a metric projection |

### 1.4 The two ways to run Plover

Plover offers the same routing engine through two front ends. Both call the identical `compute_route` pipeline, so a given set of inputs produces the same route either way.

#### 1.4.1 The dialog

Best for interactive, one-off work: you are looking at a field, you want a route now, and you want to eyeball it before saving.

1. Open QGIS with your point layer (and boundary layer, if you are using one) loaded.
2. Choose **Vector → Plover → Plover — Generate TSP Route**, or click the Plover toolbar button (status tip: `Boundary-aware TSP route through a point layer`).
3. The window **`Plover — TSP Route`** opens.

The dialog is **modeless** — the map stays fully usable while it is open, so you can pan, zoom, select features and re-run without closing it. Routing runs in a **background task**, so QGIS stays responsive, a live progress bar is shown, and long runs can be stopped with the **`Cancel`** button.

Dialog controls, in the order they appear:

| Control | Purpose |
|---|---|
| **`Points to visit:`** | Point-layer dropdown; tracks the layers in your project |
| **`Use only selected points`** | Route only the current selection on that layer |
| **`Boundary layer:`** | Polygon-layer dropdown; **may be left empty** |
| **`Start at point:`** | Feature picker for the starting waypoint |
| **`Boundary buffer:`** | Tolerance in map units (default 0.5); disabled with no boundary |
| **`Points outside boundary:`** | `Fail if any point is outside` / `Skip points outside the boundary`; disabled with no boundary |
| **`Return to start (round trip)`** | Ticked = closed tour, unticked = one-way path |
| **`Also create a numbered visit-order layer`** | Ticked by default |
| **`Total distance:`** | Read-only result field (placeholder: `Route length will appear here`) |
| Progress bar and status line | Live progress; the status line starts at `Ready.` |
| **`Run`** / **`Cancel`** / **`Save Route…`** / **`Close`** | Action buttons |

The dialog remembers the buffer, round-trip setting, visit-order-layer setting, outside-points mode and last save directory between sessions.


#### 1.4.2 The Processing algorithm

Best for repeatable, automated or bulk work: batch processing many fields, embedding routing in a Model Designer workflow, or scripting from PyQGIS.

Find it at **Processing Toolbox → Plover → Boundary-aware TSP route**. Its algorithm id is **`plover:tsproute`**.

| Parameter id | Label | Notes |
|---|---|---|
| `POINTS` | `Points to visit` | Point source, required |
| `BOUNDARY` | `Boundary polygon(s)` | Polygon source, **optional** |
| `BUFFER` | `Boundary buffer` | Distance, default `0.5`, minimum `0.0` |
| `START_INDEX` | `Start point index (order of the input layer)` | Integer, default `0`, minimum `0` — **zero-based** |
| `ROUND_TRIP` | `Return to start (round trip)` | Boolean, default `True` |
| `ON_OUTSIDE` | `Points outside the boundary` | Enum: `0` = `Fail if any point is outside`, `1` = `Skip points outside the boundary` |
| `OUTPUT_ROUTE` | `Route` | Line sink, required |
| `OUTPUT_ORDER` | `Visit order` | Point sink, optional, created by default |

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


#### 1.4.3 Choosing between them

| | Dialog | Processing |
|---|---|---|
| Start point chosen by | Feature picker (pick the actual feature) | Zero-based `START_INDEX` into the layer's feature order |
| Output layers | Added to the project, pre-styled (orange route with direction arrows; numbered orange badges) | Written to whatever sinks you specify; default QGIS styling |
| Export to GPX / KML | Yes, via **`Save Route…`** | Not built in — save the output layer yourself |
| Batch over many fields | No | Yes |
| Use inside a model | No | Yes |
| Progress and cancelling | Progress bar plus **`Cancel`** | Processing's own progress and cancel |
| Messages | Plover log panel (**View → Panels → Log Messages → Plover**) and the status line | The algorithm's Log tab |

### 1.5 What Plover produces

Covered in detail in a later chapter; in outline:

- A line layer named **`Plover route`** (dialog) or the **`Route`** output (Processing), containing one feature — the full stitched polyline — with the fields `length`, `stops` and `round_trip`.
- Optionally a point layer named **`Plover visit order`** (dialog) or the **`Visit order`** output (Processing), with one point per stop and the fields `visit_order` (1, 2, 3 …), `source_fid` (the feature id of the original input point) and `leg_length` (the length of the leg leaving that stop).
- From the dialog only, **`Save Route…`** exports the route to GeoPackage, Shapefile, GeoJSON, **GPX track** or **KML**. GPX and KML are reprojected to WGS84 automatically, so a GPX can be loaded straight onto a handheld or a phone app for field navigation.


### 1.6 Plover is a heuristic solver — what that means

This is the single most important expectation to set, so it is stated plainly.

Plover's order optimizer (`tsp_core.solve_order`) works like this:

1. **Multi-start nearest-neighbour construction.** Build a first order greedily by always hopping to the closest unvisited waypoint. For round trips, several different construction starting points are tried and the best result kept — 8 starts for up to 150 points, 4 starts for up to 400, 2 starts above that. One-way paths use a single start, because an open path must genuinely begin at your chosen point.
2. **2-opt local search.** Repeatedly reverse a section of the order when doing so shortens the route. This is what removes the crossings that make a route look obviously silly.
3. **Or-opt local search.** Repeatedly lift a run of one, two or three consecutive stops out of the order and reinsert it elsewhere (possibly reversed) when that shortens the route. This catches improvements 2-opt cannot express, such as pulling a single stop out of a detour.
4. Alternate 2-opt and Or-opt until neither can improve the route any further, and keep the best of all construction starts.

**Consequences you should understand:**

- **The result is very good but not provably optimal.** Tours are typically within a few percent of the true optimum. Plover will not tell you how far off it is, because computing that would mean solving the problem exactly.
- **The result is deterministic.** The same inputs and the same settings give the same route every time — there is no randomness. It is safe to re-run and compare.
- **Small manual improvements may exist.** If you look at a route and think "I would have done those two stops the other way round", you may occasionally be right. You are not seeing a bug.
- **It is a distance optimizer only.** It does not model time, speed, terrain difficulty, ground conditions, machinery turning radii, seeding row direction, tramlines, gates or approaches. A leg is a straight line through legal space, nothing more.
- **Distance is measured in map units of the working CRS.** In a metric projection that is metres. Plover never converts to acres, hours or fuel.

### 1.7 When should I use Plover?

Plover is a good fit when **all** of the following are true:

- You have a point layer with **at least two** point features. (Fewer is refused: `Need at least two point features to build a route.`)
- Your data is in, or can be reprojected to, a **projected CRS**.
- Travel between points is essentially **across open ground** — you go where you like within the field, rather than following a road or trail network.
- You care about the **order** of visits, and about not crossing certain areas.

Typical jobs it was built for:

- **Soil sampling routes** — a grid or zone sampling plan turned into an efficient walking or quad order.
- **Pest and disease scouting** — a set of scouting stops ordered for one pass through the field.
- **Ground-truth and plot work** — research plot visits on Smart Farm-style trial sites.
- **Manual sensor verification** — checking or downloading a set of in-field sensors.
- **Any "visit N points in a constrained area" problem** where sloughs, bush or the field edge genuinely constrain travel.

Cases where the **boundary is worth supplying** (as opposed to leaving it empty):

- The field contains sloughs, wetlands, bush or other no-go areas.
- The field is concave, L-shaped, split by a creek, or otherwise not a simple convex block.
- The route is being handed to somebody who will follow it literally, including on a GPS handheld.
- You have one large point layer covering many fields and want to route only the points inside one field — use the boundary together with `Skip points outside the boundary`.

Cases where **leaving the boundary empty** is fine:

- The field is a simple open block with nothing to avoid.
- You only want the visiting *order*, and the operator will navigate around obstacles by eye.
- You do not have a boundary polygon and it is not worth digitizing one.


### 1.8 When is Plover not the right tool?

Be honest about these up front rather than discovering them mid-season.

| Situation | Why Plover does not fit | What to do instead |
|---|---|---|
| Travel must follow roads, trails or tramlines | Plover routes across open space between visibility-graph vertices. It has no concept of a road network, one-way streets, speed limits or turn restrictions. | Use a network-analysis tool (QGIS's own network analysis, or a routing service) |
| You need a provably optimal tour | The solver is heuristic (multi-start nearest-neighbour + 2-opt + Or-opt) | Use a dedicated exact TSP solver; expect it to be far slower |
| Multiple vehicles or crews, capacity limits, time windows, shifts | Plover solves a single-vehicle TSP with no side constraints | Use a vehicle-routing (VRP) tool |
| Your data is in EPSG:4326 or another geographic CRS and must stay that way | Plover refuses geographic CRS outright — degree-based distances would be meaningless | Reproject to a projected CRS (UTM or your provincial system) before routing |
| Terrain, slope, wet spots, machinery turning radii or row direction should influence the route | None of these are modelled; a leg is a straight line through legal space | Digitize the areas to avoid as holes in the boundary, which Plover *does* respect |
| Full-coverage work: spraying, seeding, harvest passes | Plover visits discrete points; it does not plan coverage passes over an area | Use coverage/guidance path-planning software |
| You have only one point | A route needs at least two points | — |
| You want Plover to guess a route to a point it cannot legally reach | It never does. With a boundary, out-of-boundary points are either reported (fail mode) or dropped (skip mode), and points cut off by a hole or a pinch in the boundary are reported by number rather than silently straight-lined. | Fix the boundary, raise the buffer, or switch to skip mode |

### 1.9 Where to go next

- **Installation and first run** — getting the plugin into QGIS and producing your first route.
- **The dialog, control by control** — every field, checkbox and button in `Plover — TSP Route`.
- **The Processing algorithm** — batch runs, models and PyQGIS.
- **Outputs, styling and export** — the route and visit-order layers, and GPX/KML for the field.
- **Troubleshooting** — the exact messages Plover produces and what to do about each.

### 1.10 Why "Plover"

Piping Plovers are small shorebirds that nest on Alberta's prairie shorelines. They walk fast, in tight efficient zig-zags between feeding points, and they work around the obstacles in their path rather than through them — a reasonable mascot for a boundary-aware TSP tool. Plover is one of a family of bird-named QGIS plugins alongside Perch and Lapwing.