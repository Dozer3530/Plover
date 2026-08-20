## 3. Preparing Your Data

Plover is deliberately undemanding about attributes — it never reads a single field from your input layers. What it *is* strict about is geometry and coordinate reference systems. Almost every "Plover won't run" support question comes down to one of three things: a layer in degrees, a boundary that is not really closed around the points, or a slough that was digitised in a way Plover cannot recognise as a hole.

This chapter explains exactly what the inputs must look like, exactly what Plover does to them, and how to fix them when they are wrong.

### 3.1 What Plover needs, at a glance

| Input | Required? | Geometry | Attributes needed | Notes |
|---|---|---|---|---|
| Points to visit | Yes | Point layer (single or multipart) | None | At least two usable point features |
| Boundary layer | No | Polygon layer (single or multipart) | None | All features are merged into one routing region |

Both dropdowns in the dialog are filtered by geometry type, so a line layer or a table simply will not appear in the list. In the dialog the labels are **Points to visit:** and **Boundary layer:**. In the Processing algorithm they are **Points to visit** and **Boundary polygon(s)**.

Plover writes its own output fields (`length`, `stops`, `round_trip` on the route; `visit_order`, `source_fid`, `leg_length` on the visit-order layer). Nothing in your input layer is copied through, so you do not need to add an "order" or "id" column before running. The only link back to your source data is `source_fid`, which stores the QGIS feature ID of the input point.

[[FIGURE: map-inputs | A typical Plover input set: a sampling point layer, a field boundary polygon, and a slough digitised as an interior ring inside that polygon.]]

---

### 3.2 Coordinate reference systems

This is the single most important section in the chapter. Plover measures everything in straight-line map units. If the map units are degrees, every distance it reports and every tolerance you type is nonsense — so Plover refuses to run rather than produce a plausible-looking, wrong answer.

#### 3.2.1 The "working CRS"

Plover picks one CRS and does all of its geometry work in it. That CRS is called the *working CRS* in this guide, and which layer supplies it depends on whether you gave Plover a boundary:

| Situation | Working CRS is taken from | What gets reprojected |
|---|---|---|
| A boundary layer is selected | The **boundary layer's** CRS | The points are reprojected into the boundary's CRS |
| **Boundary layer** is left empty | The **point layer's** CRS | Nothing — the points are already in the working CRS |

The boundary geometry is never reprojected. It is used exactly as it is stored, and it defines the coordinate space that everything else is pulled into.

Three consequences worth internalising:

1. **The output layers are created in the working CRS**, not in your project CRS. A route computed against a boundary in NAD83 / UTM zone 11N comes back as a NAD83 / UTM zone 11N layer, whatever the project is set to. QGIS will reproject it on the fly for display, so it will still line up on screen.
2. **The boundary buffer is in working-CRS units.** The dialog spin box is labelled **Boundary buffer:** and its suffix is literally `" map units"`. With a UTM boundary those units are metres, so the default `0.5` means half a metre.
3. **Only the working CRS is checked** for being geographic (see below). Your point layer's own CRS is not checked when a boundary is present, because the points are going to be reprojected anyway.

#### 3.2.2 The projected-CRS rule

Before it does anything else, Plover tests whether the working CRS is geographic (an angular, latitude/longitude system such as EPSG:4326 WGS 84). If it is, the run stops immediately with an error. The wording differs slightly between the dialog and Processing, and the word "boundary" or "point" is substituted depending on which layer supplied the working CRS:

| Where | Exact message |
|---|---|
| Dialog, with a boundary selected | `The boundary layer uses a geographic CRS (degrees). Distances would be meaningless — reproject to a projected CRS (e.g. UTM) first.` |
| Dialog, no boundary selected | `The point layer uses a geographic CRS (degrees). Distances would be meaningless — reproject to a projected CRS (e.g. UTM) first.` |
| Processing, with a boundary | `The boundary layer uses a geographic CRS (degrees); reproject to a projected CRS (e.g. UTM) first.` |
| Processing, no boundary | `The point layer uses a geographic CRS (degrees); reproject to a projected CRS (e.g. UTM) first.` |

