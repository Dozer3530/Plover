## 8. Troubleshooting, How It Works, and Limitations

### Part A — Troubleshooting

#### 8.1 First place to look: the Plover log

Plover writes detailed diagnostics to the QGIS message log. The status line in the dialog gives you the short version; the log gives you the specifics — which feature, at which coordinate, how far outside.

Open it with **View ▸ Panels ▸ Log Messages**, then select the **Plover** tab.

Get into the habit of opening this panel *before* a run on unfamiliar data. Most "why did it do that?" questions are answered there.

#### 8.2 Errors that stop a run

These appear in red on the dialog's status line, or as an error in Processing.

##### "Select a point layer."

**Cause.** No point layer is chosen in **Points to visit**.

**Fix.** Choose a point layer. If the dropdown is empty, no point layer is loaded in the project — add one. Note that the boundary layer is *optional*, so this message never refers to the boundary.

##### "The boundary layer uses a geographic CRS (degrees). Distances would be meaningless — reproject to a projected CRS (e.g. UTM) first."

The message says `point layer` instead of `boundary layer` when you are running without a boundary.

**Cause.** The working CRS is geographic — latitude/longitude in degrees, such as EPSG:4326. A degree of longitude is a different ground distance at every latitude, so tour lengths and the buffer distance would be meaningless.

**Fix.** Reproject to a projected CRS that suits your location, then re-run. For most of the Canadian prairies that is a UTM zone (for example EPSG:32612, UTM zone 12N) or a provincial 10TM. Use **Vector ▸ Data Management Tools ▸ Reproject Layer**, or export with **Export ▸ Save Features As…** and set the CRS there.

Note this is checked against the *working* CRS: the boundary layer's CRS when a boundary is supplied, otherwise the point layer's.

##### "The boundary layer contains no usable polygons."

In Processing: `Boundary layer contains no usable polygons.`

**Cause.** Every feature in the boundary layer was rejected — the layer is empty, has no geometries, contains no polygon geometries, or every polygon was invalid and could not be repaired.

**Fix.**

1. Confirm the layer really is a polygon layer with features in it.
2. Check the Plover log for `Skipped an invalid boundary polygon that could not be repaired.`
3. Run **Vector ▸ Geometry Tools ▸ Check Validity**, or **Fix Geometries**, and route against the repaired output.

##### "'Use only selected points' is on, but no points are selected."

**Cause.** The checkbox is ticked but the point layer has no active selection.

**Fix.** Either select features on the map or in the attribute table first, or untick **Use only selected points**.

##### "Need at least two point features to build a route."

In Processing: `Need at least two point features.`

**Cause.** Fewer than two usable points were found. This counts points *after* Plover discards unusable features, so a layer with plenty of rows can still trip it.

**Fix.** Check the log for `Skipping feature <id>:` lines, which give the reason per feature:

| Log message | Meaning |
|---|---|
| `Skipping feature <id>: empty geometry.` | The feature has no geometry at all |
| `Skipping feature <id>: not a point.` | The geometry is not a point geometry |
| `Skipping feature <id>: reprojection failed.` | The point could not be transformed into the working CRS |

If you are using **Use only selected points**, check that at least two points are actually selected.

##### "<n> point(s) fall outside the buffered boundary (now selected on the layer; details in the log). Increase the buffer, switch 'Points outside boundary' to skip, or fix the data."

In Processing the equivalent error names the offending feature ids, up to twelve of them.

**Cause.** You are in **Fail if any point is outside** mode and at least one point lies outside the boundary once the buffer has been applied.

**This is often the most useful error Plover produces** — it is usually telling you something true about your data.

**Fix.** Work out which of these you actually have:

1. **Points genuinely belong to another field.** This is the common case with one project-wide sample layer. Switch **Points outside boundary** to **Skip points outside the boundary**. See chapter 5.
2. **Points sit just barely outside the line.** GPS drift or a boundary digitized slightly tight. Increase **Boundary buffer** until they are inside. The log tells you exactly how far out each one is, so you can pick a sensible value rather than guessing.
3. **Points really are wrong.** Bad coordinates, wrong CRS on import, a typo. Fix the data.

The offending features are **selected on the point layer** automatically (in the dialog, and only when you are not already restricted to a selection), so you can zoom straight to them with **Ctrl+J**. The log lists each one as:

```
Point fid=<id> at (<x>, <y>) is <d> units outside the boundary.
```

##### "Only <n> point(s) fall inside the boundary — need at least two to build a route. Increase the buffer or pick a boundary that contains more points."

**Cause.** You are in skip mode, and after dropping the outside points fewer than two remain.

**Fix.** You have almost certainly selected the wrong boundary feature, or the boundary does not overlap this point set at all. Confirm the two layers overlap on the map. If the points sit just outside, increase the buffer.

##### "<n> point(s) cannot be reached from the start point (point number <list>). They are likely separated by a hole/exclusion zone or a pinched-off part of the boundary. Increase the buffer distance or check the boundary geometry."

**Cause.** The points are inside the boundary, but no legal path exists between them and the start point. The route would have to leave the permitted region to get there.

Note the identifiers here are **point numbers within this run**, counting from 1 — not feature ids.

Typical geometry behind it:

- A slough or exclusion zone spans the field completely, cutting it into two disconnected halves.
- The boundary pinches to a point, or two edges touch, so the passage between two lobes is infinitely narrow.
- The boundary is actually two separate polygons with a gap between them, and points are stranded on the far side.
- A sliver of self-intersection has produced a zero-width neck.

**Fix.**

1. **Increase the buffer.** A pinch that is geometrically zero-width will open up with even a small buffer. This resolves the majority of cases.
2. **Inspect the boundary.** Zoom in on the narrow spot. If the field really is split into two disconnected pieces, the honest answer is that no single continuous route exists — route each piece separately.
3. **Fix the geometry.** Run **Vector ▸ Geometry Tools ▸ Fix Geometries** if the boundary self-intersects.

Plover deliberately reports these points rather than silently drawing a straight line through the obstacle to reach them. A route you cannot drive is worse than an error message.

A related low-level message, `Waypoint graph is disconnected; some points cannot be reached.`, has the same causes and the same fixes.

##### "Start point index must be between 0 and <n>." (Processing only)

**Cause.** `START_INDEX` is outside the valid range. It is a **positional index counting from 0**, not a feature id.

**Fix.** Use a value from `0` to the number of usable points minus one. Remember unusable features are discarded before this check.

##### "Routing failed unexpectedly — see the Plover log panel for the full traceback."

**Cause.** An unhandled error. This is a bug, or data far outside what was anticipated.

**Fix.** Open the Plover log and copy the traceback, then report it at <https://github.com/Dozer3530/Plover/issues> with a description of the data. The traceback is the useful part — please include it.

#### 8.3 Warnings that do not stop a run

These are written to the Plover log. The run continues, but you should know they happened.

| Message | What it means |
|---|---|
| `Reprojecting points from <a> to <b> for routing.` | Your point layer is in a different CRS from the boundary. Normal and harmless. |
| `Repaired an invalid boundary polygon with makeValid().` | A boundary polygon was invalid and was auto-repaired. Worth checking the repair did what you expected. |
| `Skipped an invalid boundary polygon that could not be repaired.` | A polygon was dropped entirely. Investigate. |
| `Treated a fully-enclosed boundary feature as an exclusion zone (hole).` | A polygon fully inside another became a hole. Usually exactly what you wanted for a slough digitized as a separate feature. |
| `Skipping <n> point(s) outside the boundary; routing the <m> inside.` | Skip mode did its job. Confirm the count matches your expectation. |
| `Chosen start point lies outside the boundary and was skipped; starting from the first in-boundary point instead.` | Your nominated start was dropped by skip mode. Pick a start that is inside the field. |
| `Chosen start point is not in the selection; starting from the first selected point instead.` | Your start point is not among the selected features. |
| `Could not apply route symbology on this QGIS version; using defaults.` | Cosmetic only — the route drew with default styling. |
| `Could not style visit-order markers on this QGIS version.` | Cosmetic only. |
| `Could not enable visit-order labels on this QGIS version.` | Cosmetic only — numbers are still in the `visit_order` attribute. |

#### 8.4 Saving and exporting problems

##### "No route layer to save — generate a route first."

**Cause.** **Save Route…** was clicked before a successful run.

**Fix.** Run a route first. The button stays disabled until one succeeds.

