# -*- coding: utf-8 -*-
"""Generate the figures used by the Plover User Guide.

Run with a QGIS Python from the repo root:

    "C:/Program Files/QGIS 4.0.1/bin/python-qgis.bat" docs/make_figures.py

Figures are written to docs/images/. Every map figure is produced by calling the
plugin's own routing pipeline and styling helpers, so the pictures in the guide
always match what the plugin actually draws.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "docs", "images")
sys.path.insert(0, REPO)

from qgis.core import (  # noqa: E402
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsFillSymbol,
    QgsGeometry,
    QgsMapSettings,
    QgsMapRendererParallelJob,
    QgsPointXY,
    QgsRectangle,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QSize, Qt  # noqa: E402
from qgis.PyQt.QtGui import (  # noqa: E402
    QColor,
    QFont,
    QImage,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
)

app = QgsApplication([], True)
app.initQgis()

# --- force a light, neutral look so figures print well on white paper --------
app.setStyle("Fusion")
pal = QPalette()
for role, colour in [
    (QPalette.ColorRole.Window, "#f4f4f4"),
    (QPalette.ColorRole.WindowText, "#1b1b1b"),
    (QPalette.ColorRole.Base, "#ffffff"),
    (QPalette.ColorRole.AlternateBase, "#ececec"),
    (QPalette.ColorRole.Text, "#1b1b1b"),
    (QPalette.ColorRole.Button, "#ebebeb"),
    (QPalette.ColorRole.ButtonText, "#1b1b1b"),
    (QPalette.ColorRole.Highlight, "#3a76c4"),
    (QPalette.ColorRole.HighlightedText, "#ffffff"),
]:
    pal.setColor(role, QColor(colour))
pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#8c8c8c"))
pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#8c8c8c"))
pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#8c8c8c"))
app.setPalette(pal)
app.setFont(QFont("Segoe UI", 9))

from tsp_route_generator.route_task import compute_route  # noqa: E402
from tsp_route_generator.tsp_route_generator_dialog import (  # noqa: E402
    TSPRouteGeneratorDialog,
)

CRS = "EPSG:32612"
os.makedirs(OUT, exist_ok=True)


# ---------------------------------------------------------------- sample data

def rect(x0, y0, x1, y1):
    return [QgsPointXY(x0, y0), QgsPointXY(x1, y0), QgsPointXY(x1, y1),
            QgsPointXY(x0, y1), QgsPointXY(x0, y0)]


def blob(cx, cy, rx, ry, n=26, wobble=0.16):
    """Irregular closed ring — reads as a slough rather than a rectangle."""
    import math
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        f = 1.0 + wobble * math.sin(3 * a) + 0.5 * wobble * math.cos(5 * a + 1.1)
        pts.append(QgsPointXY(cx + rx * f * math.cos(a), cy + ry * f * math.sin(a)))
    pts.append(pts[0])
    return pts


# A realistic prairie quarter: a large slough runs in from the west side, so the
# field itself is concave (a "bay" bitten out of it), plus two interior sloughs.
# The bay is what makes the boundary matter - a route that ignores it cuts
# straight across open water, which is exactly the mistake Plover prevents.
FIELD = [
    QgsPointXY(0, 0), QgsPointXY(1000, 0), QgsPointXY(1000, 620),
    QgsPointXY(0, 620), QgsPointXY(0, 410), QgsPointXY(545, 410),
    QgsPointXY(545, 215), QgsPointXY(0, 215), QgsPointXY(0, 0),
]
SLOUGH_A = blob(790, 300, 95, 78)     # interior slough, east side
SLOUGH_B = blob(300, 510, 65, 42)     # small interior slough, north-west

SAMPLE_POINTS = [
    (80, 90), (270, 60), (450, 120),        # south-west of the bay
    (85, 530), (255, 575), (450, 490),      # north-west of the bay
    (600, 300),                             # the neck, east of the bay
    (620, 180), (620, 450),
    (760, 90), (950, 150), (930, 240),
    (960, 420), (880, 540),
]


def field_geom(with_sloughs=True):
    rings = [FIELD]
    if with_sloughs:
        rings += [SLOUGH_A, SLOUGH_B]
    return QgsGeometry.fromPolygonXY(rings)


def make_point_layer(coords, name="Sample points"):
    lyr = QgsVectorLayer(f"Point?crs={CRS}&field=name:string(20)", name, "memory")
    feats = []
    for i, (x, y) in enumerate(coords):
        f = QgsFeature(lyr.fields())
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
        f.setAttributes([f"P{i + 1}"])
        feats.append(f)
    lyr.dataProvider().addFeatures(feats)
    lyr.updateExtents()
    lyr.renderer().setSymbol(_point_symbol())
    return lyr


def _point_symbol():
    from qgis.core import QgsMarkerSymbol
    return QgsMarkerSymbol.createSimple({
        "name": "circle", "color": "#2b6cb0", "outline_color": "white",
        "outline_width": "0.4", "size": "2.6",
    })


def make_boundary_layer(geom, name="Field boundary"):
    lyr = QgsVectorLayer(f"Polygon?crs={CRS}", name, "memory")
    f = QgsFeature()
    f.setGeometry(geom)
    lyr.dataProvider().addFeatures([f])
    lyr.updateExtents()
    lyr.renderer().setSymbol(QgsFillSymbol.createSimple({
        "color": "230,240,222,255",
        "outline_color": "#4a7c3f",
        "outline_width": "0.8",
    }))
    return lyr


# ------------------------------------------------------------- map rendering

def render(layers, path, size=(1500, 950), extent=None, margin=0.06, bg="#ffffff"):
    """Render layers (bottom-first) to a PNG."""
    ms = QgsMapSettings()
    # QgsMapSettings draws the FIRST layer on top, like the QGIS layer tree,
    # so callers pass layers top-first.
    ms.setLayers(list(layers))
    ms.setBackgroundColor(QColor(bg))
    ms.setOutputSize(QSize(*size))
    ms.setDestinationCrs(QgsCoordinateReferenceSystem(CRS))
    ms.setOutputDpi(150)
    try:
        ms.setFlag(Qgis.MapSettingsFlag.Antialiasing, True)
        ms.setFlag(Qgis.MapSettingsFlag.DrawLabeling, True)
        ms.setFlag(Qgis.MapSettingsFlag.UseAdvancedEffects, True)
    except AttributeError:
        ms.setFlag(QgsMapSettings.Antialiasing, True)
        ms.setFlag(QgsMapSettings.DrawLabeling, True)

    if extent is None:
        extent = QgsRectangle()
        for lyr in layers:
            e = lyr.extent()
            if not e.isEmpty():
                extent.combineExtentWith(e)
    ext = QgsRectangle(extent)
    ext.grow(max(ext.width(), ext.height()) * margin)
    # match the output aspect so nothing is squashed
    target = size[0] / float(size[1])
    if ext.width() / ext.height() < target:
        need = ext.height() * target
        cx = ext.center().x()
        ext.setXMinimum(cx - need / 2)
        ext.setXMaximum(cx + need / 2)
    else:
        need = ext.width() / target
        cy = ext.center().y()
        ext.setYMinimum(cy - need / 2)
        ext.setYMaximum(cy + need / 2)
    ms.setExtent(ext)

    job = QgsMapRendererParallelJob(ms)
    job.start()
    job.waitForFinished()
    img = job.renderedImage()
    img.save(path, "PNG")
    print("  wrote", os.path.relpath(path, REPO))
    return path


# ------------------------------------------------- build routed output layers

_dlg_for_style = None


def style_helpers():
    """Reuse the plugin's own styling so figures match real output."""
    global _dlg_for_style
    if _dlg_for_style is None:
        _dlg_for_style = TSPRouteGeneratorDialog(None, None)
    return _dlg_for_style


