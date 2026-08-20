## 6. Outputs, Styling and Exporting

This chapter covers everything a Plover run produces: the two output layers, every attribute field on them, the symbology Plover applies automatically, why the layers are temporary, and how to get the route out of QGIS and onto a handheld GPS or phone.

---

### 6.1 What a run produces

A successful run from the Plover dialog adds up to **two new layers** to the current QGIS project:

| Layer name (exactly as it appears in the Layers panel) | Geometry | Created when |
|---|---|---|
| `Plover route` | LineString (one feature) | Always |
| `Plover visit order` | Point (one feature per stop) | Only when **Also create a numbered visit-order layer** is ticked (ticked by default) |

Both layers are created in the **working CRS**, which is:

- the **boundary layer's** CRS when a boundary layer is chosen, or
- the **point layer's** CRS when the **Boundary layer** dropdown is left empty.

If the point layer used a different CRS, Plover reprojected the points into the working CRS before routing, and the outputs use the reprojected coordinates.

Alongside the layers, the dialog fills in two on-screen readouts:

- The **Total distance:** box shows the route length formatted with thousands separators and one decimal, for example `4,182.6 map units`. Before a run it shows the placeholder text `Route length will appear here`.
- The status line under the progress bar reads, for example:
  `Done — 24 stops, 4182.6 units (round trip). Visibility graph: 61 nodes / 812 edges.`
  If points were skipped, a sentence such as ` Skipped 3 point(s) outside the boundary.` is inserted before the visibility-graph counts.

The **Save Route…** button becomes enabled at this moment, and stays enabled until the next run.

> Running the same job through the Processing algorithm `plover:tsproute` produces the **same two attribute schemas**, but as Processing sinks rather than styled scratch layers. See section 6.9 for the differences.


---

### 6.2 The route layer — `Plover route`

One line feature containing the entire tour, stitched from the shortest paths between consecutive stops. Where a boundary was used, the line bends around field corners and exclusion zones; with no boundary, it is straight between stops.

#### 6.2.1 Attribute fields

| Field | Type | Meaning |
|---|---|---|
| `length` | double (real) | Total length of the tour in **map units** of the working CRS. For a round trip this **includes the closing leg** back to the first stop. This is the same number shown in the **Total distance:** box. |
| `stops` | integer | Number of stops in the tour, i.e. the number of points actually routed. Each point is counted **once**; on a round trip the start point is *not* counted a second time at the end. Points skipped by the *Skip points outside the boundary* mode are not counted. |
| `round_trip` | string, width 3 | `yes` when **Return to start (round trip)** was ticked, `no` when it was not. |

#### 6.2.2 Geometry notes

- The layer holds exactly **one** feature. The whole tour is a single LineString.
- For a round trip, the last vertex of the line has the same coordinates as the first vertex — the line visibly closes.
- For a one-way path, the line simply ends at the last stop.
- Vertices are the stops themselves plus any boundary "turn" vertices the route had to bend around. Consecutive duplicate vertices are removed during stitching, so a zero-length hop never leaves a doubled vertex behind.
- "Map units" means the units of the working CRS. With a projected CRS in metres (UTM, most provincial systems), `length` is metres. Plover refuses geographic CRS precisely so this number is meaningful.

#### 6.2.3 Reading the values in PyQGIS

```python
from qgis.core import QgsProject

layer = QgsProject.instance().mapLayersByName("Plover route")[0]
feature = next(layer.getFeatures())
print(feature["length"], feature["stops"], feature["round_trip"])
# e.g. 4182.61... 24 yes
```

---

### 6.3 The visit-order layer — `Plover visit order`

One point feature per stop, placed at the routed location of that stop, in visiting order. This is the layer you print, label, or load onto a device when you want to know *what to visit next*.

#### 6.3.1 Attribute fields

