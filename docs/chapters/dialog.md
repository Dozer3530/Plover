## 4. The Plover Dialog: Complete Reference

This chapter documents every control in the Plover dialog: what it is called on screen, what it does, what value it starts at, what its tooltip says, when it is greyed out, and whether Plover remembers it. Use it as a lookup table while you work.

Everything in this chapter is taken from `tsp_route_generator_dialog.py` (the dialog itself), `route_task.py` (the background task), and `tsp_route_generator.py` (the menu wiring). Where a message or label is quoted, it is quoted exactly as the plugin displays it.

---

### 4.1 Opening the dialog

The dialog is reached in either of two ways:

1. **Vector ▸ Plover ▸ Plover — Generate TSP Route**
2. The Plover toolbar button (the plover icon). Hovering it shows the status tip `Boundary-aware TSP route through a point layer`.

Both run the same command. The dialog window is titled:

> **Plover — TSP Route**

Its minimum width is 420 pixels; you can widen or resize it freely.

[[FIGURE: dialog-annotated | The Plover dialog with every control labelled: layer pickers at the top, routing options in the middle, distance / progress / status readout, and the four buttons along the bottom.]]

#### One dialog per QGIS session

The plugin creates the dialog the first time you open it and then keeps that same window object for the rest of the QGIS session. Choosing the menu item again simply shows the existing window, brings it to the front and gives it focus — it does **not** open a second copy and does **not** reset your entries. Closing the dialog and reopening it therefore returns you to exactly the controls you left behind (subject to §4.11 on what is written to disk versus what merely stays in memory).

---

### 4.2 How the dialog behaves while it is open

Two behaviours matter before you touch any individual control.

**The dialog is modeless.** It is shown with a plain `show()`, not as a blocking modal window. QGIS is not locked while it is open: you can pan and zoom the map canvas, switch layers, select features, open the attribute table, and use any other part of QGIS with the Plover window still sitting on screen. This is deliberate — it is how you select the points you want to route, or zoom to a suspect point, without losing your dialog settings.

**The route is computed in a background task.** When you press **Run**, Plover packages the inputs into a `QgsTask` (described as `Plover: computing route`) and hands it to the QGIS task manager. The calculation runs off the user-interface thread, so:

- QGIS stays responsive during long solves — the interface does not freeze.
- The run appears in the QGIS task manager (the progress indicator in the QGIS status bar), in addition to Plover's own progress bar.
- The run can be cancelled at any point (see **Cancel**, §4.7.2).
- Closing the dialog while a run is in progress cancels that run automatically.

While a task is running, the input controls are disabled so the inputs cannot change underneath the calculation. See §4.10 for the full enabled/disabled matrix.

---

### 4.3 Layout at a glance

The dialog is a single column, in this order from top to bottom:

| Row | Control | Type |
|---|---|---|
| 1 | `Points to visit:` | Layer dropdown (point layers) |
| 2 | `Use only selected points` | Tick box |
| 3 | `Boundary layer:` | Layer dropdown (polygon layers, plus an empty entry) |
| 4 | `Start at point:` | Feature picker |
| 5 | `Boundary buffer:` | Number box, suffix ` map units` |
| 6 | `Points outside boundary:` | Dropdown, two choices |
| 7 | `Return to start (round trip)` | Tick box |
| 8 | `Also create a numbered visit-order layer` | Tick box |
| 9 | `Total distance:` | Read-only text box |
| 10 | (progress bar) | Progress bar, 0–100 |
| 11 | (status line) | Wrapping text label, starts at `Ready.` |
| 12 | `Run` / `Cancel` / `Save Route…` / `Close` | Buttons, left to right |

---

### 4.4 Input controls

#### 4.4.1 Points to visit

| | |
|---|---|
| **On-screen label** | `Points to visit:` |
| **Type** | QGIS map-layer dropdown, filtered to **point layers only** |
| **Tooltip** | None |
| **Default** | Not preselected by Plover; QGIS fills the list with the point layers currently in the project. If a point layer is already showing when the dialog opens, the start picker is filled from it immediately. |
| **Remembered?** | No — not written to settings. It keeps its value while the dialog object lives (i.e. for the QGIS session), but a QGIS restart starts fresh. |
| **Disabled when** | A route is running. |

