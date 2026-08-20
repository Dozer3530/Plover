## 5. Step-by-Step Workflows

This chapter is a set of self-contained recipes. Each one is a complete procedure you can follow from an empty QGIS project to a finished route. Work through **5.1** first — the later recipes assume you have done it once and refer back to it rather than repeating every click.

Everything here describes the **dialog**. Where the same job can be done from the Processing Toolbox, a short note names the exact parameters; the Processing algorithm itself is documented in its own chapter.

---

### 5.0 Things that apply to every recipe

Read this once. It saves repeating the same five warnings eight times.

#### Opening Plover

Plover installs into two places:

1. **Vector → &Plover → Plover — Generate TSP Route**
2. The **Plover — Generate TSP Route** toolbar button (status tip: `Boundary-aware TSP route through a point layer`)

Either opens the dialog, whose window title is **Plover — TSP Route**. The dialog is *modeless*: you can pan, zoom, select features and open the attribute table while it is open. It stays open after a run, so you can change one setting and run again.

#### Pre-flight checklist

| Check | Why | What happens if you skip it |
|---|---|---|
| Point layer is a **point** layer | Only point layers appear in **Points to visit:** | The layer will not be listed in the dropdown |
| Boundary layer is a **polygon** layer | Only polygon layers appear in **Boundary layer:** | The layer will not be listed in the dropdown |
| Working CRS is **projected** (UTM, NAD83 / Alberta 10-TM, …) | Distances must be in linear units | Plover refuses to run: `The boundary layer uses a geographic CRS (degrees). Distances would be meaningless — reproject to a projected CRS (e.g. UTM) first.` (the message says `point layer` when there is no boundary) |
| At least **two** usable points | A route needs two ends | `Need at least two point features to build a route.` |

The **working CRS** is the boundary layer's CRS when you choose a boundary, and the point layer's CRS when you do not. If the points are in a different CRS from the boundary, Plover reprojects the points to the working CRS automatically and notes it in the log. It is the *working* CRS that has to be projected.

#### Where messages appear

- **Status line** at the bottom of the dialog — starts as `Ready.`, turns dark red for errors.
- **Total distance:** read-only box — placeholder `Route length will appear here`, then e.g. `12,345.6 map units`.
- **Log Messages Panel**, tab **Plover** (`View → Panels → Log Messages`) — per-point diagnostics, skipped features, reprojection notes, boundary repairs. Whenever a recipe says "check the log", this is what it means.

#### Two facts that surprise new users

- **Every run adds new layers.** A run creates a fresh memory layer called **Plover route**, and (if the checkbox is ticked) a fresh **Plover visit order**. Running again does not overwrite them — you end up with several layers of the same name. Delete the old ones as you iterate.
- **The output layers are temporary.** They are scratch (memory) layers and disappear when the project closes. Use **Save Route…** to write the route to a file. Note that **Save Route… writes the route line only** — if you also need the numbered points on disk, export **Plover visit order** with QGIS's own layer export.

#### Settings Plover remembers

Between sessions Plover restores **Boundary buffer**, **Return to start (round trip)**, **Also create a numbered visit-order layer** and **Points outside boundary:**. It does **not** remember the chosen layers, the selection checkbox or the start point. Always glance at the checkboxes before clicking **Run** — they may be set the way you left them last week.

---

### 5.1 Recipe 1 — Your first route: a round trip inside a field boundary

#### When to use this

The standard job. You have a set of sample or scouting points that all sit inside one field, and you want the shortest walking or driving loop that visits all of them and returns to where you parked.

#### Steps