def routed_layers(points, boundary, closed=True, start=0, buffer_dist=0.5):
    """Run the real pipeline and return (route_layer, order_layer, result)."""
    pts = [QgsPointXY(x, y) for x, y in points]
    result = compute_route(pts, boundary, buffer_dist, start, closed=closed)

    route = QgsVectorLayer(
        f"LineString?crs={CRS}&field=length:double&field=stops:integer"
        "&field=round_trip:string(3)", "Plover route", "memory")
    f = QgsFeature(route.fields())
    f.setGeometry(QgsGeometry.fromPolylineXY(result.route_points))
    f.setAttributes([float(result.total_length), len(result.order),
                     "yes" if closed else "no"])
    route.dataProvider().addFeature(f)
    route.updateExtents()

    order = QgsVectorLayer(
        f"Point?crs={CRS}&field=visit_order:integer&field=source_fid:integer"
        "&field=leg_length:double", "Plover visit order", "memory")
    feats = []
    for rank, wp in enumerate(result.order):
        pf = QgsFeature(order.fields())
        pf.setGeometry(QgsGeometry.fromPointXY(pts[wp]))
        leg = result.leg_lengths[rank] if rank < len(result.leg_lengths) else 0.0
        pf.setAttributes([rank + 1, int(wp), float(leg)])
        feats.append(pf)
    order.dataProvider().addFeatures(feats)
    order.updateExtents()

    d = style_helpers()
    d._style_route_layer(route)
    d._style_order_layer(order)
    return route, order, result