| Field | Type | Meaning |
|---|---|---|
| `visit_order` | integer | Position in the tour, starting at **1**. Stop `1` is always the start point that Plover used. Values run 1 … *n*, where *n* equals the `stops` value on the route layer. |
| `source_fid` | integer | The **feature ID** of the corresponding feature in your original input point layer. Use it to join Plover's ordering back onto your own attributes (sample ID, plot name, notes). |
| `leg_length` | double (real) | Length of the leg **leaving this stop**, measured along the actual routed path in map units — see below. |

#### 6.3.2 What `leg_length` measures, rank by rank

`leg_length` is always the **outgoing** leg: the distance from this stop to the stop you travel to next, following the route as drawn (including any detour around a slough or field corner). It is not a straight-line distance unless the route happens to be straight there.

| `visit_order` value | **Return to start** ticked (round trip) | **Return to start** unticked (one-way) |
|---|---|---|
| `1` … `n-1` | Distance from this stop to the next stop | Distance from this stop to the next stop |
| `n` (the last stop) | Distance of the **closing leg**: from the last stop back to stop `1` | `0.0` — there is no onward leg, so the field is filled with zero |

Consequences worth knowing:

1. **Summing `leg_length` over every feature gives the total route length** — the same value as the route layer's `length` field, to within floating-point rounding. This holds for both round trips and one-way paths (in the one-way case the final `0.0` contributes nothing).
2. A `leg_length` of `0.0` on the last stop is **not an error** — it is the documented one-way behaviour. A `0.0` anywhere else would mean two stops sit at the same coordinates.
3. To find the longest walk between two stops, sort the layer's attribute table by `leg_length` descending. The row's `visit_order` tells you which leg it is (from *v* to *v+1*, or from *n* back to *1*).
4. To label a leg with its length on the map, label the visit-order layer with `leg_length` — the value belongs to the stop the leg *starts* from.

#### 6.3.3 Geometry notes

- Point geometry, single-part, in the working CRS.
- The coordinates are the **routed** coordinates: if your points were reprojected into the boundary's CRS, these are the reprojected positions.
- If an input feature was multi-part, Plover routed its **centroid**, and that centroid is the position stored here.
- Points that were skipped (in *Skip points outside the boundary* mode) do not appear in this layer at all.

[[FIGURE: order-layer-zoom | Close-up of the visit-order layer: orange badges with bold white numbers, and the matching attribute table showing visit_order, source_fid and leg_length.]]

---

### 6.4 Automatic styling

Plover applies symbology to both layers as it creates them, so a finished run is readable on the map without any manual work. Everything described here is applied only by the **dialog** — Processing outputs are unstyled (section 6.9).

#### 6.4.1 Route layer symbology