This is the layer whose features become the stops on the route. Only point layers appear in the list; line and polygon layers are filtered out. The list tracks the project, so layers you add or remove while the dialog is open appear and disappear in the dropdown without reopening it.

Changing this dropdown immediately re-points the **Start at point** picker at the newly chosen layer.

**How features are read.** When you press Run, Plover walks the layer's features (or just the selected ones — see §4.4.2) and converts each to a single routing point:

- A single-part point is used as-is.
- A **multi-part** point feature is reduced to its **centroid**.
- A feature with no geometry or an empty geometry is skipped, and logged as `Skipping feature <id>: empty geometry.`
- A feature whose geometry is not a point is skipped, and logged as `Skipping feature <id>: not a point.`
- If the points must be reprojected (see below) and the reprojection of one point fails, that feature is skipped and logged as `Skipping feature <id>: reprojection failed.`

**Coordinate reference system.** Routing happens in a single *working CRS*:

- If a boundary layer is chosen, the working CRS is the **boundary layer's** CRS.
- If no boundary layer is chosen, the working CRS is the **point layer's** CRS.

If the point layer's CRS differs from the working CRS, Plover reprojects the points automatically and logs `Reprojecting points from <authid> to <authid> for routing.` If the working CRS is geographic (degrees), Plover refuses to run — see the error table in §4.8.

**Minimum count.** At least two usable point features are required. Fewer gives `Need at least two point features to build a route.`

---

#### 4.4.2 Use only selected points

| | |
|---|---|
| **On-screen label** | `Use only selected points` (tick box; the label column beside it is blank) |
| **Tooltip** | None |
| **Default** | **Unticked** |
| **Remembered?** | No — not written to settings, and not restored on start-up. It keeps its state while the dialog object lives. |
| **Disabled when** | A route is running. |

When ticked, Plover routes **only the features currently selected on the layer chosen in Points to visit**, ignoring everything else in the layer. When unticked, every feature in the layer is considered.

Because the dialog is modeless, the normal working pattern is: leave the dialog open, select the points you want on the map or in the attribute table, then tick this box and press **Run**.

Two behaviours depend on this tick box:

1. **If it is ticked and nothing is selected**, the run stops immediately with:
   `'Use only selected points' is on, but no points are selected.`
2. **In `Fail if any point is outside` mode** (§4.4.6), Plover normally *selects* the offending points on the layer so you can find them. It deliberately does **not** do this when *Use only selected points* is ticked — overwriting your selection would destroy the very input you asked it to route.

If the feature chosen in **Start at point** is not part of the selection, Plover falls back to the first selected point and logs `Chosen start point is not in the selection; starting from the first selected point instead.`

---

#### 4.4.3 Boundary layer

| | |
|---|---|
| **On-screen label** | `Boundary layer:` |
| **Type** | QGIS map-layer dropdown, filtered to **polygon layers**, with an additional **empty entry** |
| **Tooltip** | see below |
| **Default** | Not preselected by Plover. Always check what it shows before running. |
| **Remembered?** | No — not written to settings. |
| **Disabled when** | A route is running. |

Tooltip, exactly as displayed:

> Optional. With a boundary, the route stays inside it and routes
> around holes (sloughs / exclusion zones). Leave empty for a plain
> straight-line route through the points (ordinary Euclidean TSP).

**The empty entry.** This dropdown allows an empty selection — that is the "no boundary" option. It is not a mistake or a placeholder; choosing it is a supported mode of operation.

**With a boundary chosen:**

- The route is kept inside the boundary and routed around its holes.
- All polygon features in the layer are merged into a single routing region. A feature that lies wholly inside another feature is subtracted as an exclusion zone, and this is logged as `Treated a fully-enclosed boundary feature as an exclusion zone (hole).` Invalid polygons are repaired where possible (`Repaired an invalid boundary polygon with makeValid().`) or dropped (`Skipped an invalid boundary polygon that could not be repaired.`).
- If nothing usable survives, the run stops with `The boundary layer contains no usable polygons.`
- The working CRS is the boundary layer's CRS, and distances are reported in that CRS's units.

**With the empty entry (no boundary):**

- Plover solves an ordinary straight-line (Euclidean) travelling-salesperson problem: every point can see every other point, and the route runs in straight lines between stops with no obstacle avoidance whatsoever.
- The working CRS is the point layer's CRS.

