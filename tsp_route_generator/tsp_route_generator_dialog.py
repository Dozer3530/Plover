# -*- coding: utf-8 -*-
"""Plover dialog: gather inputs, launch the background route task, build the
output layers. All heavy lifting lives in route_task / geometry_utils /
tsp_core — this module is UI only."""

import os

from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsGeometry,
    QgsMessageLog,
    QgsPointXY,
    QgsProject,
    QgsSettings,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import QgsFeaturePickerWidget, QgsMapLayerComboBox

from .geometry_utils import collect_boundary_geometry, points_outside_region
from .route_task import PloverRouteTask

LOG_TAG = "Plover"

# Enum homes differ between Qt5/QGIS3 and Qt6/QGIS4; resolve once.
try:
    _POINT_FILTER = Qgis.LayerFilter.PointLayer
    _POLY_FILTER = Qgis.LayerFilter.PolygonLayer
except AttributeError:
    from qgis.core import QgsMapLayerProxyModel
    _POINT_FILTER = QgsMapLayerProxyModel.PointLayer
    _POLY_FILTER = QgsMapLayerProxyModel.PolygonLayer

try:
    _BTN_YES = QMessageBox.StandardButton.Yes
    _BTN_NO = QMessageBox.StandardButton.No
    _BTN_CANCEL = QMessageBox.StandardButton.Cancel
except AttributeError:
    _BTN_YES, _BTN_NO, _BTN_CANCEL = QMessageBox.Yes, QMessageBox.No, QMessageBox.Cancel


def _log(message, level=Qgis.Info):
    QgsMessageLog.logMessage(message, LOG_TAG, level)