| Element | Setting |
|---|---|
| Line colour | `#e8590c` (orange) |
| Line width | `0.7` (millimetres, QGIS's default symbol unit) |
| Direction arrows | A marker-line symbol layer added on top of the line |
| Arrow marker | `filled_arrowhead`, colour `#e8590c`, size `3` (millimetres) |
| Arrow placement | Centre of every segment of the line |

The arrows show the direction of travel, so you can tell at a glance whether the tour runs clockwise or counter-clockwise, and where it starts heading after stop 1.

#### 6.4.2 Visit-order layer symbology

**Marker (the badge):**

| Element | Setting |
|---|---|
| Shape | `circle` |
| Fill colour | `#e8590c` (matching the route) |
| Outline colour | `white` |
| Outline width | `0.4` |
| Size | `4` (millimetres) |

**Labels (the number inside the badge):**

| Element | Setting |
|---|---|
| Labelled field | `visit_order` |
| Font | Arial, bold, size 8 |
| Text colour | white |
| Halo (text buffer) | Enabled, size `0.8`, colour `#7a2e06` (dark orange) |
| Placement | Over the point — the number is centred on the marker so it reads as a badge |

#### 6.4.3 These are ordinary QGIS layers

Nothing about the symbology is locked or special. Both outputs are plain QGIS vector layers, so:

- Open **Layer Properties → Symbology** and change colours, sizes or units freely.
- Open **Layer Properties → Labels** to relabel — for example switch the label field from `visit_order` to `leg_length`, or to a field you joined on via `source_fid`.
- Apply a saved `.qml` style, or save Plover's style as a `.qml` for reuse.
- Restyling has no effect whatsoever on the geometry, the attributes or the route itself.

#### 6.4.4 When styling cannot be applied

Symbology is applied on a best-effort basis, because the relevant QGIS APIs differ between QGIS 3 (Qt5) and QGIS 4 (Qt6). If a step fails, the run still succeeds — you get correct data with QGIS's default symbols, and a warning is written to the log panel (**View → Panels → Log Messages**, tab **Plover**):

| Log warning | What it means |
|---|---|
| `Could not apply route symbology on this QGIS version; using defaults.` | The route line is drawn with QGIS's default line style, without direction arrows. |
| `Could not style visit-order markers on this QGIS version.` | The badges are drawn with QGIS's default point marker. |
| `Could not enable visit-order labels on this QGIS version.` | The visit numbers are not shown on the map. The `visit_order` field is still present and correct — you can label the layer manually. |

---

### 6.5 Important: the outputs are temporary scratch layers

Both `Plover route` and `Plover visit order` are created with the QGIS **memory** provider. They exist only in the running QGIS session:

- They are **not** files on disk. There is nothing in a folder to find later.
- Closing QGIS, or removing the layer, destroys them.
- Saving the **project** does not save their contents — a project file only records that the layers existed.

This is easy to miss because on the map they look exactly like any other layer. QGIS itself flags temporary scratch layers with an indicator icon beside the layer name in the Layers panel.

**If you need the result to survive, you must write it to a file.** There are three ways:

1. **Save Route…** in the Plover dialog — the fastest path for the route line, and the only one that handles GPX/KML reprojection for you (section 6.6). Note that it saves the **route layer only**.
2. **QGIS's own export** — right-click the layer in the Layers panel → **Export → Save Features As…**. This works for either layer and is how you export the visit-order layer (section 6.7).
3. **QGIS's "Make Permanent"** — right-click the layer → **Make Permanent**, which writes the scratch layer to a file and re-points the layer at it. This is a QGIS feature, not a Plover one, and is available in current QGIS versions.

A practical habit: run Plover, sanity-check the route on the map, then immediately save both layers into one GeoPackage before doing anything else.

---

### 6.6 Saving the route with **Save Route…**

#### 6.6.1 What this button does and does not do

- It saves the **route layer only** (`Plover route`, the single line feature and its three attributes).
- It does **not** save the visit-order layer. For that, use section 6.7.
- It is disabled until a run has completed successfully.
- If it is somehow triggered with no route available, the status line shows, in red:
  `No route layer to save — generate a route first.`

#### 6.6.2 Step by step

1. Complete a run so the status line reads `Done — …`.
2. Click **Save Route…**.
3. A **Save Route** file dialog opens. It starts in the folder you last saved to (Plover remembers this in the QGIS setting `plover/last_save_dir`) — the first time, it opens in the default location.
4. Choose a format from the file-type dropdown. The five entries are exactly:
   - `GeoPackage (*.gpkg)`
   - `Shapefile (*.shp)`
   - `GeoJSON (*.geojson)`
   - `GPX track (*.gpx)`
   - `KML (*.kml)`
5. Type a file name. **You do not have to type the extension** — if the name does not already end with the extension for the chosen format, Plover appends it.
6. Click **Save**.
7. Answer the GeoPackage prompt if it appears (section 6.6.5).
8. Check the status line: on success it reads `Route saved to <full path>`; on failure it turns red and reads `Save failed: <message from the writer>`.

#### 6.6.3 Format reference

| Filter entry | Extension appended | Writer (OGR driver) | Reprojected by Plover? | Layer name written |
|---|---|---|---|---|
| `GeoPackage (*.gpkg)` | `.gpkg` | `GPKG` | No — keeps the working CRS | `plover_route` (the table name inside the GeoPackage) |
| `Shapefile (*.shp)` | `.shp` | `ESRI Shapefile` | No — keeps the working CRS | `plover_route` |
| `GeoJSON (*.geojson)` | `.geojson` | `GeoJSON` | No — keeps the working CRS | `plover_route` |
| `GPX track (*.gpx)` | `.gpx` | `GPX` | **Yes — to EPSG:4326 (WGS84)** | `plover_route` |
| `KML (*.kml)` | `.kml` | `KML` | **Yes — to EPSG:4326 (WGS84)** | `plover_route` |

All formats are written with the file encoding **UTF-8**.

**Extension inference.** If the chosen filter cannot be matched (some platforms return an empty filter), Plover falls back to reading the extension you typed. If that also fails to match one of the five, nothing is written and the status line shows, in red:

`Unsupported file format — use .gpkg, .shp, .geojson, .gpx or .kml.`

The fix is to type a name ending in one of those five extensions, or to pick a format from the dropdown.

**Note on CRS.** Only GPX and KML are reprojected. GeoPackage, Shapefile and GeoJSON are written without a coordinate transform, so they carry the working CRS. If a downstream system requires latitude/longitude, either export to GPX/KML, or reproject the layer in QGIS first and export that.

**Note on Shapefile.** All three field names (`length`, `stops`, `round_trip`) are ten characters or fewer, so none of them are truncated by the DBF 10-character limit. Remember that a shapefile is a set of sidecar files (`.shp`, `.shx`, `.dbf`, `.prj`, …) — copy them all, or prefer GeoPackage.

#### 6.6.4 GPX specifics

GPX is the format handheld GPS units and phone navigation apps understand. Plover configures the writer as follows:

- **Reprojection to EPSG:4326** is applied automatically, because GPX is a WGS84-only format. You do not need to reproject anything yourself.
- **`FORCE_GPX_TRACK=YES`** (layer creation option) — the route is written as a GPX **track**, not as a GPX *route*. Tracks are the more widely supported of the two and are what most devices draw as a breadcrumb line to follow.
- **`GPX_USE_EXTENSIONS=YES`** (dataset creation option) — the three attribute fields (`length`, `stops`, `round_trip`) are written into GPX `<extensions>` elements. This option is not cosmetic: without it the GPX schema rejects Plover's attribute fields and the write fails outright.

What lands in the file is the **track line only**. GPX waypoints (individual numbered stops) are *not* written by **Save Route…**, because that button only ever saves the route layer. If you want numbered waypoints on the device as well, export the visit-order layer separately (section 6.7) and copy both files across.

#### 6.6.5 GeoPackage: the existing-layer prompt

GeoPackage files hold many layers, so Plover checks before writing.

- **If the target `.gpkg` does not exist**, it is created with a single layer named `plover_route`. No prompt.
- **If the target `.gpkg` exists but contains no readable layer named `plover_route`**, the route is **added as a new layer alongside the existing layers**. The rest of the GeoPackage is left untouched. No prompt.
- **If the target `.gpkg` exists and already contains a valid layer named `plover_route`**, a dialog appears, titled **Layer already exists**, reading:

  ```
  A layer named 'plover_route' already exists in:
  <full path to the file>

  Yes = overwrite it
  No = add a timestamped layer
  Cancel = don't save
  ```

  | Button | Result |
  |---|---|
  | **Yes** | The existing `plover_route` layer is replaced with the new route. Other layers in the GeoPackage are untouched. |
  | **No** | The new route is written to a second layer named `plover_route_YYYYMMDD_HHMMSS` (for example `plover_route_20260820_143015`). The old `plover_route` layer is kept. This is the safe choice when you want to compare runs. |
  | **Cancel** | Nothing is written. The dialog closes and no status message is shown. |

A GeoPackage is the recommended working format: one file, many runs, no sidecar files, no field-name limits.

#### 6.6.6 Messages you may see

| Where | Message | Meaning |
|---|---|---|
| Dialog status line | `Route saved to <path>` | Success. |
| Dialog status line (red) | `Save failed: <message>` | The writer refused. The `<message>` comes from QGIS's vector file writer — common causes are a locked or read-only file, an open GeoPackage held by another program, or a folder you lack permission to write to. |
| Dialog status line (red) | `Unsupported file format — use .gpkg, .shp, .geojson, .gpx or .kml.` | No recognised format or extension. |
| Dialog status line (red) | `No route layer to save — generate a route first.` | No route in memory. |
| Log panel, tab **Plover** | `Route saved to <path> (layer <name>)` | Success, including which layer name was actually used — check here to confirm whether a timestamped name was applied. |
| Log panel, tab **Plover** | `Save failed: <message> (code <n>)` | The full writer error plus its numeric error code. |

---

### 6.7 Exporting the visit-order layer

**Save Route…** does not cover this layer, so use QGIS's own export.

1. In the **Layers** panel, right-click `Plover visit order`.
2. Choose **Export → Save Features As…**.
3. Pick the format:
   - **GeoPackage** — best general choice; you can write it into the *same* `.gpkg` you saved the route to by choosing that file and giving the layer a name such as `plover_visit_order`.
   - **GPX** — for numbered waypoints on a handheld. QGIS writes a point layer to GPX as **waypoints**.
   - **CSV** — for a simple stop list to print or paste into a spreadsheet.
4. **For GPX, set the CRS in the export dialog to `EPSG:4326 - WGS 84`.** QGIS does not do this for you here; Plover's automatic WGS84 reprojection applies only to its own **Save Route…** button.
5. For GPX, be aware that attribute fields which do not correspond to GPX's own waypoint fields may be dropped unless the dataset option `GPX_USE_EXTENSIONS=YES` is set in the export dialog's *Custom Options*. If you only need the numbered positions, the default export is fine.
6. Click **OK**.

If you prefer to script it, the following mirrors the call Plover makes internally, pointed at the visit-order layer:

```python
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsVectorFileWriter,
)

order = QgsProject.instance().mapLayersByName("Plover visit order")[0]

options = QgsVectorFileWriter.SaveVectorOptions()
options.driverName = "GPX"
options.fileEncoding = "UTF-8"
options.datasourceOptions = ["GPX_USE_EXTENSIONS=YES"]
options.ct = QgsCoordinateTransform(
    order.crs(),
    QgsCoordinateReferenceSystem("EPSG:4326"),
    QgsProject.instance(),
)

QgsVectorFileWriter.writeAsVectorFormatV3(
    order,
    r"C:\field\visit_order.gpx",
    QgsProject.instance().transformContext(),
    options,
)
```

---

### 6.8 Getting the route into the field

The usual field kit is **one GPX file for the line to follow, plus one GPX file for the numbered stops**.

#### 6.8.1 Produce the files

1. Run Plover and check the route on the map.
2. Click **Save Route…**, choose `GPX track (*.gpx)`, and save as, for example, `field12_route.gpx`. This is the track your device draws as a line.
3. Right-click `Plover visit order` → **Export → Save Features As…**, choose **GPX**, set the CRS to `EPSG:4326 - WGS 84`, and save as, for example, `field12_stops.gpx`. These are the waypoints your device lists and navigates to one at a time.

Both files are already in WGS84 latitude/longitude, which is what every GPS device and phone app expects.

#### 6.8.2 Handheld GPS (Garmin and similar)

1. Connect the unit by USB and wait for it to appear as a drive.
2. Copy both `.gpx` files into the unit's `Garmin\GPX` folder (folder names vary by manufacturer and model — consult the unit's manual).
3. Eject the unit safely and disconnect.
4. On the unit, the track appears under its track/saved-tracks list and the waypoints under its waypoint list. Select the track to display it, and navigate to waypoint `1` first.