**What greys out when the boundary is empty.** Two controls only have meaning when there is a boundary to respect, and Plover disables them the moment the boundary dropdown is set to the empty entry:

- `Boundary buffer:`
- `Points outside boundary:`

They re-enable as soon as you pick a polygon layer. Their values are preserved while greyed out — nothing is reset — and the greyed-out buffer value is still what gets written to settings when you press Run.

---

#### 4.4.4 Start at point

| | |
|---|---|
| **On-screen label** | `Start at point:` |
| **Type** | QGIS feature picker, with the browse (previous/next) buttons switched on |
| **Tooltip** | None |
| **Default** | Whatever the picker shows for the current layer; no specific feature is forced by Plover. |
| **Remembered?** | No — not written to settings. |
| **Disabled when** | A route is running. |

The picker lists the features of the layer chosen in **Points to visit** and follows that dropdown: change the point layer and the picker repopulates. The browse buttons let you step through features one at a time.

**How the start is resolved at run time.** Plover resolves the start *after* it has built the final list of points to route (that is, after any selection filter and after any outside-boundary points have been skipped):

- If the picked feature is valid **and** its feature ID is in the final routed set, that point is the start.
- Otherwise the start falls back to the **first point in the final set** — the first feature in the order the layer supplied them (or the first selected feature when *Use only selected points* is on). Two cases are logged:
  - `Chosen start point lies outside the boundary and was skipped; starting from the first in-boundary point instead.`
  - `Chosen start point is not in the selection; starting from the first selected point instead.`

Note that the fallback is silent on screen — the run proceeds normally, and only the log records that your chosen start was not used. If the start matters to you, check the Plover log tab after the run.

**Round trips versus one-way paths.** For a **one-way path** (`Return to start` unticked) the start point genuinely fixes where the route begins. For a **round trip**, the route is a closed loop; the loop is rotated so that it is *reported* beginning at your chosen point, but the loop itself — and therefore its length — is the same whichever stop you nominate.

---

#### 4.4.5 Boundary buffer

| | |
|---|---|
| **On-screen label** | `Boundary buffer:` |
| **Type** | Number box with two decimal places, range `0.00` to `1000000.00`, suffix ` map units` |
| **Tooltip** | see below |
| **Default** | `0.50` |
| **Remembered?** | **Yes** — `plover/buffer` |
| **Disabled when** | The boundary dropdown is on the empty entry, or a route is running. |

Tooltip, exactly as displayed:

> Tolerance around the boundary: the route may pass this far
> outside the field edge and this far into exclusion zones.

The buffer is a tolerance, not a setback. It **enlarges** the legal routing region: the route may run up to this distance outside the outer field edge, and up to this distance into a slough or other exclusion zone. It is expressed in the working CRS's map units — normally metres — which is why the box carries the ` map units` suffix rather than naming a unit.

The buffer is used in two places:

1. **The containment test.** Points are checked against the *buffered* boundary, so a point sitting a few centimetres outside a digitized field edge counts as inside.
2. **The routing region.** The visibility graph is built inside the *buffered* boundary, so a route may legitimately hug or slightly cross the field edge.

**Why a buffer of zero is not really zero.** Plover always applies a minimum sliver of tolerance (0.000001 map units) even when the box reads `0.00`. Without it, GEOS treats a line running exactly along the boundary as *not* contained by the boundary, and points digitized precisely on the field edge become unroutable. You can therefore set `0.00` safely; you simply do not get an exact-zero tolerance.

**Practical guidance.** If a run fails because points are outside the boundary, or because points cannot be reached, raising the buffer is usually the first thing to try. Raising it too far lets the route cut corners across sloughs, because the exclusion zones shrink by the same amount.

---

#### 4.4.6 Points outside boundary

| | |
|---|---|
| **On-screen label** | `Points outside boundary:` |
| **Type** | Dropdown with exactly two entries |
| **Entries** | `Fail if any point is outside` (stored value `fail`) · `Skip points outside the boundary` (stored value `skip`) |
| **Tooltip** | see below |
| **Default** | `Fail if any point is outside` |
| **Remembered?** | **Yes** — `plover/outside_mode` (stores `fail` or `skip`) |
| **Disabled when** | The boundary dropdown is on the empty entry, or a route is running. |