1. Start QGIS and open (or create) the project holding your data.
2. Load the **point layer** of places to visit, and the **polygon layer** holding the field boundary.
3. Confirm the CRS of the boundary layer is projected. In the **Layers** panel, hover the layer (or open `Layer Properties → Information`) and look for something like `EPSG:32612 - WGS 84 / UTM zone 12N`, not `EPSG:4326`. If it is geographic, reproject it before continuing.
4. Open **Vector → &Plover → Plover — Generate TSP Route** (or click the toolbar button).
5. In **Points to visit:**, choose your point layer. The **Start at point:** picker fills itself from whichever layer you choose here.
6. Leave **Use only selected points** unticked (recipe 5 covers selections).
7. In **Boundary layer:**, choose your field polygon. As soon as a boundary is chosen, **Boundary buffer:** and **Points outside boundary:** become enabled — they are greyed out while the boundary is empty because they have nothing to act on.
8. Leave **Start at point:** alone for now, or pick the point you want to begin at (recipe 6 explains it properly). If nothing sensible is chosen, Plover starts at the first point in the layer.
9. Leave **Boundary buffer:** at `0.50 map units` unless you already know your points sit exactly on the field edge (recipe 8).
10. Leave **Points outside boundary:** on `Fail if any point is outside`. For a first run this is the safest setting — it tells you loudly if a point is not where you think it is.
11. Tick **Return to start (round trip)**.
12. Tick **Also create a numbered visit-order layer**.
13. Click **Run**.

While it runs: the progress bar fills, the status line reads `Routing 47 points…` (with your count), and every input widget is disabled. **Cancel** is enabled throughout — click it to stop a long solve; the status changes to `Cancelling…` and then to `Cancelled.`

[[FIGURE: map-route | A finished round trip: the orange route line with direction arrows, the numbered visit-order badges, and the field boundary.]]

#### What you should see

- The status line turns to something of this shape:

  `Done — 47 stops, 6,405.2 units (round trip). Visibility graph: 63 nodes / 1,204 edges.`

- **Total distance:** shows e.g. `6,405.2 map units`.
- Two new layers appear in the **Layers** panel:

  | Layer | Geometry | Styling | Fields |
  |---|---|---|---|
  | **Plover route** | one LineString feature | orange (`#e8590c`) line with filled arrowheads showing direction of travel | `length` (double), `stops` (integer), `round_trip` (`yes` / `no`) |
  | **Plover visit order** | one point per stop | orange circles with a white outline, labelled with a bold white number and a dark halo | `visit_order` (integer, 1..n), `source_fid` (integer), `leg_length` (double) |

- **Save Route…** is now enabled.

If the new layers are not in view, right-click **Plover route** in the Layers panel and use QGIS's **Zoom to Layer**.

[[FIGURE: order-layer-zoom | Close-up of the visit-order layer: orange badges numbered 1, 2, 3 … along the route.]]

#### Reading the outputs

- `visit_order` is the sequence you follow: 1 first, then 2, and so on.
- `source_fid` is the feature ID of the original point in your input layer, so you can join the route order back to your own attributes.
- `leg_length` is the length of the leg **leaving** that stop. On a round trip the last stop's `leg_length` is the closing leg back to stop 1. On a one-way route the last stop's `leg_length` is `0`, because nothing leaves it.
- `stops` on the route layer equals the number of points actually routed — which can be lower than the number of points in your layer if any were skipped (recipe 3).

#### Saving it

1. Click **Save Route…**.
2. Choose a folder and file name in the **Save Route** dialog and pick a format: **GeoPackage (\*.gpkg)**, **Shapefile (\*.shp)**, **GeoJSON (\*.geojson)**, **GPX track (\*.gpx)** or **KML (\*.kml)**.
3. Click Save. The layer inside the file is named `plover_route`.

GPX and KML are written in WGS84 (`EPSG:4326`) — Plover reprojects on the way out, so a `.gpx` can be loaded straight onto a handheld GPS or a phone app. If you save to a GeoPackage that already contains a `plover_route` layer, Plover asks (dialog title **Layer already exists**): **Yes** overwrites it, **No** adds a timestamped layer such as `plover_route_20260820_143012`, **Cancel** aborts the save. On success the status line reads `Route saved to C:\...\route.gpkg`.

---

### 5.2 Recipe 2 — Routing around a slough or other exclusion zone

#### When to use this

The field has something in it you must not drive or walk through: a slough, a wetland, a rock pile, a fenced-off trial block, a construction area. You want the route to go *around* it rather than straight across.

#### How to represent the exclusion zone

Plover recognises two forms, and the difference matters:

| How the slough is digitized | What Plover does |
|---|---|
| As an **interior ring (hole)** in the field polygon | The hole is not part of the polygon interior, so no route segment can cross it. Works directly. |
| As a **separate polygon feature, entirely inside** the field polygon, in the same boundary layer | Plover detects that it is fully contained and **subtracts** it, logging `Treated a fully-enclosed boundary feature as an exclusion zone (hole).` |
| As a separate polygon that **overlaps or pokes out of** the field polygon | It is **not** subtracted — it is unioned into the region, making the routable area *bigger*. This is almost never what you want. |

So: an exclusion polygon must be **wholly inside** the field polygon, or be a real hole. If part of your slough hangs over the field edge, clip it to the field first.

Plover also merges all boundary features into one routing region: the largest-area polygon is the base, fully-contained features are subtracted, and everything else is unioned. Invalid polygons are repaired where possible (log note `Repaired an invalid boundary polygon with makeValid().`) or dropped (`Skipped an invalid boundary polygon that could not be repaired.`).

#### Steps

1. Load the point layer and the boundary layer that contains the field and its slough.
2. Confirm the slough is a hole in the field polygon, or a separate polygon fully inside it. Use QGIS's editing/geometry-checking tools to fix it if not.
3. Open Plover. Set **Points to visit:** and **Boundary layer:**.
4. Set **Boundary buffer:** to a **small** value — `0.50` is a sensible default. The buffer is a two-way tolerance: it lets the route stray that far outside the field edge **and** that far *into* the exclusion zone. A 20-unit buffer means the route is allowed to clip 20 units into your slough.
5. Leave **Points outside boundary:** on `Fail if any point is outside` — if a sample point has accidentally been placed inside the slough, you want to know.
6. Click **Run**.
7. Open the **Log Messages Panel → Plover** tab and confirm you see the exclusion-zone note if you relied on a separate polygon.

#### What you should see

- A route that bends around the slough instead of crossing it, with the bends occurring at the slough's corners. Plover only adds *turn vertices* to its graph — the concave corners of the field and the corners of holes — because a taut shortest path can only ever bend there.
- The status line's `Visibility graph: N nodes / M edges` count will be larger than for a plain rectangular field, because the hole contributes nodes.

#### Troubleshooting

- **`4 point(s) cannot be reached from the start point (point number 12, 13, 27, 31). They are likely separated by a hole/exclusion zone or a pinched-off part of the boundary. Increase the buffer distance or check the boundary geometry.`**
  This means the exclusion zone (or a pinch in the field outline) has cut part of the field off from the start. Common causes: a slough that touches both sides of the field and splits it in two; a boundary drawn as two polygons that touch only at a single point; a buffer of `0` with a very narrow gap. The numbers in brackets are the **positions of the points in the routing set** (1-based), not feature IDs — count from the beginning of the routed point list, and remember the list is shorter than your layer if points were skipped.
  Fixes, in order of preference: widen the real gap in the geometry, increase **Boundary buffer:** slightly, or exclude the cut-off points from the run.

- **The route crosses the slough anyway.** Either the slough is a separate polygon that is not fully inside the field polygon (so it was unioned, not subtracted), or the **Boundary buffer:** is large enough to swallow the slough. Check both.

---

### 5.3 Recipe 3 — One point layer covering many fields: route only the current field

#### When to use this

You have one master point layer — every sample site on the farm, or every scouting point for the season — and you want a route for **one** field only, without splitting the layer or making a selection by hand. You supply that field's boundary and let Plover discard everything else.

#### Steps

1. Load the master point layer and the boundary layer for the single field you want to route. If the boundary layer contains many fields, filter or select it down to the one field first — Plover merges *all* features in the boundary layer into one region, so a multi-field boundary layer would route across all of them.
2. Open Plover.
3. Set **Points to visit:** to the master point layer.
4. Set **Boundary layer:** to the single-field boundary.
5. Set **Boundary buffer:** as usual (`0.50` unless edge points need more — see recipe 8). Remember: the buffer decides what counts as "inside" for this test, so a large buffer will pull in points from just over the fence line.
6. Set **Points outside boundary:** to **`Skip points outside the boundary`**.
7. Set **Start at point:** if you have a preferred first stop (see the start-point note below).
8. Click **Run**.