In the dialog this appears as red text in the status line under the progress bar; nothing is computed and no layers are added. In Processing it is raised as an algorithm exception, so the run fails and appears in the algorithm's **Log** tab.

Note the asymmetry that follows from 3.2.1: **a point layer in EPSG:4326 is perfectly acceptable as long as you also supply a boundary in a projected CRS.** Plover will reproject the points into the boundary's CRS and carry on. It is only when the *working* CRS is geographic that the run is refused. If you drop the boundary from that same setup, the run will now fail, because the point layer has become the working CRS.

#### 3.2.3 Why degrees would be meaningless

A projected CRS has axes measured in a real ground unit — metres, usually — and one unit is the same length everywhere on the map. A geographic CRS measures in degrees of latitude and longitude, and a degree is not a fixed ground distance:

- One degree of latitude is roughly 111 km anywhere.
- One degree of longitude is about 111 km at the equator but only about 68 km at 52° N (central Alberta), because the meridians converge as you go north.

So in degrees the x and y axes have different scales, and the x scale changes with latitude. Every calculation Plover performs — the straight-line distance between two points, the total tour length, the buffer around the field edge — uses plain Pythagorean arithmetic on those coordinates. In degrees that produces a number with no physical meaning, and it is systematically biased: east–west legs would be over-weighted relative to north–south legs, so the "optimised" visiting order would genuinely be the wrong order, not merely a right order with wrong units.

The tolerances go wrong even more dramatically. The default buffer of `0.5` map units means half a metre in UTM. In degrees it would mean half a degree — roughly 55 km. Every point in the province would count as "inside the boundary".

#### 3.2.4 Automatic reprojection of the points

When a boundary is present and the point layer's CRS differs from it, Plover builds a coordinate transform and converts each point on the fly. Your point layer on disk is never modified.

In the dialog this is announced in the log (see 3.4.5) as, for example:

```
Reprojecting points from EPSG:4326 to EPSG:26911 for routing.
```

If an individual point cannot be transformed, the dialog skips just that feature and logs:

```
Skipping feature 42: reprojection failed.
```