class TSPRouteGeneratorDialog(QDialog):
    """Modeless dialog driving the Plover routing pipeline."""

    def __init__(self, iface=None, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.task = None
        self.route_layer = None
        self.order_layer = None

        self.setWindowTitle("Plover — TSP Route")
        self.setMinimumWidth(420)
        self._build_ui()
        self._restore_settings()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.poi_combo = QgsMapLayerComboBox()
        self.poi_combo.setFilters(_POINT_FILTER)
        form.addRow("Points to visit:", self.poi_combo)

        self.selected_only = QCheckBox("Use only selected points")
        form.addRow("", self.selected_only)

        self.boundary_combo = QgsMapLayerComboBox()
        self.boundary_combo.setFilters(_POLY_FILTER)
        self.boundary_combo.setAllowEmptyLayer(True)
        self.boundary_combo.setToolTip(
            "Optional. With a boundary, the route stays inside it and routes\n"
            "around holes (sloughs / exclusion zones). Leave empty for a plain\n"
            "straight-line route through the points (ordinary Euclidean TSP).")
        form.addRow("Boundary layer:", self.boundary_combo)

        self.start_picker = QgsFeaturePickerWidget()
        self.start_picker.setShowBrowserButtons(True)
        form.addRow("Start at point:", self.start_picker)
        self.poi_combo.layerChanged.connect(self.start_picker.setLayer)
        if self.poi_combo.currentLayer():
            self.start_picker.setLayer(self.poi_combo.currentLayer())

        self.buffer_spin = QDoubleSpinBox()
        self.buffer_spin.setDecimals(2)
        self.buffer_spin.setRange(0.0, 1e6)
        self.buffer_spin.setValue(0.5)
        self.buffer_spin.setSuffix(" map units")
        self.buffer_spin.setToolTip(
            "Tolerance around the boundary: the route may pass this far\n"
            "outside the field edge and this far into exclusion zones."
        )
        form.addRow("Boundary buffer:", self.buffer_spin)

        self.outside_mode = QComboBox()
        self.outside_mode.addItem("Fail if any point is outside", "fail")
        self.outside_mode.addItem("Skip points outside the boundary", "skip")
        self.outside_mode.setToolTip(
            "What to do with points that fall outside the buffered boundary.\n"
            "Fail: stop and report them (good when every point should be in-field).\n"
            "Skip: drop them and route only the points inside (good for one big\n"
            "point layer spanning many fields — route just this field's points)."
        )
        form.addRow("Points outside boundary:", self.outside_mode)

        self.round_trip = QCheckBox("Return to start (round trip)")
        self.round_trip.setChecked(True)
        form.addRow("", self.round_trip)

        self.make_order_layer = QCheckBox("Also create a numbered visit-order layer")
        self.make_order_layer.setChecked(True)
        form.addRow("", self.make_order_layer)

        layout.addLayout(form)

        self.distance_output = QLineEdit()
        self.distance_output.setReadOnly(True)
        self.distance_output.setPlaceholderText("Route length will appear here")
        dist_row = QHBoxLayout()
        dist_row.addWidget(QLabel("Total distance:"))
        dist_row.addWidget(self.distance_output)
        layout.addLayout(dist_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        buttons = QHBoxLayout()
        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self.run_tsp)
        buttons.addWidget(self.run_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._cancel_task)
        self.cancel_button.setEnabled(False)
        buttons.addWidget(self.cancel_button)

        self.save_button = QPushButton("Save Route…")
        self.save_button.clicked.connect(self.save_route)
        self.save_button.setEnabled(False)
        buttons.addWidget(self.save_button)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        # Buffer / outside-mode only matter when there is a boundary to respect.
        self.boundary_combo.layerChanged.connect(self._update_boundary_dependent_state)
        self._update_boundary_dependent_state()

    def _update_boundary_dependent_state(self, *args):
        has_boundary = self.boundary_combo.currentLayer() is not None
        self.buffer_spin.setEnabled(has_boundary)
        self.outside_mode.setEnabled(has_boundary)

    def _set_status(self, text, error=False):
        self.status_label.setStyleSheet("color: #c0392b;" if error else "")
        self.status_label.setText(text)

    def _set_running(self, running):
        self.run_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        for w in (self.poi_combo, self.boundary_combo, self.start_picker,
                  self.buffer_spin, self.round_trip, self.selected_only,
                  self.outside_mode, self.make_order_layer):
            w.setEnabled(not running)
        if not running:
            self._update_boundary_dependent_state()

    # ------------------------------------------------------------ settings

    def _restore_settings(self):
        s = QgsSettings()
        self.buffer_spin.setValue(float(s.value("plover/buffer", 0.5)))
        self.round_trip.setChecked(s.value("plover/round_trip", True, type=bool))
        self.make_order_layer.setChecked(s.value("plover/order_layer", True, type=bool))
        mode_index = self.outside_mode.findData(s.value("plover/outside_mode", "fail"))
        if mode_index >= 0:
            self.outside_mode.setCurrentIndex(mode_index)

    def _save_settings(self):
        s = QgsSettings()
        s.setValue("plover/buffer", self.buffer_spin.value())
        s.setValue("plover/round_trip", self.round_trip.isChecked())
        s.setValue("plover/order_layer", self.make_order_layer.isChecked())
        s.setValue("plover/outside_mode", self.outside_mode.currentData())

    # ------------------------------------------------------------- run flow

    def run_tsp(self):
        self.progress_bar.setValue(0)
        self.distance_output.clear()
        self._save_settings()

        poi_layer = self.poi_combo.currentLayer()
        boundary_layer = self.boundary_combo.currentLayer()
        if poi_layer is None:
            self._set_status("Select a point layer.", error=True)
            return

        # The boundary is optional. With one, routing stays inside it and
        # dodges holes; without one, the working CRS is the point layer's and
        # the route is a plain straight-line (Euclidean) TSP.
        working_crs = boundary_layer.crs() if boundary_layer is not None else poi_layer.crs()
        if working_crs.isGeographic():
            which = "boundary" if boundary_layer is not None else "point"
            self._set_status(
                f"The {which} layer uses a geographic CRS (degrees). Distances "
                "would be meaningless — reproject to a projected CRS "
                "(e.g. UTM) first.", error=True)
            return

        # --- boundary geometry (merge all polygon features), if any ---
        boundary_geom = None
        if boundary_layer is not None:
            geoms = [f.geometry() for f in boundary_layer.getFeatures() if f.hasGeometry()]
            boundary_geom, notes = collect_boundary_geometry(geoms)
            for note in notes:
                _log(note, Qgis.Warning)
            if boundary_geom is None:
                self._set_status("The boundary layer contains no usable polygons.", error=True)
                return

        # --- points (optionally selection only), transformed to working CRS ---
        if self.selected_only.isChecked():
            features = list(poi_layer.selectedFeatures())
            if not features:
                self._set_status("'Use only selected points' is on, but no points are selected.", error=True)
                return
        else:
            features = list(poi_layer.getFeatures())

        transform = None
        if poi_layer.crs() != working_crs:
            transform = QgsCoordinateTransform(poi_layer.crs(), working_crs,
                                               QgsProject.instance())
            _log(f"Reprojecting points from {poi_layer.crs().authid()} "
                 f"to {working_crs.authid()} for routing.")

        points, fids = [], []
        for feature in features:
            geom = feature.geometry()
            if geom is None or geom.isEmpty():
                _log(f"Skipping feature {feature.id()}: empty geometry.", Qgis.Warning)
                continue
            if geom.type() != QgsWkbTypes.PointGeometry:
                _log(f"Skipping feature {feature.id()}: not a point.", Qgis.Warning)
                continue
            if geom.isMultipart():
                point = geom.centroid().asPoint()
            else:
                point = geom.asPoint()
            if transform is not None:
                try:
                    point = transform.transform(point)
                except Exception:  # noqa: BLE001
                    _log(f"Skipping feature {feature.id()}: reprojection failed.", Qgis.Warning)
                    continue
            points.append(QgsPointXY(point))
            fids.append(feature.id())

        if len(points) < 2:
            self._set_status("Need at least two point features to build a route.", error=True)
            return

        # --- containment check against the buffered boundary (boundary only) ---
        buffer_dist = self.buffer_spin.value()
        skipped_fids = set()
        outside = points_outside_region(points, boundary_geom.buffer(
            max(buffer_dist, 1e-6), 8)) if boundary_geom is not None else []
        if outside:
            for idx in outside:
                p = points[idx]
                d = QgsGeometry.fromPointXY(p).distance(boundary_geom)
                _log(f"Point fid={fids[idx]} at ({p.x():.2f}, {p.y():.2f}) is "
                     f"{d:.2f} units outside the boundary.", Qgis.Warning)

            if self.outside_mode.currentData() == "skip":
                # Keep only the points inside the boundary; route those.
                outside_set = set(outside)
                skipped_fids = {fids[i] for i in outside}
                points = [p for i, p in enumerate(points) if i not in outside_set]
                fids = [f for i, f in enumerate(fids) if i not in outside_set]
                if len(points) < 2:
                    self._set_status(
                        f"Only {len(points)} point(s) fall inside the boundary — "
                        "need at least two to build a route. Increase the buffer "
                        "or pick a boundary that contains more points.", error=True)
                    return
                _log(f"Skipping {len(outside)} point(s) outside the boundary; "
                     f"routing the {len(points)} inside.")
            else:  # "fail"
                if not self.selected_only.isChecked():
                    poi_layer.selectByIds([fids[i] for i in outside])
                self._set_status(
                    f"{len(outside)} point(s) fall outside the buffered boundary "
                    "(now selected on the layer; details in the log). Increase the "
                    "buffer, switch 'Points outside boundary' to skip, or fix the "
                    "data.", error=True)
                return

        # --- start point (resolved against the final, in-boundary point set) ---
        start_feature = self.start_picker.feature()
        if start_feature is not None and start_feature.isValid() and start_feature.id() in fids:
            start_index = fids.index(start_feature.id())
        else:
            start_index = 0
            if start_feature is not None and start_feature.isValid() and \
                    start_feature.id() in skipped_fids:
                _log("Chosen start point lies outside the boundary and was "
                     "skipped; starting from the first in-boundary point instead.",
                     Qgis.Warning)
            elif self.selected_only.isChecked():
                _log("Chosen start point is not in the selection; starting "
                     "from the first selected point instead.", Qgis.Warning)

        # --- launch background task ---
        self._set_running(True)
        self._set_status(f"Routing {len(points)} points…")
        self._run_meta = {
            "poi_layer": poi_layer,
            "crs_authid": working_crs.authid(),
            "fids": fids,
            "points": points,
            "closed": self.round_trip.isChecked(),
            "skipped": len(skipped_fids),
        }
        task = PloverRouteTask(
            points, boundary_geom, buffer_dist, start_index,
            closed=self.round_trip.isChecked(),
            on_done=self._task_done,
        )
        # Capture the task in the closure: self.task is reset to None when the
        # run finishes, but queued progress signals may still arrive after.
        task.progressChanged.connect(
            lambda: self.progress_bar.setValue(int(task.progress())))
        self.task = task
        QgsApplication.taskManager().addTask(task)

    def _cancel_task(self):
        if self.task is not None:
            self.task.cancel()
            self._set_status("Cancelling…")

    def _task_done(self, task):
        """Runs on the main thread once the task finishes (or fails)."""
        self._set_running(False)
        if task is not self.task:
            return  # stale callback from a superseded run
        self.task = None

        if task.user_error:
            self._set_status(task.user_error, error=True)
            _log(task.user_error, Qgis.Critical)
            return
        if task.exception:
            self._set_status("Routing failed unexpectedly — see the Plover log "
                             "panel for the full traceback.", error=True)
            _log(task.exception, Qgis.Critical)
            return
        if task.result is None:
            self._set_status("Cancelled.")
            self.progress_bar.setValue(0)
            return

        result = task.result
        meta = self._run_meta
        try:
            self._build_output_layers(result, meta)
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Route computed but creating layers failed: {exc}", error=True)
            import traceback
            _log(traceback.format_exc(), Qgis.Critical)
            return

        self.distance_output.setText(f"{result.total_length:,.1f} map units")
        trip = "round trip" if meta["closed"] else "one-way path"
        skipped_note = (f" Skipped {meta['skipped']} point(s) outside the boundary."
                        if meta.get("skipped") else "")
        self._set_status(
            f"Done — {len(result.order)} stops, {result.total_length:,.1f} units "
            f"({trip}).{skipped_note} Visibility graph: {result.node_count} nodes / "
            f"{result.edge_count} edges.")
        _log(f"Route created: {len(result.order)} stops, "
             f"{result.total_length:.2f} units, {trip}.")
        self.save_button.setEnabled(True)

    # ------------------------------------------------------------- outputs

    def _build_output_layers(self, result, meta):
        crs = meta["crs_authid"]
        closed = meta["closed"]

        # Field definitions via the memory-provider URI keeps us off the
        # QgsField/QVariant API, which changed between Qt5 and Qt6.
        route_layer = QgsVectorLayer(
            f"LineString?crs={crs}&field=length:double&field=stops:integer"
            "&field=round_trip:string(3)",
            "Plover route", "memory")
        feature = QgsFeature(route_layer.fields())
        feature.setGeometry(QgsGeometry.fromPolylineXY(result.route_points))
        feature.setAttributes([
            float(result.total_length),
            len(result.order),
            "yes" if closed else "no",
        ])
        route_layer.dataProvider().addFeature(feature)
        route_layer.updateExtents()
        self._style_route_layer(route_layer)
        QgsProject.instance().addMapLayer(route_layer)
        self.route_layer = route_layer

        if self.make_order_layer.isChecked():
            order_layer = QgsVectorLayer(
                f"Point?crs={crs}&field=visit_order:integer&field=source_fid:integer&field=leg_length:double",
                "Plover visit order", "memory")
            provider = order_layer.dataProvider()
            features = []
            for rank, wp_index in enumerate(result.order):
                f = QgsFeature(order_layer.fields())
                f.setGeometry(QgsGeometry.fromPointXY(meta["points"][wp_index]))
                leg = result.leg_lengths[rank] if rank < len(result.leg_lengths) else 0.0
                f.setAttributes([rank + 1, int(meta["fids"][wp_index]), float(leg)])
                features.append(f)
            provider.addFeatures(features)
            order_layer.updateExtents()
            self._label_order_layer(order_layer)
            QgsProject.instance().addMapLayer(order_layer)
            self.order_layer = order_layer

    def _style_route_layer(self, layer):
        """Orange line with direction arrows; best-effort across QGIS versions."""
        try:
            from qgis.core import QgsLineSymbol, QgsMarkerLineSymbolLayer, QgsMarkerSymbol
            symbol = QgsLineSymbol.createSimple({
                "line_color": "#e8590c", "line_width": "0.7"})
            marker_line = QgsMarkerLineSymbolLayer()
            try:  # QGIS >= 3.24 flags API; fall back to the legacy setter
                marker_line.setPlacements(
                    Qgis.MarkerLinePlacements(Qgis.MarkerLinePlacement.SegmentCenter))
            except AttributeError:
                try:
                    marker_line.setPlacement(Qgis.MarkerLinePlacement.SegmentCenter)
                except AttributeError:
                    marker_line.setPlacement(QgsMarkerLineSymbolLayer.CentralPoint)
            arrow = QgsMarkerSymbol.createSimple({
                "name": "filled_arrowhead", "color": "#e8590c", "size": "3"})
            marker_line.setSubSymbol(arrow)
            symbol.appendSymbolLayer(marker_line)
            layer.renderer().setSymbol(symbol)
            layer.triggerRepaint()
        except Exception:  # noqa: BLE001 — styling is cosmetic, never fatal
            _log("Could not apply route symbology on this QGIS version; "
                 "using defaults.", Qgis.Warning)

    def _label_order_layer(self, layer):
        try:
            from qgis.core import QgsPalLayerSettings, QgsVectorLayerSimpleLabeling
            settings = QgsPalLayerSettings()
            settings.fieldName = "visit_order"
            labeling = QgsVectorLayerSimpleLabeling(settings)
            layer.setLabeling(labeling)
            layer.setLabelsEnabled(True)
            layer.triggerRepaint()
        except Exception:  # noqa: BLE001
            _log("Could not enable visit-order labels on this QGIS version.",
                 Qgis.Warning)

    # ---------------------------------------------------------------- save

    def save_route(self):
        if not self.route_layer:
            self._set_status("No route layer to save — generate a route first.", error=True)
            return

        settings = QgsSettings()
        last_dir = settings.value("plover/last_save_dir", "")
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Save Route", last_dir,
            "GeoPackage (*.gpkg);;Shapefile (*.shp);;GeoJSON (*.geojson);;"
            "GPX track (*.gpx);;KML (*.kml)")
        if not file_path:
            return
        settings.setValue("plover/last_save_dir", os.path.dirname(file_path))

        drivers = {
            "GeoPackage": ("GPKG", ".gpkg"),
            "Shapefile": ("ESRI Shapefile", ".shp"),
            "GeoJSON": ("GeoJSON", ".geojson"),
            "GPX": ("GPX", ".gpx"),
            "KML": ("KML", ".kml"),
        }
        driver = None
        for label, (drv, ext) in drivers.items():
            if label in selected_filter:
                driver = drv
                if not file_path.lower().endswith(ext):
                    file_path += ext
                break
        if driver is None:  # infer from typed extension
            for drv, ext in drivers.values():
                if file_path.lower().endswith(ext):
                    driver = drv
                    break
        if driver is None:
            self._set_status("Unsupported file format — use .gpkg, .shp, "
                             ".geojson, .gpx or .kml.", error=True)
            return

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = driver
        options.fileEncoding = "UTF-8"
        options.layerName = "plover_route"

        # GPX and KML are WGS84 formats; reproject on the way out.
        if driver in ("GPX", "KML"):
            options.ct = QgsCoordinateTransform(
                self.route_layer.crs(),
                QgsCoordinateReferenceSystem("EPSG:4326"),
                QgsProject.instance())
            if driver == "GPX":
                options.layerOptions = ["FORCE_GPX_TRACK=YES"]
                # Dataset-level option: without it the GPX schema rejects our
                # attribute fields and the write fails outright.
                options.datasourceOptions = ["GPX_USE_EXTENSIONS=YES"]

        if driver == "GPKG" and os.path.exists(file_path):
            existing = QgsVectorLayer(f"{file_path}|layername=plover_route", "probe", "ogr")
            if existing.isValid():
                choice = QMessageBox.question(
                    self, "Layer already exists",
                    f"A layer named 'plover_route' already exists in:\n{file_path}\n\n"
                    "Yes = overwrite it\nNo = add a timestamped layer\nCancel = don't save",
                    _BTN_YES | _BTN_NO | _BTN_CANCEL)
                if choice == _BTN_CANCEL:
                    return
                if choice == _BTN_NO:
                    from datetime import datetime
                    options.layerName = "plover_route_" + datetime.now().strftime("%Y%m%d_%H%M%S")
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            self.route_layer, file_path,
            QgsProject.instance().transformContext(), options)
        error_code = result[0]
        error_message = result[1] if len(result) > 1 else ""

        if error_code != QgsVectorFileWriter.NoError:
            self._set_status(f"Save failed: {error_message}", error=True)
            _log(f"Save failed: {error_message} (code {error_code})", Qgis.Critical)
        else:
            self._set_status(f"Route saved to {file_path}")
            _log(f"Route saved to {file_path} (layer {options.layerName})")

    # ------------------------------------------------------------- closing

    def closeEvent(self, event):
        if self.task is not None:
            self.task.cancel()
        super().closeEvent(event)