[[FIGURE: map-skip | A master point layer spanning four fields. Only the points inside the highlighted field are routed; the rest are ignored.]]

#### Exactly what gets dropped

Two different filters run, in this order:

1. **Unusable features are dropped before anything else**, whether or not you use skip mode. A feature is dropped if it has no geometry or an empty geometry (`Skipping feature 118: empty geometry.`), if it is not a point (`Skipping feature 119: not a point.`), or if it cannot be reprojected into the working CRS (`Skipping feature 120: reprojection failed.`). Multipart points are **not** dropped — Plover uses their centroid.
2. **The containment test.** Plover buffers the merged boundary by the **Boundary buffer:** value and keeps only the points that fall inside (or exactly on the edge of) that buffered region. Every point that fails is logged individually, with its distance from the *unbuffered* boundary:

   `Point fid=204 at (412355.10, 5765990.44) is 187.63 units outside the boundary.`

   In skip mode those points are then removed from the routing set, and a summary is logged:

   `Skipping 312 point(s) outside the boundary; routing the 18 inside.`

Skipped points are simply not routed. Nothing is deleted, edited or moved in your source layer, and — unlike fail mode — skip mode does **not** change the layer's selection.

If fewer than two points survive, the run stops with:

`Only 1 point(s) fall inside the boundary — need at least two to build a route. Increase the buffer or pick a boundary that contains more points.`

#### How the start point is re-resolved when your chosen start was skipped

This is the part that catches people out. The start point is resolved **after** the skipping, against the surviving point list:

1. If the feature chosen in **Start at point:** is still in the routed set, the route starts there. Nothing unusual happens.
2. If it is **not** in the routed set, Plover falls back to **the first point of the surviving list** — that is, the first in-boundary point in the order the layer returned its features (normally the lowest feature ID that survived). It does not fail, and it does not warn you in the dialog.
3. If the reason it is missing is that it was skipped as outside the boundary, Plover writes a warning to the log:

   `Chosen start point lies outside the boundary and was skipped; starting from the first in-boundary point instead.`

So if your start matters, always check the log after a skip-mode run, or pick a start that you know is inside the field.

#### What you should see

- The status line includes the skipped count:

  `Done — 18 stops, 2,140.7 units (round trip). Skipped 312 point(s) outside the boundary. Visibility graph: 22 nodes / 231 edges.`

- **Plover visit order** contains one point per *routed* stop only. Its `source_fid` values let you trace each stop back to the master layer.
- The `stops` field on **Plover route** equals the routed count (18 above), not the size of the input layer.

#### Doing the same in Processing

Run **Boundary-aware TSP route** (`plover:tsproute`) with `ON_OUTSIDE` set to `1` (`Skip points outside the boundary`). The Processing version behaves the same way, with one difference worth knowing: the start is given as `START_INDEX` (a position in the input layer, 0-based, validated *before* skipping). Plover remembers which feature that index referred to, and after skipping either re-finds it or falls back to the first surviving point with the warning `Start point lies outside the boundary and was skipped; starting from the first in-boundary point instead.`

---

### 5.4 Recipe 4 — A one-way route (no return to start)

#### When to use this

- You will be picked up at the far end, or you carry on to the next field from wherever you finish.
- The field entrance and exit are different gates.
- You are planning a transect or a pass that ends at a road, a shed or a bin.

A one-way route is always the same length or shorter than the equivalent round trip, because the closing leg is not counted — do not compare the two numbers as if they measure the same thing.

#### Steps

1. Set up the run exactly as in recipe 1 (points, boundary if any, buffer, outside-points mode).
2. Choose the point where you want to **begin** in **Start at point:**. For a one-way route this matters much more than for a round trip — see "What you cannot control" below.
3. **Untick** **Return to start (round trip)**.
4. Click **Run**.

[[FIGURE: map-oneway | A one-way route: the arrows run from stop 1 to the final stop, with no closing leg back to the start.]]