The Processing algorithm performs the same transform (using the Processing context's transform context) but does not trap per-feature transform failures — a transform error there will fail the whole algorithm rather than silently drop a point.

Because the transform is silent-by-default and per-feature, it is worth checking the log after a run that mixed CRSs, especially if the reported number of stops is lower than the number of points you expected.

#### 3.2.5 How to reproject a layer

If you are told to reproject, use one of these. All of them create a **new** dataset; none of them alter the original.

**Method A — Processing (recommended, repeatable):**

1. Open **Vector → Data Management Tools → Reproject Layer…**
2. **Input layer**: your boundary (or point) layer.
3. **Target CRS**: a projected CRS covering your field — for the Canadian prairies, NAD83 / UTM zone 11N (`EPSG:26911`) or zone 12N (`EPSG:26912`) are the usual choices; pick the zone your field actually falls in. If your organisation standardises on an Alberta 3TM or 10TM zone, use that instead.
4. **Reprojected**: give it a real filename (a GeoPackage is a good default) rather than leaving it as a temporary layer.
5. Click **Run**, then use the new layer in Plover.

**Method B — Export:**

1. Right-click the layer in the **Layers** panel → **Export → Save Features As…**
2. Set **Format** (GeoPackage), **File name**, and importantly the **CRS** selector to your projected CRS.
3. Tick **Add saved file to map** and click **OK**.

**Method C — from the Python console:**

```python
import processing

processing.run("native:reprojectlayer", {
    "INPUT": "C:/data/field_boundary.shp",
    "TARGET_CRS": "EPSG:26911",
    "OUTPUT": "C:/data/field_boundary_utm11n.gpkg",
})
```

> **Do not confuse reprojecting with re-declaring.** Layer **Properties → Source → Set Source Coordinate Reference System** (and the "assign CRS" tools) only change the label QGIS attaches to the existing coordinates. If your data really is in degrees, telling QGIS it is UTM will not convert anything — it will place your field somewhere off the coast of Africa and Plover will happily compute a route through nonsense coordinates. Always convert the geometry, do not relabel it.

Changing the **project** CRS also has no effect on this check. Plover reads the *layer's* CRS, not the project's.

---

### 3.3 The point layer

#### 3.3.1 Basic requirements

- It must be a point layer. The **Points to visit:** dropdown only lists point layers; the Processing parameter only accepts point vector sources.
- At least two features must survive the filtering described below.
- No attributes are required.
- Any provider works: GeoPackage, shapefile, delimited text (CSV loaded as points), memory/scratch layers, a database layer, and so on.

#### 3.3.2 How each feature is treated

Plover walks the features in layer order and applies these rules, in this order:

| Condition | What Plover does | Dialog log message |
|---|---|---|
| Geometry is NULL or empty | Skipped | `Skipping feature <id>: empty geometry.` |
| Geometry is not a point (e.g. a mixed-geometry layer) | Skipped | `Skipping feature <id>: not a point.` |
| Geometry is **multipart** (MultiPoint) | The geometry's **centroid** is used as the single waypoint | *(no message)* |
| Single-part point | Its coordinate is used | *(no message)* |
| Reprojection fails for that feature | Skipped (dialog only) | `Skipping feature <id>: reprojection failed.` |

Two behaviours deserve emphasis:

**Multipart points collapse to a centroid.** A MultiPoint feature holding three cluster members does not become three stops — it becomes one stop at the centroid of those three, which may be a location where no sample was actually taken. Shapefiles in particular are often written as MultiPoint even when every feature has exactly one point; in that harmless case the centroid *is* the point and nothing changes. But if you genuinely have multi-member features, run **Vector → Geometry Tools → Multipart to Singleparts** first so that each sample site becomes its own waypoint.

**The dialog logs skips; Processing does not.** The Processing algorithm applies the same NULL / empty / non-point filter but drops those features silently. If you are running in batch or in a model, reconcile the `stops` count in the output against your expected point count rather than assuming everything was included.

#### 3.3.3 Too few points

If fewer than two usable points remain, the run stops:

| Where | Exact message |
|---|---|
| Dialog | `Need at least two point features to build a route.` |
| Processing | `Need at least two point features.` |

If you see this on a layer that visibly has plenty of points, the cause is almost always the filtering table above (empty geometries, or a layer whose "points" are actually something else) or the **Use only selected points** option below.

#### 3.3.4 Using a selection

The dialog has a checkbox labelled **Use only selected points**. When it is ticked, Plover routes only the currently selected features of the point layer. If nothing is selected you get:

```
'Use only selected points' is on, but no points are selected.
```

In the Processing algorithm the equivalent is the standard **Selected features only** option on the **Points to visit** input.

The boundary layer is different: the dialog always reads **every** feature of the boundary layer, regardless of what is selected on it. A selection on the boundary layer has no effect in the dialog. (In Processing, the boundary is an ordinary feature source, so its own **Selected features only** option does apply.)

#### 3.3.5 Point ordering and the start point

The dialog lets you choose the start with the **Start at point:** feature picker, so ordering does not matter to you there.

The Processing algorithm instead takes **Start point index (order of the input layer)**, a zero-based number. Be aware that this indexes the list of points Plover actually kept, *after* the NULL/empty/non-point filter has run. If features 0 and 1 of your layer have empty geometries, index `0` refers to what you think of as the third feature. An out-of-range value fails with:

```
Start point index must be between 0 and <n-1>.
```

where `<n-1>` is one less than the number of kept points. This is a good reason to clean empty geometries out of a layer before using it in a model or batch run, where you cannot see what was dropped.

---

### 3.4 The boundary layer

The boundary is optional. Leave **Boundary layer:** empty (the dropdown allows an empty entry) and Plover solves a plain straight-line tour with no obstacle avoidance; the **Boundary buffer:** and **Points outside boundary:** controls are greyed out because they have nothing to act on. Everything in this section applies only when you do supply a boundary.

#### 3.4.1 Basic requirements

- It must be a polygon layer. The dropdown filters to polygon layers; the Processing parameter accepts polygon vector sources only.
- Its CRS must be projected (section 3.2.2) — it is the working CRS.
- No attributes are required.
- It may contain one feature or many. It may contain multipart polygons. It may contain interior rings (holes).

#### 3.4.2 How multiple boundary features are merged

Plover does not ask you which polygon is "the field". It reads every boundary feature that has a geometry and merges them into a single routing region using a fixed rule. Understanding this rule is what lets you model sloughs as separate polygons.

The merge works like this:

1. **Filter.** Features with no geometry, empty geometry, or non-polygon geometry are dropped.
2. **Repair.** Any geometry that is not GEOS-valid is passed through `makeValid()` (see 3.4.4).
3. **Sort by area, largest first.**
4. **Seed.** The largest polygon becomes the working region.
5. **Fold in each remaining polygon, in descending area order:**
   - If the current region **fully contains** the polygon, the polygon is **subtracted** — it becomes a hole, an exclusion zone.
   - Otherwise, the polygon is **unioned** into the region — the routable area grows.

Two details follow from step 5 that are easy to get wrong:

- **The test is against the region as it stands at that moment,** not against the original largest polygon. So if two adjacent quarter-sections are unioned into one region first, a slough polygon sitting inside either of them will still be recognised as fully enclosed and subtracted.
- **"Fully contains" means fully.** If any part of the inner polygon pokes outside the region — even slightly, because it was snapped sloppily to a field edge — the containment test fails and the polygon is **unioned instead of subtracted**. Instead of an exclusion zone you get a bump added to the field. This failure is quiet: the only symptom is a route that happily drives straight through the slough. If that happens, check that the slough polygon is genuinely inside the field polygon and does not overhang it.

When a polygon is subtracted, Plover records a note (see 3.4.5):

```
Treated a fully-enclosed boundary feature as an exclusion zone (hole).
```

If nothing usable survives step 1 and 2, the run stops:

| Where | Exact message |
|---|---|
| Dialog | `The boundary layer contains no usable polygons.` |
| Processing | `Boundary layer contains no usable polygons.` |

#### 3.4.3 Multipart boundary features

A multipart polygon feature is accepted, and its parts all contribute to the region. But note carefully: **the enclosure rule compares whole features against each other, never parts within one feature.** Plover never inspects the parts of a single multipart geometry to see whether one encloses another.

Practical consequence: if you draw the field as part 1 and the slough as part 2 of the *same* multipart feature, the slough will **not** become an exclusion zone. That geometry is also self-overlapping and therefore invalid, so it will be pushed through `makeValid()` first and you will end up routing across whatever that repair produces. Use one of the two supported patterns in section 3.5 instead.

Multipart features are entirely fine when the parts are genuinely separate areas — two disjoint blocks of the same field, for instance.

#### 3.4.4 Invalid polygons and automatic repair

Self-intersecting rings, bow ties, duplicated vertices and rings that cross themselves are common in hand-digitised and legacy boundary data. Plover checks each polygon with a GEOS validity test and, if it fails, attempts `makeValid()`:

| Outcome | Note recorded |
|---|---|
| Repair produced a usable geometry | `Repaired an invalid boundary polygon with makeValid().` |
| Repair produced nothing usable | `Skipped an invalid boundary polygon that could not be repaired.` |

Both of these are notes about your data, not about Plover. Repair is a best-effort rescue: `makeValid()` will produce *a* valid geometry, but not necessarily the geometry you meant. A bow-tie polygon can come back as two lobes; a self-overlapping outline can come back with the overlap merged away. **If you see a repair note, treat the resulting route as provisional and fix the source polygon properly** with **Vector → Geometry Tools → Check Validity** and the vertex tool, or with **Vector → Geometry Tools → Fix Geometries** to produce a cleaned copy you can inspect.

The second message means a polygon was thrown away entirely. If your route looks like it is ignoring part of the field, that message is the first thing to look for.

#### 3.4.5 Where the notes appear

The boundary notes above are informational; they never stop the run, so they are easy to miss.

- **In the dialog** they are written to the QGIS message log under the tag `Plover`, at warning level. Open it with **View → Panels → Log Messages**, then select the **Plover** tab. Get into the habit of checking this tab after any run on unfamiliar boundary data.
- **In Processing** they are pushed into the algorithm feedback, so they appear in the **Log** tab of the algorithm dialog (and in the model/batch log).

---

### 3.5 Modelling a slough (or any exclusion zone)

A slough, rock pile, wetland, fenced yard site or no-drive zone is anything you want the route to go *around* rather than *through*. Plover supports exactly two ways to express one, and both end up in the same place — an area that is not part of the routing region, so no straight visibility segment is allowed to cross it.

| | Option A: interior ring | Option B: separate enclosed polygon |
|---|---|---|
| How it is stored | A hole inside the field polygon feature | Its own polygon feature in the same boundary layer |
| Recognised by | Native polygon geometry — holes are not part of a polygon's interior | The enclosure rule in 3.4.2 |
| Feature count in the layer | 1 | 2 or more |
| Must be fully inside the field | Yes, by construction | Yes — and this is enforced by a containment test that fails quietly |
| Can it be toggled on and off easily | No — you must delete the ring | Yes — delete or filter out the feature |
| Best for | A stable, permanent field description | Wetland inventories, seasonal exclusions, zones maintained by someone else |

#### 3.5.1 Option A — digitise the slough as an interior ring

This is the most robust option, because the hole is part of the polygon itself and there is no containment test to fail.

1. Turn on the **Advanced Digitizing** toolbar if it is not visible: **View → Toolbars → Advanced Digitizing Toolbar**.
2. Select the boundary layer in the **Layers** panel and click **Toggle Editing** (the pencil).
3. Select the field polygon feature.
4. Choose the **Add Ring** tool.
5. Digitise the slough outline **entirely inside** the field polygon. Do not let any vertex fall outside the outer ring — a ring that crosses the outer boundary is rejected or produces an invalid geometry.
6. Right-click to close the ring.
7. Click **Save Layer Edits**, then **Toggle Editing** off.
8. Verify with **Vector → Geometry Tools → Check Validity** that the result reports no invalid geometries.

If the slough already exists as its own polygon layer, the **Fill Ring** tool's counterpart workflow is to use **Vector → Geoprocessing Tools → Difference**, with the field layer as **Input layer** and the slough layer as **Overlay layer**. The output is the field polygon with the slough punched out as a proper interior ring, ready to hand to Plover.

#### 3.5.2 Option B — digitise the slough as a separate polygon inside the field

This suits the common case where sloughs are maintained as their own inventory layer and the field outline must stay a clean, simple polygon.

1. Put the field polygon and the slough polygons **in the same layer**. Plover reads one boundary layer, so if they live in separate files, merge them first with **Vector → Data Management Tools → Merge Vector Layers** (both layers must be in the same CRS, and that CRS must be projected).
2. Enable snapping (**Project → Snapping Options…**) so the slough vertices are placed precisely.
3. Digitise the slough as an ordinary new polygon feature, **entirely within** the field polygon.
4. Critically: **keep it strictly inside.** Do not let the slough overhang the field edge anywhere. If it does, the containment test fails and Plover will union it into the field instead of subtracting it — you will get no error, just a route that ignores the slough.
5. Save the edits and run Plover. Confirm in the log that you see `Treated a fully-enclosed boundary feature as an exclusion zone (hole).` once per slough. **That log line is your confirmation that Option B worked.** If it is absent, the polygon was not recognised as enclosed.

#### 3.5.3 What not to do

- **Do not put the field and the slough in the same multipart feature.** Parts within one feature are never compared to each other, so the slough will not become a hole (see 3.4.3).
- **Do not use a separate slough layer and expect Plover to read it.** Plover takes exactly one boundary layer.
- **Do not rely on a slough polygon that shares or crosses the field edge.** If the excluded area genuinely touches the field boundary — a wetland running off the edge of the quarter — model it by cutting it out of the field outline instead (Option A, or **Difference**), so the field polygon simply does not extend into it.
- **Do not model an exclusion zone as a line or as an unclosed polygon.** Only polygon geometries are considered.

#### 3.5.4 A note on the buffer

The **Boundary buffer:** value (default `0.5`, in working-CRS map units) enlarges the region slightly before routing, so that points sitting exactly on the field edge are still routable. The same enlargement applies to holes, which means the route may also cut this far *into* an exclusion zone. If you have a slough with a hard no-entry requirement, keep the buffer small; if your sample points were captured on the fence line with a metre of GPS drift, you will need it larger. Either way, remember that the number is in working-CRS units — metres under UTM.

---

### 3.6 Data hygiene checklist

Run through this before your first Plover run on a new dataset. It takes two minutes and prevents nearly every failure mode described above.

**Coordinate reference systems**

- [ ] The layer that will supply the working CRS (the boundary if you have one, otherwise the points) is in a **projected** CRS — check **Layer Properties → Information**, and confirm the units are metres, not degrees.
- [ ] If you reprojected anything, you *converted* the geometry (Reproject Layer / Save Features As) rather than re-declaring the CRS.
- [ ] You know what one map unit means, because you are about to type a buffer in those units.

**Point layer**

- [ ] It is a point layer and it contains at least two features.
- [ ] No NULL or empty geometries (**Vector → Geometry Tools → Check Validity**, or a `$geometry is null` expression filter).
- [ ] Multipart points converted to single parts if any feature genuinely holds more than one point (**Multipart to Singleparts**).
- [ ] Points are where you think they are — zoom in and look, rather than trusting the extent.
- [ ] If you plan to use **Use only selected points**, the selection is made *before* you click **Run**.
- [ ] For Processing runs, you have accounted for the fact that **Start point index** counts kept points, not raw layer rows.

**Boundary layer (if used)**

- [ ] It is a polygon layer, in the same projected CRS you intend as the working CRS.
- [ ] Every polygon is valid — **Check Validity** reports zero invalid geometries. Fix them at source rather than relying on `makeValid()`.
- [ ] Sloughs and exclusion zones are modelled as interior rings, or as separate polygons **fully** inside the field polygon (and in the *same* layer).
- [ ] No stray polygons from other fields are sitting in the layer — remember that everything is merged, so an unrelated polygon elsewhere in the section will be unioned into your routing region.
- [ ] Field and slough are not two parts of one multipart feature.

**After the first run**

- [ ] Open **View → Panels → Log Messages → Plover** (or the Processing **Log** tab) and read the notes. Look specifically for `Repaired an invalid boundary polygon with makeValid().`, `Skipped an invalid boundary polygon that could not be repaired.`, `Treated a fully-enclosed boundary feature as an exclusion zone (hole).`, and any `Skipping feature …` lines.
- [ ] Check that the number of stops reported matches the number of points you expected to visit.
- [ ] Look at the route on the map and confirm it goes around, not through, every exclusion zone.