##### "Unsupported file format — use .gpkg, .shp, .geojson, .gpx or .kml."

**Cause.** The filename's extension was not recognised and no format was chosen in the file-type dropdown.

**Fix.** Pick a format from the dropdown, or type a filename with one of those five extensions.

##### "Save failed: <message>"

**Cause.** The underlying writer refused. Common reasons: the file is open in another program, the folder is read-only or on a disconnected network drive, or the path is invalid.

**Fix.** Check the full message in the Plover log — it includes the error code. Close the file elsewhere, or save to a local folder such as your Documents directory and copy it afterwards.

#### 8.5 Behaviour that is not a bug

##### The route disappeared when I closed QGIS

The route and visit-order layers are **memory (scratch) layers**. They are not saved anywhere until you export them. Use **Save Route…**, or right-click the layer and choose **Export ▸ Save Features As…**, before closing the project. See chapter 6.

##### Nothing happens when I click Run

Check the status line at the bottom of the dialog. If it reads `Routing <n> points…` the run is in progress — the progress bar advances and **Cancel** is available. Large point counts with complex boundaries take longer.

##### The buffer or "Points outside boundary" controls are greyed out

That is deliberate. Both only apply when a boundary is supplied. Choose a boundary layer and they become active. See chapter 4.

##### The route runs slightly outside the field edge

That is the buffer doing its job. The route is permitted to stray up to the **Boundary buffer** distance outside the strict boundary and that far into exclusion zones. Reduce the buffer if you need it tighter — but note that a buffer of exactly zero is internally widened by a hair, because a route hugging the field edge would otherwise be rejected.

##### The tour is not the shortest possible

Plover is a heuristic solver. See section 8.10.

---

### Part B — How Plover Works

You do not need this section to use Plover. It is here so that whoever maintains the plugin next understands what the numbers mean, and so that anyone can judge how far to trust the output.

#### 8.6 The pipeline

A run proceeds in five stages.

**Stage 1 — Build the permitted region.** The boundary polygon is buffered outward by the **Boundary buffer** distance. Everything afterwards asks one question of this region: *does this straight segment stay inside it?* Because holes are not part of a polygon's interior, obstacle avoidance is a free consequence of the geometry — there is no separate "avoid sloughs" step.

A buffer of exactly zero is widened by a negligible amount, because the geometric containment test excludes the boundary line itself and a route running along the field edge would otherwise be rejected.

With no boundary supplied, this stage is skipped entirely and every segment is permitted.

**Stage 2 — Reduce the boundary to its turn vertices.** A shortest path inside a polygon is taut, like a string pulled tight. A taut string can only bend at a corner that juts *into* the open space — a concave corner of the field outline, or a corner of a hole. It can never bend at a convex field corner or at a vertex in the middle of a straight edge.

Plover therefore keeps only those "reflex" vertices and discards the rest. The saving is large: a rectangular field contributes **no** vertices at all, and a boundary traced from imagery with hundreds of near-collinear vertices typically contributes a handful.

[[FIGURE: visibility-diagram | A taut path bends only at corners that jut into the open space. The straight line from A to B is rejected because it leaves the permitted region; the distance Plover records for that pair is the length of the path around the slough.]]

**Stage 3 — Build the visibility graph.** Plover takes the waypoints plus the surviving boundary vertices and tests every pair: if the straight segment between them stays inside the permitted region, that pair gets an edge whose weight is the straight-line distance.

This is the expensive stage, so the containment test uses a *prepared geometry* — a form the geometry engine optimises once and then reuses for thousands of tests.

With no boundary, no test is needed and every pair is simply connected.

**Stage 4 — Measure true distances between waypoints.** The graph gives distances between *neighbours*, but the solver needs the real travel distance between every pair of waypoints — going around obstacles where necessary. Plover runs Dijkstra's shortest-path algorithm **once per waypoint**, which fills in an entire row of the distance matrix at a time, and caches the actual path taken so it can be redrawn later.

At the end of this stage Plover checks whether any waypoint is unreachable from the start and reports it rather than faking a straight line.

**Stage 5 — Choose the visiting order, then draw it.** With a full distance matrix the problem becomes pure ordering. Plover:

1. builds several starting tours with **nearest-neighbour** construction from different beginnings;
2. improves the best of them with **2-opt**, which repeatedly reverses a section of the tour when doing so shortens it — this is what removes crossings;
3. improves it further with **Or-opt**, which relocates short runs of one to three stops to a better position;
4. alternates the two until neither can find an improvement.

Finally the chosen order is expanded back into a real polyline using the cached shortest paths, so each leg follows the true route around obstacles rather than a straight line.

#### 8.7 What this means in practice

- **Rectangular fields with no sloughs are very fast.** The boundary contributes nothing to the graph, so cost is driven almost entirely by the number of points.
- **Complex boundaries cost more than many points do.** A field traced in fine detail with several sloughs has many turn vertices, and graph construction grows with the square of the node count.
- **Progress is not linear.** The bar moves through graph construction, then the distance matrix, then optimisation. A pause partway through is normal.
- **The run is cancellable** because it happens on a background thread. QGIS stays responsive and you can pan and zoom while it works.

The project README records a benchmark against the older 2.7.0 engine on a synthetic 100-point field with an 80-vertex boundary and two sloughs: wall time fell from 2.9 s to 0.26 s, and tour length from 6749 m to 6405 m.

---

### Part C — Limitations and Good Practice

#### 8.8 It optimises distance, not driving time

Plover minimises geometric distance inside a polygon. It knows nothing about:

- roads, tracks, field approaches or gates
- soil conditions, wet spots or where you would actually get stuck
- speed differences between headland and standing crop
- turning circles, implement width or compaction concerns
- traffic, time windows or crew scheduling

Treat the output as a strong first draft of a visiting order, not as a prescription. The visiting order is usually the valuable part; the exact drawn line is a suggestion.

#### 8.9 It has no concept of a real access route

The line Plover draws is the shortest legal path *within the polygon you gave it*. If you must enter the field by a particular gate, add that gate as a point and set it as the start.

#### 8.10 The solver is heuristic, not exact

Plover uses nearest-neighbour construction improved by 2-opt and Or-opt. These reliably produce good tours — typically within a few percent of optimal — but they do not prove optimality, and re-running will not usually find something better.

For field work this is the right trade: a route two percent longer than perfect, computed in under a second, beats a provably optimal route you cannot compute at all. If you need certainty for a small point set, a dedicated exact TSP solver is the correct tool.

#### 8.11 Without a boundary there is no reachability safety net

In no-boundary mode every point connects to every other in a straight line, so the "cannot be reached" check can never trigger. A stray point hundreds of kilometres away — a mis-keyed coordinate, a point imported in the wrong CRS — will be silently included with a very long leg.

Sanity-check the reported total distance against what you expect. If a quarter-section route comes back as 400 km, you have a rogue point.

#### 8.12 Very large point counts

Cost grows quickly with the number of waypoints, because the graph is built pairwise and one shortest-path search is run per waypoint. A few dozen points is instant. Several hundred with a complex boundary will take noticeably longer.

If a job is too large, consider splitting the work by field or by zone and routing each separately — which is usually what you want operationally anyway.

#### 8.13 CRS caveats

- Always work in a **projected** CRS appropriate to your location. Plover refuses geographic CRS outright.
- Distances are in the **working CRS's map units** — metres for UTM. The `length` and `leg_length` attributes carry no unit, so record which CRS a saved route came from.
- Using a projection badly suited to your latitude introduces distance error. For the Canadian prairies, use the correct UTM zone or a provincial projection.

#### 8.14 A short pre-flight checklist

1. Both layers in the same projected CRS, appropriate to the area.
2. Boundary geometry valid; sloughs digitized as holes or as fully-enclosed polygons.
3. Point layer contains the points you expect, and no strays.
4. Decided: fail or skip for points outside the boundary.
5. Buffer set sensibly for your GPS accuracy — typically a few metres.
6. Start point chosen deliberately, usually the field entrance.
7. Plover log panel open if the data is unfamiliar.
8. **Save the outputs** before closing the project.

#### 8.15 Getting help

- **Plover log** — **View ▸ Panels ▸ Log Messages**, **Plover** tab. Always look here first.
- **Issue tracker** — <https://github.com/Dozer3530/Plover/issues>. Include the QGIS version, the Plover version, the exact message, and the traceback if there was one.
- **Source** — <https://github.com/Dozer3530/Plover>.