Tooltip, exactly as displayed:

> What to do with points that fall outside the buffered boundary.
> Fail: stop and report them (good when every point should be in-field).
> Skip: drop them and route only the points inside (good for one big
> point layer spanning many fields — route just this field's points).

This setting only comes into play if at least one point falls outside the **buffered** boundary. If every point is inside, the two modes behave identically.

Regardless of mode, every offending point is written to the log first, one line each:

```
Point fid=1234 at (512340.55, 5766120.10) is 3.87 units outside the boundary.
```

The distance quoted is measured to the **unbuffered** boundary, so it tells you how much buffer would be needed to bring that point inside.

##### Mode 1 — `Fail if any point is outside` (default)

The run **stops**. Nothing is computed and no layers are created. Plover does three things:

1. Logs each offending point as shown above.
2. **Selects the offending features on the point layer**, so you can immediately zoom to them and inspect them — *unless* `Use only selected points` is ticked, in which case the selection is left untouched.
3. Shows this in red on the status line:

   `<n> point(s) fall outside the buffered boundary (now selected on the layer; details in the log). Increase the buffer, switch 'Points outside boundary' to skip, or fix the data.`

Note that step 2 **replaces** whatever was selected on that layer before.

Use this mode when every point in the layer is supposed to be inside the field. It turns a data problem into a visible, fixable list rather than a quietly wrong route.

##### Mode 2 — `Skip points outside the boundary`

The offending points are **dropped** and the route is built from the points that remain inside. Specifically:

1. The outside points are removed from the routing set, and their feature IDs are remembered as "skipped".
2. If fewer than two points remain, the run stops with:
   `Only <n> point(s) fall inside the boundary — need at least two to build a route. Increase the buffer or pick a boundary that contains more points.`
3. Otherwise the log records `Skipping <n> point(s) outside the boundary; routing the <m> inside.`
4. The route is computed over the remaining points, and the success status line adds a sentence: ` Skipped <n> point(s) outside the boundary.`
5. If the point you chose in **Start at point** was one of the skipped ones, the start falls back to the first in-boundary point (logged, see §4.4.4).

Use this mode when a single point layer covers many fields and you want to route only the points that fall inside the boundary you have chosen. Change the boundary layer, run again, and you get that field's route from the same point layer.

Because skipped points never enter the calculation, they also never appear in the numbered visit-order layer.

---

#### 4.4.7 Return to start (round trip)

| | |
|---|---|
| **On-screen label** | `Return to start (round trip)` (tick box; the label column beside it is blank) |
| **Tooltip** | None |
| **Default** | **Ticked** |
| **Remembered?** | **Yes** — `plover/round_trip` |
| **Disabled when** | A route is running. |

- **Ticked** — the route is a closed loop: it visits every point and returns to the starting point. The closing leg is part of the route geometry and is included in the reported total distance.
- **Unticked** — the route is a one-way path: it starts at the chosen start point, visits every other point, and stops at the last one. No return leg is drawn or counted.

This choice feeds through to three visible places:

| Where | Round trip ticked | Round trip unticked |
|---|---|---|
| Status line trip type | `round trip` | `one-way path` |
| `round_trip` field on the route layer | `yes` | `no` |
| Route geometry | closes back on the start | ends at the final stop |

---

#### 4.4.8 Also create a numbered visit-order layer

| | |
|---|---|
| **On-screen label** | `Also create a numbered visit-order layer` (tick box; the label column beside it is blank) |
| **Tooltip** | None |
| **Default** | **Ticked** |
| **Remembered?** | **Yes** — `plover/order_layer` |
| **Disabled when** | A route is running. |

When ticked, a successful run adds a **second** layer to the project, named `Plover visit order`, alongside the `Plover route` line layer. It contains one point per stop, in the working CRS, with three fields:

| Field | Type | Meaning |
|---|---|---|
| `visit_order` | integer | 1, 2, 3 … the position of this stop in the tour |
| `source_fid` | integer | the feature ID of the original point in your input layer |
| `leg_length` | double | length of the leg **leaving** this stop, in map units |

Plover also styles it: orange circular markers matching the route colour, with a white outline, and the `visit_order` number drawn in bold white over each marker with a dark halo — so it reads as a numbered badge at map scale. If your QGIS build rejects any part of the styling it is logged (`Could not style visit-order markers on this QGIS version.` / `Could not enable visit-order labels on this QGIS version.`) and the layer is still created with default symbology. Styling is never fatal.


This layer is a **memory (scratch) layer**, like the route layer. It exists only in the current QGIS project until you save it somewhere. Note that the **Save Route…** button saves the *route line* only — it does not export the visit-order layer.

---

### 4.5 Total distance

| | |
|---|---|
| **On-screen label** | `Total distance:` (a caption to the left of the box) |
| **Type** | Read-only text box. You cannot type into it. |
| **Placeholder text** | `Route length will appear here` |
| **Remembered?** | No |

After a successful run it shows the total route length formatted with a thousands separator and one decimal place, followed by the unit wording — for example:

```
6,405.2 map units
```

"Map units" means the units of the working CRS (§4.4.1) — metres for a UTM or other metric projected CRS. Plover does not convert to kilometres, miles or acres.

The box is **cleared at the start of every run**, so a stale figure never sits next to a fresh failure. If a run fails or is cancelled, it stays empty.

For a round trip the figure includes the closing leg back to the start. With a boundary, it is the true obstacle-aware path length, not the straight-line distance between stops.

---

### 4.6 Progress bar and status line

#### 4.6.1 The progress bar

An ordinary 0–100 progress bar sits below the distance box. It is driven by the background task, and it is reset to 0 at the start of every run and when a run is cancelled.

The percentage maps onto the pipeline stages as follows, which is useful for diagnosing where a slow run is spending its time:

| Progress range | Stage |
|---|---|
| 0 – 45 % | Building the visibility graph (testing which node pairs can see each other) |
| 45 – 70 % | Shortest paths between every pair of waypoints (one Dijkstra run per waypoint) |
| 70 – 95 % | Optimizing the visiting order (multi-start nearest-neighbour, 2-opt, Or-opt) |
| 100 % | Route stitched and complete |

Because the work runs as a QGIS task, the same run also shows in the QGIS task manager in the main-window status bar, described as `Plover: computing route`.

#### 4.6.2 The status line

Below the progress bar is a wrapping text label. It starts at:

> `Ready.`

It reports every stage of every run. Error messages are shown in **red** (`#c0392b`); informational messages are shown in the normal text colour. The message list is in §4.8.

---

### 4.7 The buttons

The four buttons run left to right along the bottom of the dialog.

#### 4.7.1 Run

| | |
|---|---|
| **Label** | `Run` |
| **Enabled** | Always, except while a route is running |

Validates the inputs, saves the remembered settings (§4.11), and launches the background task. If validation fails, the reason appears in red on the status line and nothing is launched. The full validation sequence is in §4.8.

On launch, the status line reads `Routing <n> points…`, where `<n>` is the number of points actually being routed — after the selection filter and after any skipped outside-boundary points.

Each successful run **adds new layers to the project**; it does not overwrite the layers from the previous run. Run three times and you will have three `Plover route` layers. Remove the ones you do not want.

#### 4.7.2 Cancel

| | |
|---|---|
| **Label** | `Cancel` |
| **Enabled** | Only while a route is running. Disabled at all other times, including when the dialog first opens. |

Requests cancellation of the running task. The status line changes to `Cancelling…` immediately; the task stops at its next cancellation checkpoint (checkpoints exist inside every stage of the pipeline, so cancellation is normally near-instant). When the task actually stops, the status line reads `Cancelled.` and the progress bar returns to 0.

No layers are created by a cancelled run and the distance box stays empty.

`Cancel` does **not** close the dialog — that is `Close`.

#### 4.7.3 Save Route…

| | |
|---|---|
| **Label** | `Save Route…` |
| **Enabled** | Disabled until a route has been computed successfully; enabled from then on |

Opens a standard save-file dialog titled `Save Route`, offering these formats:

| Filter shown | Driver used | Extension |
|---|---|---|
| `GeoPackage (*.gpkg)` | GPKG | `.gpkg` |
| `Shapefile (*.shp)` | ESRI Shapefile | `.shp` |
| `GeoJSON (*.geojson)` | GeoJSON | `.geojson` |
| `GPX track (*.gpx)` | GPX | `.gpx` |
| `KML (*.kml)` | KML | `.kml` |

Points to note at reference level (the export chapter covers the workflow in full):

- The extension is appended automatically if you do not type it. If the chosen filter cannot be matched, Plover infers the driver from the extension you typed; if that also fails, it reports `Unsupported file format — use .gpkg, .shp, .geojson, .gpx or .kml.`
- The written layer is named `plover_route`.
- **GPX and KML are reprojected to WGS84 (EPSG:4326)** on the way out, because those formats are defined in geographic coordinates.
- If you save to an existing GeoPackage that already contains a `plover_route` layer, a question box titled `Layer already exists` appears, offering `Yes = overwrite it`, `No = add a timestamped layer`, `Cancel = don't save`. The timestamped name is `plover_route_YYYYMMDD_HHMMSS`.
- The folder you last saved into is remembered (`plover/last_save_dir`) and offered again next time.
- Only the **route line layer** is written. The numbered visit-order layer is not part of this export.

#### 4.7.4 Close

| | |
|---|---|
| **Label** | `Close` |
| **Enabled** | Always, including while a route is running |

Hides the dialog. If a route is still running, closing the dialog **cancels** it.

Closing does not discard your entries: the same dialog window is reused next time you open Plover, so every control comes back as you left it for the remainder of the QGIS session. Layers already added to the project are unaffected.

---

### 4.8 What happens when you press Run

Plover checks the inputs in a fixed order and stops at the first problem. Knowing the order makes messages easier to interpret — a later check never runs if an earlier one failed.

1. Progress bar reset to 0; distance box cleared; settings saved.
2. A point layer must be chosen.
3. The working CRS (boundary CRS if a boundary is chosen, otherwise point-layer CRS) must not be geographic.
4. If a boundary is chosen, its polygons are merged into a usable region.
5. The point features are gathered — all of them, or only the selection.
6. Points are reprojected to the working CRS if needed; unusable features are skipped and logged.
7. At least two points must remain.
8. If a boundary is chosen, points are tested against the **buffered** boundary and the `Points outside boundary` mode is applied.
9. The start point is resolved against the final point set.
10. The background task is launched.

#### 4.8.1 Status-line messages, in full

Messages shown in red are failures; the run stops and no layers are created.

| Message (exactly as shown) | Colour | Meaning / what to do |
|---|---|---|
| `Ready.` | normal | Dialog just opened; nothing has run yet. |
| `Select a point layer.` | red | `Points to visit:` has no layer. Add or choose a point layer. |
| `The boundary layer uses a geographic CRS (degrees). Distances would be meaningless — reproject to a projected CRS (e.g. UTM) first.` | red | The chosen boundary layer is in degrees. Reproject it. |
| `The point layer uses a geographic CRS (degrees). Distances would be meaningless — reproject to a projected CRS (e.g. UTM) first.` | red | No boundary chosen, and the point layer is in degrees. Reproject it. |
| `The boundary layer contains no usable polygons.` | red | Every polygon was empty, non-polygon or unrepairable. Check the log for the repair notes. |
| `'Use only selected points' is on, but no points are selected.` | red | Select some features, or untick the box. |
| `Need at least two point features to build a route.` | red | Fewer than two usable points survived reading (empty/non-point/failed reprojection features are skipped — see the log). |
| `<n> point(s) fall outside the buffered boundary (now selected on the layer; details in the log). Increase the buffer, switch 'Points outside boundary' to skip, or fix the data.` | red | Fail mode found outside points; they are now selected on the layer for you. |
| `Only <n> point(s) fall inside the boundary — need at least two to build a route. Increase the buffer or pick a boundary that contains more points.` | red | Skip mode dropped too many points. |
| `Routing <n> points…` | normal | The background task has started. |
| `Cancelling…` | normal | Cancel was pressed; waiting for the task to stop. |
| `Cancelled.` | normal | The run stopped at your request. Progress bar back to 0. |
| `<n> point(s) cannot be reached from the start point (point number <list>). They are likely separated by a hole/exclusion zone or a pinched-off part of the boundary. Increase the buffer distance or check the boundary geometry.` | red | The boundary cuts the field into disconnected pieces. The numbers are **positions in the routed point list** (1-based), not feature IDs; at most 12 are listed, followed by `…`. |
| `Waypoint graph is disconnected; some points cannot be reached.` | red | Same class of problem, raised deeper in the solver. Rarely seen — the message above normally catches it first. |
| `Routing failed unexpectedly — see the Plover log panel for the full traceback.` | red | An unhandled error. The full traceback is in the Plover log tab; send it with a bug report. |
| `Route computed but creating layers failed: <detail>` | red | The route solved, but building the output layers failed. |
| `Done — <stops> stops, <length> units (<trip>).<skipped note> Visibility graph: <nodes> nodes / <edges> edges.` | normal | Success. Decoded in §4.9. |
| `No route layer to save — generate a route first.` | red | `Save Route…` pressed with no route in hand. |
| `Unsupported file format — use .gpkg, .shp, .geojson, .gpx or .kml.` | red | The save filename had no recognised extension. |
| `Save failed: <detail>` | red | The writer refused. The detail and an error code go to the log. |
| `Route saved to <path>` | normal | Export succeeded. |

#### 4.8.2 Where the detail goes

Warnings and diagnostics that are too long for the status line go to the QGIS message log, under the tab named **Plover** (**View ▸ Panels ▸ Log Messages**). Messages you will see there include:

| Log message | Raised when |
|---|---|
| `Repaired an invalid boundary polygon with makeValid().` | A boundary polygon was invalid but repairable. |
| `Skipped an invalid boundary polygon that could not be repaired.` | A boundary polygon was invalid beyond repair. |
| `Treated a fully-enclosed boundary feature as an exclusion zone (hole).` | A boundary feature sits entirely inside another and was subtracted. |
| `Reprojecting points from <authid> to <authid> for routing.` | The point layer's CRS differs from the working CRS. |
| `Skipping feature <id>: empty geometry.` / `: not a point.` / `: reprojection failed.` | An individual feature could not be used. |
| `Point fid=<id> at (<x>, <y>) is <d> units outside the boundary.` | Per-point detail behind an outside-boundary failure or skip. |
| `Skipping <n> point(s) outside the boundary; routing the <m> inside.` | Skip mode dropped points. |
| `Chosen start point lies outside the boundary and was skipped; starting from the first in-boundary point instead.` | Your start point was skipped. |
| `Chosen start point is not in the selection; starting from the first selected point instead.` | Your start point is outside the current selection. |
| `Route created: <stops> stops, <length> units, <trip>.` | Success. |
| `Could not apply route symbology on this QGIS version; using defaults.` | Route styling was rejected; the layer is still created. |
| `Route saved to <path> (layer <name>)` | Successful export, including the layer name actually written. |

---

### 4.9 Reading the success status line

A successful run produces one dense line. Here is a worked example:

```
Done — 42 stops, 6,405.2 units (round trip). Skipped 3 point(s) outside the boundary. Visibility graph: 118 nodes / 2 431 edges.
```

| Part | What it means |
|---|---|
| `42 stops` | How many points are in the tour. This is the number of points actually routed — after the selection filter and after skipping — so if it is lower than you expected, check the selection and the skip count. |
| `6,405.2 units` | Total route length in working-CRS map units, same figure as the **Total distance** box. Includes the closing leg on a round trip. |
| `(round trip)` | The trip type: `round trip` when **Return to start** is ticked, `one-way path` when it is not. |
| `Skipped 3 point(s) outside the boundary.` | Appears **only** when skip mode actually dropped points. Absent when nothing was skipped. |
| `118 nodes / 2 431 edges` | Size of the visibility graph — a diagnostic, not a quality measure. |

**About nodes and edges.** *Nodes* are the routed points plus the boundary's "turn vertices" — the only corners a shortest path can ever bend around (concave corners of the outer boundary and corners of holes poking into the field). A convex, hole-free field contributes **zero** extra nodes, so `nodes` equals the number of stops. *Edges* count the node pairs that can see each other in a straight line inside the buffered boundary.

Practical readings:

- Node count much larger than the stop count → a complicated boundary (many concave corners, several sloughs). Expect longer run times.
- Edge count near the maximum for the node count → few obstructions between points.
- A low edge count relative to nodes → the boundary is chopping up visibility, which is also the situation that produces "cannot be reached from the start point" failures.

With **no boundary**, `nodes` always equals the number of stops and `edges` is the complete-graph count, because every point can see every other point.

---

### 4.10 Enabled and disabled: the full picture

Two independent things grey controls out: the boundary being empty, and a run being in progress.

| Control | Greyed out when boundary is empty | Greyed out while a run is in progress |
|---|---|---|
| `Points to visit:` | No | **Yes** |
| `Use only selected points` | No | **Yes** |
| `Boundary layer:` | No | **Yes** |
| `Start at point:` | No | **Yes** |
| `Boundary buffer:` | **Yes** | **Yes** |
| `Points outside boundary:` | **Yes** | **Yes** |
| `Return to start (round trip)` | No | **Yes** |
| `Also create a numbered visit-order layer` | No | **Yes** |
| `Total distance:` | n/a (always read-only) | n/a |
| `Run` | No | **Yes** |
| `Cancel` | No | No — this is the only time it is *enabled* |
| `Save Route…` | No | No (but disabled until the first successful run) |
| `Close` | No | No — always available |

When a run finishes, fails or is cancelled, everything is re-enabled and the boundary-dependent rule is re-applied, so `Boundary buffer:` and `Points outside boundary:` come back greyed out if the boundary dropdown is still empty.

---

### 4.11 What Plover remembers

Plover stores a small number of preferences in QGIS's own settings store (`QgsSettings`), under the `plover/` prefix. They survive closing QGIS and apply across all projects and all user profiles that share the same QGIS profile.

**When they are saved.** The four routing settings are written **when you press Run** — not when you change a control and not when you close the dialog. Changing a setting and closing without running therefore leaves the stored value untouched. The save directory is written when you complete a save.

**When they are restored.** The four routing settings are read once, when the dialog object is created — that is, the first time you open Plover in a QGIS session.

| Setting key | Control | Default | Stored value |
|---|---|---|---|
| `plover/buffer` | `Boundary buffer:` | `0.5` | number |
| `plover/round_trip` | `Return to start (round trip)` | `True` (ticked) | true / false |
| `plover/order_layer` | `Also create a numbered visit-order layer` | `True` (ticked) | true / false |
| `plover/outside_mode` | `Points outside boundary:` | `fail` | `fail` or `skip` |
| `plover/last_save_dir` | Folder offered by `Save Route…` | empty | folder path |

Everything else — the point layer, the boundary layer, the start point, and the `Use only selected points` tick — is **not** written to settings. It persists only for as long as the dialog object lives, which in practice means until QGIS is closed.

---

### 4.12 Summary: every control at a glance

| Control (exact label) | Type | Default | Remembered | Greyed out when |
|---|---|---|---|---|
| `Points to visit:` | Point-layer dropdown | none forced | No (session only) | Run in progress |
| `Use only selected points` | Tick box | Unticked | No (session only) | Run in progress |
| `Boundary layer:` | Polygon-layer dropdown, empty entry allowed | none forced | No (session only) | Run in progress |
| `Start at point:` | Feature picker with browse buttons | none forced | No (session only) | Run in progress |
| `Boundary buffer:` | Number, 2 dp, 0.00–1000000.00, suffix ` map units` | `0.50` | Yes — `plover/buffer` | Boundary empty; run in progress |
| `Points outside boundary:` | Dropdown: `Fail if any point is outside` / `Skip points outside the boundary` | Fail | Yes — `plover/outside_mode` | Boundary empty; run in progress |
| `Return to start (round trip)` | Tick box | Ticked | Yes — `plover/round_trip` | Run in progress |
| `Also create a numbered visit-order layer` | Tick box | Ticked | Yes — `plover/order_layer` | Run in progress |
| `Total distance:` | Read-only text, placeholder `Route length will appear here` | empty | No | Always read-only |
| Progress bar | 0–100 | 0 | No | — |
| Status line | Wrapping label | `Ready.` | No | — |
| `Run` | Button | Enabled | — | Run in progress |
| `Cancel` | Button | Disabled | — | Enabled only during a run |
| `Save Route…` | Button | Disabled | Last folder — `plover/last_save_dir` | Enabled after the first successful run |
| `Close` | Button | Enabled | — | Never |