Practical notes:

- Waypoint names on the device come from the exported attributes. If the numbers do not show the way you want, add a text field to the visit-order layer holding the number (or a name built from `visit_order` and your own sample ID) before exporting.
- Some older units cap the number of points in a single track. If the track is rejected, simplify the route geometry in QGIS before exporting, or rely on the waypoints alone.

#### 6.8.3 Phone and tablet apps

Most mobile GIS and outdoor navigation apps (QField, Avenza Maps, Gaia GPS, OsmAnd, Organic Maps, and others) import GPX directly.

1. Transfer both `.gpx` files to the device — email, cloud storage, or a USB cable.
2. Open the file with the app, or use the app's own **Import** function.
3. Display the track for the line to walk or drive, and the waypoints for the ordered stop list.

For QField specifically, the more capable route is to package the whole QGIS project — including the saved (non-temporary) route and visit-order layers — with QFieldSync, rather than importing loose GPX files. That keeps your styling, your attributes, and any joins on `source_fid`.

#### 6.8.4 KML for Google Earth

Save with the `KML (*.kml)` filter and open the file in Google Earth (desktop or mobile). Like GPX, the KML is reprojected to WGS84 automatically. KML is convenient for showing a planned route to someone who does not have QGIS.

---

### 6.9 Outputs from the Processing algorithm

