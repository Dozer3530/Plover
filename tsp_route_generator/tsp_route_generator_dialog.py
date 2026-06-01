# -*- coding: utf-8 -*-
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton, QHBoxLayout, QTextEdit, QProgressBar, QFileDialog, QSlider, QMessageBox
from qgis.PyQt.QtCore import Qt
from qgis.core import (
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    Qgis,
    QgsMessageLog,
    QgsWkbTypes,
    QgsVectorFileWriter,
    QgsCoordinateTransformContext,
)
import math
from heapq import heappush, heappop
import os

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'tsp_route_generator_dialog_base.ui'))

class TSPRouteGeneratorDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, iface=None, parent=None):
        """Initialize the dialog with an optional QgisInterface for canvas access."""
        super(TSPRouteGeneratorDialog, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.canvas = iface.mapCanvas() if iface else None

        # Hide default button box
        try:
            self.button_box.setVisible(False)
        except AttributeError:
            pass

        # Set up layout manually
        layout = QVBoxLayout()
        
        # Point Layer Dropdown
        poi_layout = QHBoxLayout()
        poi_layout.addWidget(QLabel("Poi:"))
        self.poi_combo = QComboBox()
        poi_layout.addWidget(self.poi_combo)
        layout.addLayout(poi_layout)

        # Boundary Layer Dropdown
        boundary_layout = QHBoxLayout()
        boundary_layout.addWidget(QLabel("Boundary:"))
        self.boundary_combo = QComboBox()
        boundary_layout.addWidget(self.boundary_combo)
        layout.addLayout(boundary_layout)

        # Buffer Distance Input with Slider
        buffer_layout = QHBoxLayout()
        buffer_layout.addWidget(QLabel("Buffer Distance:"))
        self.buffer_input = QLineEdit("0.1")
        self.buffer_input.setMaximumWidth(60)
        self.buffer_input.textChanged.connect(self.update_slider_from_input)
        buffer_layout.addWidget(self.buffer_input)

        self.buffer_slider = QSlider(Qt.Orientation.Horizontal)
        self.buffer_slider.setRange(0, 1000)
        self.buffer_slider.setValue(100)
        self.buffer_slider.setTickInterval(100)
        self.buffer_slider.valueChanged.connect(self.update_input_from_slider)
        buffer_layout.addWidget(self.buffer_slider)
        layout.addLayout(buffer_layout)

        # Start Point Index Input
        start_layout = QHBoxLayout()
        start_layout.addWidget(QLabel("Start Point Index:"))
        self.start_input = QLineEdit("0")
        start_layout.addWidget(self.start_input)
        layout.addLayout(start_layout)

        # Analysis Output
        analysis_layout = QHBoxLayout()
        analysis_layout.addWidget(QLabel("Total Distance:"))
        self.distance_output = QTextEdit()
        self.distance_output.setReadOnly(True)
        self.distance_output.setFixedHeight(30)
        analysis_layout.addWidget(self.distance_output)
        layout.addLayout(analysis_layout)

        # Progress Bar
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("Progress:"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        progress_layout.addWidget(self.progress_bar)
        layout.addLayout(progress_layout)

        # Run Button
        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self.run_tsp)
        layout.addWidget(self.run_button)

        # Save Route Button
        self.save_button = QPushButton("Save Route")
        self.save_button.clicked.connect(self.save_route)
        self.save_button.setEnabled(False)
        layout.addWidget(self.save_button)

        self.setLayout(layout)

        # Populate layer dropdowns
        self.populate_layers()
        self.route_layer = None

    def populate_layers(self):
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if isinstance(layer, QgsVectorLayer):
                if layer.geometryType() == QgsWkbTypes.PointGeometry:
                    self.poi_combo.addItem(layer.name(), layer)
                elif layer.geometryType() == QgsWkbTypes.PolygonGeometry:
                    self.boundary_combo.addItem(layer.name(), layer)

    def calculate_distance(self, point1, point2):
        return math.sqrt((point2.x() - point1.x()) ** 2 + (point2.y() - point1.y()) ** 2)

    def line_intersects_boundary(self, point1, point2, boundary_geom):
        """Return True if the segment is NOT entirely inside the polygon-with-holes.

        A segment is valid (returns False) only when it stays within the polygon
        AND does not pass through any interior ring (hole / slough). Edge-following
        segments are allowed.
        """
        line = QgsGeometry.fromPolylineXY([point1, point2])
        # A segment is fully inside the polygon-with-holes iff subtracting the
        # polygon from the line leaves nothing. This naturally rejects segments
        # that cross holes, since holes are not part of the polygon's interior.
        outside = line.difference(boundary_geom)
        if outside is None or outside.isEmpty():
            return False
        # Allow vanishingly small slivers from floating-point noise.
        return outside.length() > 1e-9

    def get_boundary_vertices(self, boundary_geom):
        vertices = []
        if boundary_geom.isMultipart():
            polygons = boundary_geom.asMultiPolygon()
            if polygons:
                for polygon in polygons:
                    for ring in polygon:
                        vertices.extend([QgsPointXY(v) for v in ring[:-1]])
        else:
            polygon = boundary_geom.asPolygon()
            if polygon:
                for ring in polygon:
                    vertices.extend([QgsPointXY(v) for v in ring[:-1]])
        return vertices

    def build_visibility_graph(self, points, boundary_vertices, boundary_geom, buffered_boundary):
        all_nodes = points + boundary_vertices
        n = len(all_nodes)
        graph = {i: {} for i in range(n)}
        total_edges = (n * (n - 1)) // 2
        edges_processed = 0
        for i in range(n):
            for j in range(i + 1, n):
                line = QgsGeometry.fromPolylineXY([all_nodes[i], all_nodes[j]])
                if not self.line_intersects_boundary(all_nodes[i], all_nodes[j], boundary_geom) and line.within(buffered_boundary):
                    distance = self.calculate_distance(all_nodes[i], all_nodes[j])
                    graph[i][j] = distance
                    graph[j][i] = distance
                edges_processed += 1
                progress = min(int((edges_processed / total_edges) * 30), 30) if total_edges > 0 else 0
                self.progress_bar.setValue(progress)
        return graph, all_nodes

    def dijkstra(self, graph, start, end, n):
        distances = {i: float('inf') for i in range(n)}
        distances[start] = 0
        previous = {i: None for i in range(n)}
        pq = [(0, start)]
        visited = set()
        while pq:
            current_distance, current = heappop(pq)
            if current in visited:
                continue
            visited.add(current)
            if current == end:
                break
            for neighbor, weight in graph[current].items():
                if neighbor in visited:
                    continue
                distance = current_distance + weight
                if distance < distances[neighbor]:
                    distances[neighbor] = distance
                    previous[neighbor] = current
                    heappush(pq, (distance, neighbor))
        path = []
        current = end
        while current is not None:
            path.append(current)
            current = previous[current]
        return path[::-1] if path[-1] == start else []

    def find_tsp_route(self, points, boundary_vertices, boundary_geom, buffered_boundary, start_point_index):
        """Build a waypoint-only TSP order plus cached shortest paths between waypoints.

        Returns:
            waypoint_order: list of waypoint indices (into `points`), forming the tour
            paths: dict {(i, j): [node_indices]} giving the visibility-graph shortest
                   path between every pair of waypoints i and j. Used later to expand
                   the optimized tour into final geometry.
            all_nodes: list of QgsPointXY (waypoints first, then boundary vertices)
        """
        graph, all_nodes = self.build_visibility_graph(points, boundary_vertices, boundary_geom, buffered_boundary)
        n_points = len(points)

        # Step 1: compute shortest path and distance between every pair of waypoints.
        # The distance matrix is what nearest-neighbour + 2-opt will operate on.
        # The paths are cached so we can stitch them back together at the end.
        dist = [[float('inf')] * n_points for _ in range(n_points)]
        paths = {}
        for i in range(n_points):
            dist[i][i] = 0.0
            for j in range(i + 1, n_points):
                path = self.dijkstra(graph, i, j, len(all_nodes))
                if path:
                    d = sum(self.calculate_distance(all_nodes[path[k]], all_nodes[path[k + 1]])
                            for k in range(len(path) - 1))
                    dist[i][j] = d
                    dist[j][i] = d
                    paths[(i, j)] = path
                    paths[(j, i)] = path[::-1]

        # Step 2: nearest-neighbour TSP on the waypoint distance matrix.
        start = start_point_index
        waypoint_order = [start]
        unvisited = set(range(n_points)) - {start}
        current = start
        total_steps = len(unvisited) if unvisited else 1
        step = 0
        while unvisited:
            nearest = None
            nearest_d = float('inf')
            for candidate in unvisited:
                if dist[current][candidate] < nearest_d:
                    nearest_d = dist[current][candidate]
                    nearest = candidate
            if nearest is None:
                # No reachable waypoint remaining (visibility graph disconnected)
                break
            waypoint_order.append(nearest)
            unvisited.remove(nearest)
            current = nearest
            step += 1
            progress = 30 + min(int((step / total_steps) * 40), 40)
            self.progress_bar.setValue(progress)

        # Close the tour
        waypoint_order.append(start)

        return waypoint_order, paths, dist, all_nodes

    def two_opt_optimize(self, waypoint_order, dist):
        """Classic 2-opt on the waypoint distance matrix.

        Operates on the closed tour (start...start). Because `dist[i][j]` is the
        Dijkstra shortest-path cost through the visibility graph, every reachable
        pair already routes around obstacles. No per-swap validation is required:
        any swap that reduces total cost is geometrically valid.
        """
        best = waypoint_order[:]
        n = len(best)
        if n < 4:  # nothing to optimize on tours of 3 or fewer edges
            return best

        improved = True
        iterations = 0
        max_iterations = n * (n - 1) // 2
        while improved:
            improved = False
            for i in range(1, n - 2):
                for j in range(i + 1, n - 1):
                    a, b = best[i - 1], best[i]
                    c, d = best[j], best[j + 1]
                    old = dist[a][b] + dist[c][d]
                    new = dist[a][c] + dist[b][d]
                    if new + 1e-9 < old:  # epsilon guards against float-noise infinite loops
                        best[i:j + 1] = best[i:j + 1][::-1]
                        improved = True
                    iterations += 1
                    progress = 70 + min(int((iterations / max_iterations) * 30), 30)
                    self.progress_bar.setValue(progress)
        return best

    def create_route_layer(self, point_layer, waypoint_order, paths, dist, all_nodes, boundary_geom):
        """Expand the optimized waypoint order into full geometry using cached paths."""
        crs = point_layer.crs().authid()
        route_layer = QgsVectorLayer(f"LineString?crs={crs}", "TSP_Route_Boundary", "memory")
        provider = route_layer.dataProvider()
        feature = QgsFeature()

        # Run 2-opt on the closed tour. We pop the trailing start, optimize the
        # interior, then re-append the start.
        closed_tour = waypoint_order  # already ends in start
        optimized_tour = self.two_opt_optimize(closed_tour, dist)

        # Stitch full geometry by concatenating cached Dijkstra paths between
        # each consecutive pair of waypoints. Skip the first node of each leg
        # after the first to avoid duplicates.
        route_points = []
        for k in range(len(optimized_tour) - 1):
            i, j = optimized_tour[k], optimized_tour[k + 1]
            path = paths.get((i, j))
            if path is None:
                # Unreachable pair — fall back to a straight line (shouldn't happen
                # if the visibility graph is connected)
                segment_pts = [all_nodes[i], all_nodes[j]]
                QgsMessageLog.logMessage(
                    f"No cached path between waypoints {i} and {j}; using direct line.",
                    "Plover", Qgis.Warning
                )
            else:
                segment_pts = [all_nodes[idx] for idx in path]
            if k == 0:
                route_points.extend(segment_pts)
            else:
                route_points.extend(segment_pts[1:])

        geometry = QgsGeometry.fromPolylineXY(route_points)
        feature.setGeometry(geometry)
        provider.addFeature(feature)
        self.progress_bar.setValue(100)
        QgsProject.instance().addMapLayer(route_layer)
        self.route_layer = route_layer
        self.save_button.setEnabled(True)
        return route_layer

    def save_route(self):
        if not self.route_layer:
            QgsMessageLog.logMessage("No route layer to save. Please generate a route first.", "Plover", Qgis.Critical)
            return

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Route",
            "",
            "GeoPackage (*.gpkg);;Shapefile (*.shp);;GeoJSON (*.geojson)"
        )
        if not file_path:
            return

        # Infer driver from filter selection, fall back to extension
        if "GeoPackage" in selected_filter:
            driver = "GPKG"
            if not file_path.lower().endswith(".gpkg"):
                file_path += ".gpkg"
        elif "Shapefile" in selected_filter:
            driver = "ESRI Shapefile"
            if not file_path.lower().endswith(".shp"):
                file_path += ".shp"
        elif "GeoJSON" in selected_filter:
            driver = "GeoJSON"
            if not file_path.lower().endswith(".geojson"):
                file_path += ".geojson"
        else:
            # Fallback: infer from extension
            ext = file_path.lower()
            if ext.endswith(".gpkg"):
                driver = "GPKG"
            elif ext.endswith(".shp"):
                driver = "ESRI Shapefile"
            elif ext.endswith(".geojson"):
                driver = "GeoJSON"
            else:
                QgsMessageLog.logMessage("Unsupported file format. Please use .gpkg, .shp, or .geojson.", "Plover", Qgis.Critical)
                return

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = driver
        options.fileEncoding = "UTF-8"
        options.layerName = "TSP_Route"

        # GeoPackage-specific: handle existing file / layer conflicts
        if driver == "GPKG" and os.path.exists(file_path):
            # Check whether the target file already contains a TSP_Route layer
            existing = QgsVectorLayer(f"{file_path}|layername=TSP_Route", "probe", "ogr")
            if existing.isValid():
                choice = QMessageBox.question(
                    self,
                    "Layer already exists",
                    f"A layer named 'TSP_Route' already exists in:\n{file_path}\n\n"
                    "Yes = Overwrite the existing layer\n"
                    "No  = Append as a new layer with a timestamped name\n"
                    "Cancel = Don't save",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                )
                if choice == QMessageBox.Cancel:
                    return
                elif choice == QMessageBox.Yes:
                    options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
                else:  # No → append with timestamp
                    from datetime import datetime
                    options.layerName = "TSP_Route_" + datetime.now().strftime("%Y%m%d_%H%M%S")
                    options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
            else:
                # File exists but no TSP_Route layer — append cleanly
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

        transform_context = QgsProject.instance().transformContext()
        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            self.route_layer,
            file_path,
            transform_context,
            options
        )

        # writeAsVectorFormatV3 returns (error_code, error_message[, new_file, new_layer])
        error_code = result[0]
        error_message = result[1] if len(result) > 1 else ""

        if error_code != QgsVectorFileWriter.NoError:
            QgsMessageLog.logMessage(
                f"Failed to save route: {error_message} (code {error_code}). Check file permissions or format compatibility.",
                "Plover",
                Qgis.Critical
            )
        else:
            QgsMessageLog.logMessage(
                f"Route saved successfully to {file_path} (layer: {options.layerName})",
                "Plover",
                Qgis.Info
            )

    def update_slider_from_input(self):
        try:
            value = float(self.buffer_input.text()) * 1000
            self.buffer_slider.setValue(int(value))
        except ValueError:
            QgsMessageLog.logMessage("Error: Buffer distance must be a valid number. Please enter a numeric value.", "Plover", Qgis.Warning)
            self.buffer_input.setText("0.1")  # Reset to default

    def update_input_from_slider(self):
        value = self.buffer_slider.value() / 1000
        self.buffer_input.setText(f"{value:.3f}")

    def run_tsp(self):
        self.progress_bar.setValue(0)
        poi_layer = self.poi_combo.currentData()
        boundary_layer = self.boundary_combo.currentData()
        if not poi_layer or not boundary_layer:
            QgsMessageLog.logMessage("Error: Please select both a point layer and a boundary layer.", "Plover", Qgis.Critical)
            return

        try:
            buffer_dist = float(self.buffer_input.text())
            start_index = int(self.start_input.text())
        except ValueError as e:
            QgsMessageLog.logMessage(f"Error: Invalid input - Buffer distance must be a number, and Start index must be an integer. Details: {str(e)}", "Plover", Qgis.Critical)
            return

        # CRS Validation
        if poi_layer.crs() != boundary_layer.crs():
            QgsMessageLog.logMessage(f"Warning: Layers have different CRS ({poi_layer.crs().authid()} vs {boundary_layer.crs().authid()}). Results may be inaccurate. Consider reprojecting layers to match.", "Plover", Qgis.Warning)
            return

        # Extract points with geometry type validation and MultiPointZ conversion
        points = []
        for feature in poi_layer.getFeatures():
            geom = feature.geometry()
            if geom.type() == QgsWkbTypes.PointGeometry:
                points.append(geom.asPoint())
            elif geom.type() == QgsWkbTypes.MultiPointGeometry:
                multi_points = geom.asMultiPoint()
                if multi_points:
                    # Use the centroid of MultiPointZ as a representative point
                    centroid = QgsGeometry.fromMultiPointXY(multi_points).centroid().asPoint()
                    points.append(centroid)
                    QgsMessageLog.logMessage(f"Converted MultiPointZ feature at index {feature.id()} to centroid ({centroid.x():.6f}, {centroid.y():.6f}).", "Plover", Qgis.Info)
                else:
                    QgsMessageLog.logMessage(f"Warning: Skipping empty MultiPointZ feature at index {feature.id()}.", "Plover", Qgis.Warning)
            else:
                QgsMessageLog.logMessage(f"Warning: Skipping feature with geometry type {geom.typeName()} at index {feature.id()}. Only Point and MultiPoint geometries are supported.", "Plover", Qgis.Warning)
        if not points:
            QgsMessageLog.logMessage("Error: No valid point features found in the point layer. Ensure the layer contains Point or MultiPoint geometries.", "Plover", Qgis.Critical)
            return
        if start_index < 0 or start_index >= len(points):
            QgsMessageLog.logMessage(f"Error: Invalid start_point_index {start_index}. Must be between 0 and {len(points) - 1}.", "Plover", Qgis.Critical)
            return

        boundary_geom = next(boundary_layer.getFeatures(), None)
        if not boundary_geom or not boundary_geom.geometry().isGeosValid():
            QgsMessageLog.logMessage("Error: Boundary geometry is invalid or not found. Run 'Fix Geometries' in QGIS or ensure the boundary layer has valid polygon features.", "Plover", Qgis.Critical)
            return
        boundary_geom = boundary_geom.geometry()

        buffered_boundary = boundary_geom.buffer(buffer_dist, 5)
        invalid_points = []
        for i, point in enumerate(points):
            point_geom = QgsGeometry.fromPointXY(point)
            if not point_geom.within(buffered_boundary):
                distance = point_geom.distance(boundary_geom)
                invalid_points.append((i, point.x(), point.y(), distance))

        if invalid_points:
            QgsMessageLog.logMessage(f"Warning: Points not within or on the boundary (buffered by {buffer_dist} units):", "Plover", Qgis.Warning)
            for idx, x, y, dist in invalid_points:
                QgsMessageLog.logMessage(f"Point {idx}: ({x:.6f}, {y:.6f}), Distance from boundary: {dist:.6f}", "Plover", Qgis.Warning)
            QgsMessageLog.logMessage("Some points are outside the boundary. Adjust buffer distance or check layer data.", "Plover", Qgis.Critical)
            return

        boundary_vertices = self.get_boundary_vertices(boundary_geom)
        try:
            waypoint_order, paths, dist, all_nodes = self.find_tsp_route(
                points, boundary_vertices, boundary_geom, buffered_boundary, start_index
            )
            if not waypoint_order or len(waypoint_order) < 2:
                raise ValueError("Could not find a valid route. Check if points are connected within the boundary.")
        except Exception as e:
            QgsMessageLog.logMessage(f"Error during route calculation: {str(e)}. Ensure all points are within the buffered boundary and the start index is valid.", "Plover", Qgis.Critical)
            return

        try:
            self.create_route_layer(poi_layer, waypoint_order, paths, dist, all_nodes, boundary_geom)
            # Total distance is computed from the optimized tour the route layer
            # actually used. Re-derive it from the layer's geometry to keep this
            # accurate regardless of internal changes.
            if self.route_layer and self.route_layer.featureCount() > 0:
                total_distance = next(self.route_layer.getFeatures()).geometry().length()
            else:
                total_distance = 0.0
            self.distance_output.setText(f"{total_distance:.2f} units")
            QgsMessageLog.logMessage(f"TSP route created. Total distance: {total_distance:.2f}", "Plover", Qgis.Info)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error creating route layer: {str(e)}. Check geometry validity or layer CRS.", "Plover", Qgis.Critical)