# --------------------------------------------------------------- annotations

def annotate(src_png, out_png, rows, scale, margin=52, radius=15):
    """Add a left margin to a screenshot and number each row in it.

    ``rows`` is a list of (number, y) in *widget* coordinates; ``scale`` is the
    device-pixel ratio of the grab, so the badges line up on HiDPI captures.
    Badges sit outside the dialog so they never cover a label.
    """
    src = QPixmap(src_png)
    m = int(margin * scale)
    out = QPixmap(src.width() + m, src.height())
    out.fill(QColor("#ffffff"))

    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.drawPixmap(m, 0, src)

    font = QFont("Segoe UI", int(10 * scale))
    font.setBold(True)
    p.setFont(font)
    r = int(radius * scale)
    for num, y in rows:
        cy = int(y * scale)
        cx = m // 2
        p.setBrush(QColor("#E8590C"))
        p.setPen(QPen(QColor("#ffffff"), max(2, int(scale))))
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        p.setPen(QPen(QColor("#ffffff")))
        p.drawText(cx - r, cy - r, r * 2, r * 2,
                   int(Qt.AlignmentFlag.AlignCenter), str(num))
    p.end()
    out.save(out_png, "PNG")
    print("  wrote", os.path.relpath(out_png, REPO))


# ------------------------------------------------------- concept diagrams