When you run **Processing Toolbox → Plover → Boundary-aware TSP route** (`plover:tsproute`), the outputs carry the **same fields with the same names, types and meanings** as described in sections 6.2 and 6.3, but they are delivered differently.

| Aspect | Dialog | Processing (`plover:tsproute`) |
|---|---|---|
| Route output | Layer named `Plover route`, memory provider | Sink parameter `OUTPUT_ROUTE`, labelled **Route** |
| Visit-order output | Layer named `Plover visit order`, memory provider, controlled by the tick box **Also create a numbered visit-order layer** | Sink parameter `OUTPUT_ORDER`, labelled **Visit order**, optional but created by default |
| Route fields | `length`, `stops`, `round_trip` | Identical |
| Visit-order fields | `visit_order`, `source_fid`, `leg_length` | Identical |
| Automatic symbology | Yes (section 6.4) | **No** — outputs use QGIS's default symbols |
| Persistence | Temporary scratch layers | Whatever you set the sink to: a temporary layer, or a real file path you choose in the algorithm dialog |
| Where the summary appears | Dialog status line | Processing **Log** tab, for example `Route: 24 stops, 4182.61 units (round trip).`, with `, 3 skipped` appended when points were skipped |

Because the sink can be pointed straight at a file, Processing is the tidier option when you want a persistent result without a separate save step, and the only sensible option for batch runs and Model Designer workflows.