#### What you should see

- The status line says `one-way path` instead of `round trip`:

  `Done — 24 stops, 3,812.4 units (one-way path). Visibility graph: 31 nodes / 402 edges.`

- On **Plover route**, the `round_trip` field is `no`.
- The drawn line ends at the last stop; there is no leg from the last badge back to badge 1.
- In **Plover visit order**, the highest-numbered stop has `leg_length` `0`, because no leg leaves it.

#### What you cannot control

You choose where the route **starts**. You cannot choose where it **ends** — the optimizer picks the finishing point as part of minimising the total length. If you need to finish at a specific gate, the practical approach is to run the route twice (once starting at each candidate gate) and compare the results, or to place the route by choosing the start that puts the far end where you want it.

Also note the difference in how the solver treats the two modes. For a round trip, the loop's length does not depend on where you start it, so Plover tries several construction starts spread across the points and rotates the winning loop back to your chosen start. For a one-way route only **your** start is used, and the optimizer is additionally free to reverse the tail of the path. The upshot: a one-way result depends genuinely on the start you pick, so it is worth trying two or three.

#### Doing the same in Processing

Set `ROUND_TRIP` to `False`.

---

### 5.5 Recipe 5 — Routing only selected points

#### When to use this

- Today you only need to revisit the points that failed QC, or only the ones due for sampling this week.
- The layer covers several fields and you would rather pick the points by hand than by boundary.
- You want a quick "what if" route over a handful of points without editing any data.

#### Steps

1. Load the point layer and make it the active layer in the **Layers** panel.
2. Select the points you want, using any normal QGIS method:
   - the **Select Features by area or single click** tool, holding <kbd>Ctrl</kbd> to add to the selection;
   - **Select Features by Value** or an expression select;
   - selecting rows in the attribute table.
3. Confirm the selection count in the QGIS status bar before continuing.
4. Open Plover (or bring the already-open dialog to the front — selecting features on the map does not disturb it).
5. Set **Points to visit:** to that layer.
6. Tick **Use only selected points**.
7. Set the boundary, buffer and outside-points mode as needed.
8. Set **Start at point:** — see the caution below.
9. Click **Run**.

#### What you should see

- The status line during the run counts only the selected points: `Routing 9 points…`
- The finished route visits exactly the selected points; unselected points are ignored entirely, even if they sit right on the line.

#### Cautions specific to selections

- **Empty selection.** If the box is ticked but nothing is selected, Plover refuses to run with:

  `'Use only selected points' is on, but no points are selected.`

- **The start picker still lists the whole layer.** **Start at point:** is not filtered to your selection. If you pick a feature that is not in the selection, Plover starts at the first selected point instead and logs:

  `Chosen start point is not in the selection; starting from the first selected point instead.`

- **Your selection is preserved in fail mode.** Normally, when points fall outside the buffered boundary, Plover *selects* the offending features on the layer so you can find them. When **Use only selected points** is ticked it deliberately does not do this — otherwise it would destroy the selection you just made. The offending points are still listed in the log.
- **Fewer than two selected points** produces `Need at least two point features to build a route.`

#### Note

There is no equivalent tick-box in the Processing algorithm's own parameters — instead, use the **Selected features only** option that Processing offers on the `POINTS` input, or pre-filter the layer.

---

### 5.6 Recipe 6 — Choosing and changing the start point

#### When to use this

- You always park at the same gate or approach.
- You want the numbering on the visit-order layer to begin at a specific, recognisable point.
- You are planning a one-way route, where the start genuinely changes the path (recipe 4).

#### Steps

1. Set **Points to visit:** first. The **Start at point:** picker is bound to that dropdown — changing the point layer resets the picker to the new layer.
2. Click into the **Start at point:** widget and start typing to filter, or use the small browse arrows beside it to step through features one at a time.
3. Pick the feature you want. The widget shows features using the layer's display name, so if every entry looks blank or shows only a number, set a sensible display field in `Layer Properties → Display` (a site name or ID column) and reopen the picker.
4. Set everything else as usual and click **Run**.
5. To change the start, pick a different feature and click **Run** again — a new pair of output layers is created, so delete the previous **Plover route** / **Plover visit order** if you do not want them stacking up.

