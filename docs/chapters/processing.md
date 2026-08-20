## 7. Automation: Processing Algorithm, Models and Scripting

Everything the Plover dialog does can also be done from the QGIS **Processing** framework. This matters when you have more than one field to route, when routing needs to be one step inside a larger workflow, or when you want the job to run unattended.

The Processing version uses the same engine as the dialog — both call an identical routing pipeline — so anything you can produce in the dialog you can reproduce exactly in Processing.

### 7.1 Where to find it

Plover registers a Processing **provider**:

| Item | Value |
|---|---|
| Provider name | **Plover** |
| Provider id | `plover` |
| Algorithm display name | **Boundary-aware TSP route** |
| Algorithm name | `tsproute` |
| Full algorithm id | **`plover:tsproute`** |

Open **Processing ▸ Toolbox** (or press `Ctrl+Alt+T`), then expand the **Plover** group. Double-click **Boundary-aware TSP route** to open the algorithm dialog.

If the **Plover** group is not in the Toolbox, see section 7.9.

[[FIGURE: processing-dialog | The Boundary-aware TSP route algorithm in the Processing Toolbox. The boundary is optional and may be left blank.]]

### 7.2 Parameter reference

These are the parameters exactly as the algorithm defines them. The **Key** column is the string used when scripting; the **Label** column is what appears in the dialog.

| Key | Label | Type | Optional | Default |
|---|---|---|---|---|
| `POINTS` | Points to visit | Point feature source | No | — |
| `BOUNDARY` | Boundary polygon(s) | Polygon feature source | **Yes** | *(unset)* |
| `BUFFER` | Boundary buffer | Distance (minimum `0.0`) | No | `0.5` |
| `START_INDEX` | Start point index (order of the input layer) | Integer (minimum `0`) | No | `0` |
| `ROUND_TRIP` | Return to start (round trip) | Boolean | No | `True` |
| `ON_OUTSIDE` | Points outside the boundary | Enum | No | `0` |
| `OUTPUT_ROUTE` | Route | Line feature sink | No | — |
| `OUTPUT_ORDER` | Visit order | Point feature sink | Yes (created by default) | — |

#### The ON_OUTSIDE enum

Enum parameters are passed as **integers** when scripting. The index order is part of the algorithm's public interface and will not change:

| Index | Option string | Behaviour |
|---|---|---|
| `0` | `Fail if any point is outside` | Any point outside the buffered boundary aborts the run with an error listing the offending feature ids. |
| `1` | `Skip points outside the boundary` | Points outside the buffered boundary are dropped; only the points inside are routed. |

Index `0` is the default. See section 7.6 for what skip mode does to the start point.

> **The buffer is tied to the boundary.** `BUFFER` is declared as a distance parameter whose parent is `BOUNDARY`, so the Processing dialog shows it in the boundary layer's map units. With no boundary supplied, the buffer has no effect.

#### START_INDEX is positional, not a feature id

`START_INDEX` is an index into the points **in the order the algorithm reads them from the input layer**, starting at `0`. It is *not* a feature id. The valid range is `0` to the number of usable points minus one; anything outside that range raises:

```
Start point index must be between 0 and <n>.
```

The count is of *usable* points — features with empty or non-point geometries are skipped before the index is checked.

### 7.3 Outputs

Two sinks are produced. Field names and types are exactly as follows.

**`OUTPUT_ROUTE` — "Route"** (LineString, one feature):

| Field | Type | Meaning |
|---|---|---|
| `length` | double | Total route length in the working CRS's map units |
| `stops` | integer | Number of stops visited |
| `round_trip` | string(3) | `yes` for a round trip, `no` for a one-way path |

**`OUTPUT_ORDER` — "Visit order"** (Point, one feature per stop):

| Field | Type | Meaning |
|---|---|---|
| `visit_order` | integer | Rank in the tour, starting at `1` |
| `source_fid` | integer | Feature id of the originating point in the input layer |
| `leg_length` | double | Length of the leg *leaving* this stop |