```python
import processing

result = processing.run("plover:tsproute", {
    "POINTS": points_layer,
    "BOUNDARY": boundary_layer,   # optional
    "BUFFER": 0.5,
    "START_INDEX": 0,
    "ROUND_TRIP": True,
    "ON_OUTSIDE": 0,              # 0 = fail, 1 = skip
    "OUTPUT_ROUTE": r"C:\field\field12.gpkg",
    "OUTPUT_ORDER": "memory:visit_order",
})
```

If you want Plover's orange-and-arrows look on Processing outputs, save the dialog's styling as a `.qml` once (**Layer Properties → Style → Save Style…**) and load it onto the Processing results afterwards.

---

### 6.10 Quick reference

| Question | Answer |
|---|---|
| What is the route layer called? | `Plover route` |
| What is the numbered layer called? | `Plover visit order` |
| Which field holds the total distance? | `length`, on the route layer, in map units |
| Does `length` include the trip back to the start? | Yes, when `round_trip` is `yes` |
| What does `leg_length` measure? | The leg **leaving** that stop, along the routed path |
| What is `leg_length` on the last stop? | The closing leg back to stop 1 for a round trip; `0.0` for a one-way path |
| How do I link a stop back to my own data? | Join on `source_fid` = the input layer's feature ID |
| Are the outputs saved automatically? | **No.** They are memory (scratch) layers and vanish when QGIS closes |
| Does **Save Route…** save the numbered points too? | No — route line only. Export the visit-order layer separately |
| Which formats are reprojected to WGS84? | GPX and KML only |
| Which layer name goes into the file? | `plover_route`, or `plover_route_YYYYMMDD_HHMMSS` if you chose *add a timestamped layer* |
| Where do I look when something went wrong? | **View → Panels → Log Messages**, tab **Plover** |