#### What you should see

- In **Plover visit order**, the badge numbered `1` sits on the point you chose.
- For a round trip, the loop closes back to that same badge.

#### What happens if you do not choose one

If no feature is chosen, or the chosen feature is not part of the routed set, Plover starts at **the first point in the routed list** — the first feature the layer returned that survived filtering. That is usually, but not guaranteed to be, the lowest feature ID. Two cases produce a log warning rather than silence:

| Situation | Result | Log message |
|---|---|---|
| The chosen start was skipped as outside the boundary (skip mode) | Starts at the first in-boundary point | `Chosen start point lies outside the boundary and was skipped; starting from the first in-boundary point instead.` |
| **Use only selected points** is on and the chosen start is not selected | Starts at the first selected point | `Chosen start point is not in the selection; starting from the first selected point instead.` |
| Nothing chosen at all | Starts at the first point in the routed list | (no message) |

#### How much does the start actually matter?

- **Round trip:** the length of a loop does not depend on where you enter it, so changing the start mainly changes where the numbering begins. Because your start is also one of the construction candidates the solver tries, the resulting loop can differ slightly from run to run with different starts, but the length should be close to identical.
- **One-way route:** the start is fixed by design and the path is built from it, so different starts give genuinely different — and differently long — routes.

#### Doing the same in Processing

The algorithm has no feature picker. Use `START_INDEX`, "Start point index (order of the input layer)", a 0-based position in the input layer's feature order. Out-of-range values fail with `Start point index must be between 0 and N-1.`

---

### 5.7 Recipe 7 — A quick route with no boundary at all

#### When to use this

- There is no obstacle worth modelling: an open field, a yard, a set of bins, a line of weather stations.
- You have not digitized a boundary and do not want to.
- You want a fast sanity check, or a baseline length to compare a boundary-constrained route against.

With no boundary the problem becomes an ordinary straight-line (Euclidean) travelling-salesperson tour: every point can go directly to every other point, and nothing is avoided.

#### Steps

1. Load the point layer. It must be in a **projected** CRS, because with no boundary it is the point layer's CRS that becomes the working CRS.
2. Open Plover.
3. Set **Points to visit:**.
4. Leave **Boundary layer:** on its **empty** entry (the blank item at the top of the dropdown). If a boundary is already selected from a previous run, choose the blank entry to clear it.
5. Notice that **Boundary buffer:** and **Points outside boundary:** grey out. That is expected — with no boundary there is nothing to buffer and nothing can be "outside". Whatever values they hold are ignored.
6. Set **Return to start (round trip)** and **Also create a numbered visit-order layer** as you want them.
7. Optionally set **Start at point:**.
8. Click **Run**.

[[FIGURE: map-noboundary | A straight-line tour with no boundary: legs run directly between points, crossing anything in their way.]]

#### What you should see

- A fast result — with no boundary there are no turn vertices to add, so the visibility graph has exactly as many nodes as you have points, and the `Visibility graph: N nodes / M edges` figures in the status line reflect a complete graph.
- Route legs that are dead-straight between consecutive stops, crossing sloughs, roads and fences without noticing them.
- No possibility of the "points outside the boundary" or "cannot be reached from the start point" errors — every point is reachable from every other by definition.

#### When not to use it

If there is anything in the field you must not cross, do not use this mode and eyeball the result. Draw the boundary and use recipe 2. Plover will not warn you that a straight leg went through the slough, because in this mode it has no idea the slough exists.

---

### 5.8 Recipe 8 — Re-running with a different buffer to fix edge points

#### When to use this

You ran with a boundary in fail mode and got:

`3 point(s) fall outside the buffered boundary (now selected on the layer; details in the log). Increase the buffer, switch 'Points outside boundary' to skip, or fix the data.`

…but you are fairly sure all the points *are* in the field. This is the classic case of points digitized right on the field edge, or a boundary traced slightly inside the true edge, where the points miss the polygon by centimetres.