def svg_to_png(svg_text, path, width, height):
    from qgis.PyQt.QtSvg import QSvgRenderer
    from qgis.PyQt.QtCore import QByteArray
    renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
    img = QImage(width, height, QImage.Format.Format_ARGB32)
    img.fill(QColor("#ffffff"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(p)
    p.end()
    img.save(path, "PNG")
    print("  wrote", os.path.relpath(path, REPO))


def _box(x, y, w, h, lines, fill="#eef4fb", stroke="#2b6cb0", fs=10):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" '
           f'fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>']
    total = len(lines)
    for i, ln in enumerate(lines):
        ty = y + h / 2 + (i - (total - 1) / 2.0) * (fs + 2.5) + fs * 0.35
        out.append(f'<text x="{x + w / 2}" y="{ty:.1f}" font-family="Segoe UI,Arial" '
                   f'font-size="{fs}" fill="#2B3540" text-anchor="middle">{ln}</text>')
    return "".join(out)


def _arrow(x1, y, x2, colour="#8a949e"):
    return (f'<line x1="{x1}" y1="{y}" x2="{x2 - 6}" y2="{y}" stroke="{colour}" '
            f'stroke-width="1.6"/>'
            f'<path d="M{x2},{y} L{x2 - 7},{y - 4} L{x2 - 7},{y + 4} Z" fill="{colour}"/>')


WORKFLOW_SVG = f'''<svg viewBox="0 0 760 235" xmlns="http://www.w3.org/2000/svg">
<rect width="760" height="235" fill="#ffffff"/>
<text x="380" y="20" font-family="Segoe UI,Arial" font-size="12" font-weight="bold"
      fill="#2B3540" text-anchor="middle">How a Plover run works</text>

{_box(10, 45, 108, 38, ["Points to visit"], "#eef4fb", "#2b6cb0")}
{_box(10, 108, 108, 38, ["Boundary polygon", "(optional)"], "#eef7ec", "#4a7c3f", 9)}

<path d="M118,64 C136,64 136,105 150,105" fill="none" stroke="#8a949e" stroke-width="1.6"/>
<path d="M156,105 L149,101 L149,109 Z" fill="#8a949e"/>
<path d="M118,127 C136,127 136,105 150,105" fill="none" stroke="#8a949e" stroke-width="1.6"/>

{_box(158, 78, 104, 54, ["Permitted region", "+ turn vertices"], "#fdf1e8", "#E8590C", 9)}
{_arrow(262, 105, 288)}
{_box(288, 78, 104, 54, ["Visibility", "graph"], "#fdf1e8", "#E8590C", 9)}
{_arrow(392, 105, 418)}
{_box(418, 78, 104, 54, ["Distance matrix", "(Dijkstra)"], "#fdf1e8", "#E8590C", 9)}
{_arrow(522, 105, 548)}
{_box(548, 78, 104, 54, ["Order: NN +", "2-opt + Or-opt"], "#fdf1e8", "#E8590C", 9)}

<path d="M652,105 C666,105 666,64 682,64" fill="none" stroke="#8a949e" stroke-width="1.6"/>
<path d="M688,64 L681,60 L681,68 Z" fill="#8a949e"/>
<path d="M652,105 C666,105 666,146 682,146" fill="none" stroke="#8a949e" stroke-width="1.6"/>
<path d="M688,146 L681,142 L681,150 Z" fill="#8a949e"/>

{_box(688, 45, 66, 38, ["Route", "line"], "#fdf1e8", "#E8590C", 9)}
{_box(688, 127, 66, 38, ["Visit order", "points"], "#fdf1e8", "#E8590C", 9)}

<text x="380" y="178" font-family="Segoe UI,Arial" font-size="9" fill="#6b7580"
      text-anchor="middle">With no boundary, the first two stages are skipped and every pair of
points is joined directly (plain Euclidean TSP).</text>
<text x="380" y="199" font-family="Segoe UI,Arial" font-size="9" fill="#6b7580"
      text-anchor="middle">The chosen order is finally stitched back into a real polyline using the
cached shortest paths, so each leg follows the true route.</text>
</svg>'''


VISIBILITY_SVG = '''<svg viewBox="0 0 700 310" xmlns="http://www.w3.org/2000/svg">
<rect width="700" height="310" fill="#ffffff"/>
<text x="350" y="22" font-family="Segoe UI,Arial" font-size="12" font-weight="bold"
      fill="#2B3540" text-anchor="middle">Why the route bends: the visibility graph</text>

<!-- field with a hole -->
<path d="M40,45 L470,45 L470,255 L40,255 Z
         M190,110 L330,105 L345,190 L200,200 Z"
      fill="#e6f0e0" stroke="#4a7c3f" stroke-width="1.6" fill-rule="evenodd"/>
<text x="267" y="185" font-family="Segoe UI,Arial" font-size="10" fill="#6b7580"
      text-anchor="middle">slough</text>

<!-- blocked straight line -->
<line x1="105" y1="150" x2="420" y2="150" stroke="#c0392b" stroke-width="1.8"
      stroke-dasharray="6 4"/>
<text x="262" y="143" font-family="Segoe UI,Arial" font-size="9" fill="#c0392b"
      text-anchor="middle">straight line - rejected</text>

<!-- taut path around the hole -->
<polyline points="105,150 190,110 330,105 420,150" fill="none" stroke="#E8590C"
          stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/>

<!-- turn vertices -->
<circle cx="190" cy="110" r="4.5" fill="#ffffff" stroke="#E8590C" stroke-width="2.2"/>
<circle cx="330" cy="105" r="4.5" fill="#ffffff" stroke="#E8590C" stroke-width="2.2"/>

<!-- waypoints -->
<circle cx="105" cy="150" r="5.5" fill="#2b6cb0" stroke="#ffffff" stroke-width="1.6"/>
<circle cx="420" cy="150" r="5.5" fill="#2b6cb0" stroke="#ffffff" stroke-width="1.6"/>
<text x="105" y="172" font-family="Segoe UI,Arial" font-size="9" fill="#2B3540"
      text-anchor="middle">A</text>
<text x="420" y="172" font-family="Segoe UI,Arial" font-size="9" fill="#2B3540"
      text-anchor="middle">B</text>

<text x="190" y="98" font-family="Segoe UI,Arial" font-size="8.5" fill="#E8590C"
      text-anchor="middle">turn vertex</text>
<text x="330" y="93" font-family="Segoe UI,Arial" font-size="8.5" fill="#E8590C"
      text-anchor="middle">turn vertex</text>

<!-- explanatory text -->
<text x="510" y="70" font-family="Segoe UI,Arial" font-size="9.5" fill="#2B3540">A taut path can only</text>
<text x="510" y="85" font-family="Segoe UI,Arial" font-size="9.5" fill="#2B3540">bend at a corner that</text>
<text x="510" y="100" font-family="Segoe UI,Arial" font-size="9.5" fill="#2B3540">juts into open space:</text>
<text x="510" y="121" font-family="Segoe UI,Arial" font-size="9.5" fill="#2B3540">- corners of a hole</text>
<text x="510" y="136" font-family="Segoe UI,Arial" font-size="9.5" fill="#2B3540">- concave corners of</text>
<text x="519" y="150" font-family="Segoe UI,Arial" font-size="9.5" fill="#2B3540">the field outline</text>
<text x="510" y="176" font-family="Segoe UI,Arial" font-size="9.5" fill="#6b7580">Convex corners and</text>
<text x="510" y="190" font-family="Segoe UI,Arial" font-size="9.5" fill="#6b7580">mid-edge vertices are</text>
<text x="510" y="204" font-family="Segoe UI,Arial" font-size="9.5" fill="#6b7580">discarded, so a plain</text>
<text x="510" y="218" font-family="Segoe UI,Arial" font-size="9.5" fill="#6b7580">rectangular field adds</text>
<text x="510" y="232" font-family="Segoe UI,Arial" font-size="9.5" fill="#6b7580">nothing to the graph.</text>

<text x="255" y="283" font-family="Segoe UI,Arial" font-size="9" fill="#6b7580"
      text-anchor="middle">The distance Plover uses for A-B is the length of the orange path, not the red one.</text>
</svg>'''


def processing_dialog_figure():
    """Screenshot the real Processing algorithm dialog, if it can be built."""
    path = os.path.join(OUT, "processing-dialog.png")
    try:
        # The Processing plugin ships inside the QGIS install, not on sys.path.
        for base in (os.environ.get("QGIS_PREFIX_PATH", ""),
                     r"C:/Program Files/QGIS 4.0.1/apps/qgis"):
            cand = os.path.join(base, "python", "plugins")
            if os.path.isdir(cand) and cand not in sys.path:
                sys.path.append(cand)
        from qgis.analysis import QgsNativeAlgorithms  # noqa: F401
        import processing
        from processing.core.Processing import Processing
        from processing.gui.AlgorithmDialog import AlgorithmDialog
        from tsp_route_generator.processing_provider import (
            PloverProcessingProvider,
            PloverRouteAlgorithm,
        )

        Processing.initialize()
        reg = QgsApplication.processingRegistry()
        if reg.providerById("plover") is None:
            provider = PloverProcessingProvider()
            reg.addProvider(provider)
            processing_dialog_figure._provider = provider  # keep alive

        alg = reg.algorithmById("plover:tsproute") or PloverRouteAlgorithm()
        alg = alg.create()
        dlg = AlgorithmDialog(alg)
        dlg.resize(720, 660)
        dlg.grab().save(path, "PNG")
        print("  wrote", os.path.relpath(path, REPO))
    except Exception as exc:  # noqa: BLE001
        print(f"  SKIPPED processing-dialog.png ({type(exc).__name__}: {exc})")


def main():
    print("Generating figures into docs/images ...")

    boundary = field_geom(True)
    b_layer = make_boundary_layer(boundary)
    p_layer = make_point_layer(SAMPLE_POINTS)

    # 1. inputs only
    render([p_layer, b_layer], os.path.join(OUT, "map-inputs.png"))

    # 2. full result (round trip, boundary aware)
    route, order, res = routed_layers(SAMPLE_POINTS, boundary, closed=True)
    render([order, route, b_layer], os.path.join(OUT, "map-route.png"))
    print(f"    round trip: {len(res.order)} stops, {res.total_length:.0f} m")

    # 3. zoom on the numbered badges
    ext = QgsRectangle(30, 30, 700, 470)
    render([order, route, b_layer], os.path.join(OUT, "order-layer-zoom.png"),
           size=(1400, 900), extent=ext, margin=0.02)

    # 4. no boundary (straight-line TSP) — same points, no constraint
    nb_route, nb_order, nb_res = routed_layers(SAMPLE_POINTS, None, closed=True)
    render([nb_order, nb_route, b_layer], os.path.join(OUT, "map-noboundary.png"))
    print(f"    no boundary: {nb_res.total_length:.0f} m")

    # 5. comparison: the unconstrained route (which cuts through the slough)
    #    against the boundary-aware one. Restyle the unconstrained route so the
    #    two are told apart at a glance.
    from qgis.core import QgsLineSymbol
    nb_route.renderer().setSymbol(QgsLineSymbol.createSimple({
        "line_color": "#c0392b", "line_width": "0.6", "line_style": "dash"}))
    nb_route.triggerRepaint()
    render([route, nb_route, b_layer], os.path.join(OUT, "map-compare.png"))
    print(f"    compare: boundary-aware {res.total_length:.0f} m vs "
          f"unconstrained {nb_res.total_length:.0f} m")

    # 6. one-way route
    ow_route, ow_order, ow_res = routed_layers(SAMPLE_POINTS, boundary, closed=False)
    render([ow_order, ow_route, b_layer], os.path.join(OUT, "map-oneway.png"))
    print(f"    one-way: {ow_res.total_length:.0f} m")

    # 7. skip mode: points spanning two fields, boundary on the west field only
    far = [(1600, 120), (1850, 300), (1700, 520), (1950, 150)]
    all_pts = SAMPLE_POINTS + far
    east = make_boundary_layer(
        QgsGeometry.fromPolygonXY([rect(1500, 40, 2050, 590)]), "Neighbouring field")
    east.renderer().setSymbol(QgsFillSymbol.createSimple({
        "color": "245,245,245,255", "outline_color": "#b0b0b0",
        "outline_width": "0.5", "outline_style": "dash",
    }))
    all_layer = make_point_layer(all_pts, "All sample points")
    sk_route, sk_order, _ = routed_layers(SAMPLE_POINTS, boundary, closed=True)
    render([sk_order, sk_route, all_layer, b_layer, east],
           os.path.join(OUT, "map-skip.png"), size=(1700, 760))

    # 8. dialog screenshots (real widgets, real layers in the combo boxes)
    from qgis.core import QgsProject
    QgsProject.instance().addMapLayers([p_layer, b_layer])
    dlg = TSPRouteGeneratorDialog(None, None)
    dlg.resize(468, 396)
    dlg.setWindowTitle("Plover \u2014 TSP Route")
    plain = os.path.join(OUT, "dialog-plain.png")
    dlg.grab().save(plain, "PNG")
    print("  wrote", os.path.relpath(plain, REPO))

    # Annotated version. Row positions are read from the real widgets, so the
    # badges stay aligned even if the layout changes.
    scale = dlg.grab().width() / float(dlg.width())
    rows = []
    for num, widget in enumerate([
        dlg.poi_combo, dlg.selected_only, dlg.boundary_combo, dlg.start_picker,
        dlg.buffer_spin, dlg.outside_mode, dlg.round_trip,
        dlg.make_order_layer, dlg.distance_output,
    ], start=1):
        centre = widget.mapTo(dlg, widget.rect().center())
        rows.append((num, centre.y()))
    annotate(plain, os.path.join(OUT, "dialog-annotated.png"), rows, scale)

    # 9. concept diagrams
    svg_to_png(WORKFLOW_SVG, os.path.join(OUT, "workflow-diagram.png"), 1500, 470)
    svg_to_png(VISIBILITY_SVG, os.path.join(OUT, "visibility-diagram.png"), 1400, 620)

    # 10. the real Processing algorithm dialog
    processing_dialog_figure()

    print("Done.")


if __name__ == "__main__":
    main()