`OUTPUT_ORDER` is optional but is created by default. To suppress it, pass `None` for that parameter.

> **The output CRS depends on the boundary.** If a boundary is supplied, both outputs use the **boundary layer's** CRS and the points are reprojected into it. With no boundary, both outputs use the **point layer's** CRS. Plan for this when chaining outputs into other algorithms.

### 7.4 Running from the Toolbox

1. Open **Processing ▸ Toolbox**.
2. Expand **Plover** and double-click **Boundary-aware TSP route**.
3. Set **Points to visit**.
4. Set **Boundary polygon(s)**, or leave it blank for a plain straight-line tour.
5. Adjust **Boundary buffer**, **Start point index**, **Return to start** and **Points outside the boundary** as needed.
6. Choose output locations, or leave them as temporary layers.
7. Click **Run**.

Progress is reported to the dialog's progress bar and the run can be cancelled. Informational notes — repaired boundary polygons, enclosed features treated as holes, skipped points — are written to the **Log** tab of the algorithm dialog.

### 7.5 Using it in the Graphical Model Designer

Because Plover is a normal Processing algorithm, it can be dropped into a model like any other.

1. Open **Processing ▸ Graphical Modeler**.
2. Add model inputs — typically a vector layer input for the points and one for the boundary.
3. On the **Algorithms** tab, search for `Boundary-aware TSP route` and add it.
4. Connect the inputs, then set the remaining parameters as fixed values or expose them as model inputs.
5. Name and save the model.

A common pattern is to place an **Extract by location** step before Plover so a project-wide point layer is filtered to one field, then routed. Plover's own skip mode (`ON_OUTSIDE = 1`) usually achieves the same result in one step.

### 7.6 Batch mode: many fields in one run

Batch mode is the fastest way to route a set of fields.

1. In the Toolbox, right-click **Boundary-aware TSP route** and choose **Execute as Batch Process…**.
2. Each row is one run. Fill in the points layer, boundary layer and outputs per row.
3. Use **Autofill** on a column to populate it quickly — for example, filling the boundary column from a folder of field polygons.
4. Click **Run**.

Batch runs are where `ON_OUTSIDE = 1` (skip) earns its keep: point one shared point layer at every field boundary in turn, and each row routes only the points inside that field.

**Start point in skip mode.** The algorithm resolves `START_INDEX` against the *original* point list, remembers that feature, then re-finds it after the outside points are dropped. If the point you nominated was itself outside the boundary and was skipped, the run does not fail — it falls back to the first remaining point and warns:

```
Start point lies outside the boundary and was skipped;
starting from the first in-boundary point instead.
```

### 7.7 Scripting with PyQGIS

Open **Plugins ▸ Python Console** and run:

```python
import processing

result = processing.run("plover:tsproute", {
    "POINTS": points_layer,        # QgsVectorLayer, or a layer id / file path
    "BOUNDARY": boundary_layer,    # optional - omit or pass None for a straight-line tour
    "BUFFER": 0.5,
    "START_INDEX": 0,
    "ROUND_TRIP": True,
    "ON_OUTSIDE": 0,               # 0 = fail if any point is outside, 1 = skip them
    "OUTPUT_ROUTE": "TEMPORARY_OUTPUT",
    "OUTPUT_ORDER": "TEMPORARY_OUTPUT",
})

print(result["OUTPUT_ROUTE"], result["OUTPUT_ORDER"])
```

To read the total length back out:

```python
from qgis.core import QgsVectorLayer

route = result["OUTPUT_ROUTE"]
layer = route if isinstance(route, QgsVectorLayer) else QgsVectorLayer(route, "route", "ogr")
feature = next(layer.getFeatures())
print(f"{feature['stops']} stops, {feature['length']:.1f} map units, round trip: {feature['round_trip']}")
```

A minimal straight-line run with no boundary at all:

```python
result = processing.run("plover:tsproute", {
    "POINTS": points_layer,
    "OUTPUT_ROUTE": "TEMPORARY_OUTPUT",
})
```

Looping over several field boundaries, routing each field's points:

```python
import processing
from qgis.core import QgsProject

points = QgsProject.instance().mapLayersByName("All sample points")[0]

for boundary in QgsProject.instance().mapLayersByName("Fields"):
    out = processing.run("plover:tsproute", {
        "POINTS": points,
        "BOUNDARY": boundary,
        "BUFFER": 1.0,
        "ON_OUTSIDE": 1,           # skip anything outside this field
        "ROUND_TRIP": True,
        "OUTPUT_ROUTE": "TEMPORARY_OUTPUT",
        "OUTPUT_ORDER": None,      # suppress the visit-order layer
    })
    print(boundary.name(), "->", out["OUTPUT_ROUTE"])
```

> Use `processing.run` inside scripts rather than `processing.runAndLoadResults`, unless you actually want every intermediate layer added to the project.

### 7.8 Running headless from the command line

`qgis_process` runs algorithms without opening QGIS, which suits scheduled jobs and servers.

```bash
qgis_process run plover:tsproute --POINTS=points.gpkg --BOUNDARY=field.gpkg --BUFFER=0.5 --ROUND_TRIP=true --ON_OUTSIDE=1 --OUTPUT_ROUTE=route.gpkg
```

**Important quirk — `qgis_process` does not see profile plugins.** By default `qgis_process` loads only core plugins. A plugin installed normally into your user profile is invisible to it, and the command above fails with an unknown-algorithm error.

The fix is to point `QGIS_PLUGINPATH` at a directory that *contains* the plugin folder, then enable the plugin by its folder name — `tsp_route_generator`, not `plover`:

Windows PowerShell:

```powershell
$env:QGIS_PLUGINPATH = "C:\path\to\folder-containing-the-plugin"
qgis_process plugins enable tsp_route_generator
qgis_process run plover:tsproute --POINTS=points.gpkg --OUTPUT_ROUTE=route.gpkg
```

Linux or macOS:

```bash
export QGIS_PLUGINPATH="/path/to/folder-containing-the-plugin"
qgis_process plugins enable tsp_route_generator
qgis_process run plover:tsproute --POINTS=points.gpkg --OUTPUT_ROUTE=route.gpkg
```

Confirm it is visible with:

```bash
qgis_process list
```

> **PowerShell and the pipe character.** Data source strings often contain a pipe, as in `field.gpkg|layername=fields`. PowerShell treats `|` as its own pipe operator and will mangle the argument. Put the stop-parsing token `--%` before the arguments, or quote the whole value.

### 7.9 If the Plover group is missing from the Toolbox

1. Confirm the plugin is installed and ticked in **Plugins ▸ Manage and Install Plugins ▸ Installed**.
2. Restart QGIS — the provider is registered when the plugin loads.
3. Check **Processing ▸ Options ▸ Providers** and make sure **Plover** is enabled.
4. Look in **View ▸ Panels ▸ Log Messages** for load errors on the **Plugins** tab.

### 7.10 Validation the algorithm performs

The algorithm checks its inputs before doing any work and raises a clear error rather than producing a wrong answer:

- The working layer must use a **projected** CRS. A geographic CRS raises `The boundary layer uses a geographic CRS (degrees); reproject to a projected CRS (e.g. UTM) first.` — or `point layer` in place of `boundary layer` when no boundary was supplied.
- A boundary that contributes no usable polygons raises `Boundary layer contains no usable polygons.`
- Fewer than two usable points raises `Need at least two point features.`
- An out-of-range start index raises `Start point index must be between 0 and <n>.`
- Points outside the buffered boundary in fail mode raise an error naming up to twelve feature ids.
- Fewer than two points remaining after skipping raises `Only <n> point(s) fall inside the boundary — need at least two. Increase the buffer or use a boundary that contains more points.`

All of these are covered in detail in chapter 8.