#### What the buffer actually does

**Boundary buffer:** (default `0.50 map units`, two decimals, minimum `0.00`) is used in two places:

1. **The containment test.** A point counts as inside when it falls within the boundary grown outwards by the buffer distance.
2. **The routing region itself.** Route segments must stay inside that same grown region — which means the route may pass up to the buffer distance **outside** the field edge, and up to the buffer distance **into** any exclusion zone.

Both effects come from the same number, so the buffer is a genuine trade-off, not a free tolerance. Even a buffer of `0.00` gets a microscopic tolerance internally, so that a segment running exactly along the boundary line is not rejected.

The value is in the **working CRS's map units** — metres for UTM and most projected agricultural CRSs.

#### Steps

1. Do not change anything yet. Open **View → Panels → Log Messages** and click the **Plover** tab.
2. Find the per-point lines from the failed run. Each names the feature ID, the coordinates, and the distance from the field boundary:

   ```
   Point fid=57 at (412355.10, 5765990.44) is 0.31 units outside the boundary.
   Point fid=61 at (412420.88, 5766014.02) is 1.12 units outside the boundary.
   Point fid=63 at (412498.55, 5766040.71) is 0.44 units outside the boundary.
   ```

3. Note the **largest** distance — `1.12` in this example.
4. Look at the offending points on the map. Fail mode has already **selected them on your point layer**, so open the attribute table and switch it to **Show Selected Features** to inspect them, or just zoom to the selection. Confirm they are edge points and not, say, a point in the wrong field or a point in the wrong CRS.
5. Back in the Plover dialog, set **Boundary buffer:** to a little more than the largest reported distance — `1.50` here. Round up rather than matching exactly; the distance reported is to the strict boundary and a small margin avoids borderline failures.
6. Click **Run** again.
7. If it now succeeds, sanity-check the drawn route: with a 1.5 unit buffer the line is allowed to cut 1.5 units outside the field edge and 1.5 units into any slough. At field scale that is usually irrelevant; if your exclusion zone is small and safety-critical, it may not be.
8. Delete the extra **Plover route** / **Plover visit order** layers left behind by the failed and successful attempts as you iterate.

#### What you should see

- The error clears and you get the normal `Done — …` status line.
- The route now includes the edge points, hugging the boundary where necessary.

#### How to decide between the three fixes

| Symptom | Best fix |
|---|---|
| Points miss the boundary by centimetres to a couple of metres, all along the field edge | Increase **Boundary buffer:** (this recipe) |
| Points are tens or hundreds of metres out and belong to other fields | Switch **Points outside boundary:** to `Skip points outside the boundary` (recipe 3) |
| Points are thousands of units out, or in a straight offset line | Neither — this is a CRS or data problem. Check the point layer's CRS and the boundary's CRS |
| Only one or two genuinely bad points | Fix the data: move or delete the offending features (they are already selected for you) |

#### Do not over-buffer

A very large buffer makes the failure go away by making the boundary meaningless: exclusion zones shrink by the buffer distance and can vanish entirely, the route is free to leave the field, and points from neighbouring fields start counting as inside. If you find yourself typing a buffer larger than the width of your headland, stop and fix the data instead.

---

### 5.9 Quick reference: which recipe do I need?

| Your situation | Recipe | Key settings |
|---|---|---|
| All points in one field, loop back to the truck | 5.1 | Boundary set, `Fail if any point is outside`, **Return to start (round trip)** ticked |
| Slough or exclusion zone in the field | 5.2 | Hole or fully-enclosed polygon in the boundary layer, small buffer |
| One layer covering the whole farm | 5.3 | Boundary = the one field, `Skip points outside the boundary` |
| Finish somewhere other than the start | 5.4 | **Return to start (round trip)** unticked |
| Only some points today | 5.5 | Select on the map, tick **Use only selected points** |
| Start at a specific gate | 5.6 | **Start at point:** picker |
| No obstacles worth modelling | 5.7 | **Boundary layer:** left empty |
| "…points fall outside the buffered boundary" but they look fine | 5.8 | Raise **Boundary buffer:** just above the largest logged distance |