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
        graph, all_nodes = self.build_visibility_graph(points, boundary_vertices, boundary_geom, buffered_boundary)
        n_points = len(points)
        start = start_point_index
        route = [start]
        unvisited = set(range(n_points)) - {start}
        current = start
        total_steps = len(unvisited) if unvisited else 1
        step = 0
        while unvisited:
            min_distance = float('inf')
            next_node = None
            for candidate in unvisited:
                path = self.dijkstra(graph, current, candidate, len(all_nodes))
                if path:
                    distance = sum(self.calculate_distance(all_nodes[path[i]], all_nodes[path[i + 1]]) 
                                 for i in range(len(path) - 1))
                    if distance < min_distance:
                        min_distance = distance
                        next_node = candidate
                        next_path = path
            if next_node is None:
                break
            route.extend(next_path[1:])
            unvisited.remove(next_node)
            current = next_node
            step += 1
            progress = 30 + min(int((step / total_steps) * 40), 40)
            self.progress_bar.setValue(progress)
        return_path = self.dijkstra(graph, current, start, len(all_nodes))
        if return_path:
            route.extend(return_path[1:])
        unique_route = [route[0]]
        for i in range(1, len(route) - 1):
            if route[i] != route[i - 1] and route[i] not in unique_route:
                unique_route.append(route[i])
        unique_route.append(route[-1])
        return unique_route, all_nodes

    def two_opt_optimize(self, route, all_nodes, boundary_geom):
        best_route = route[:]
        improved = True
        iterations = 0
        max_iterations = len(route) * (len(route) - 1) // 2 if len(route) > 1 else 1
        while improved:
            improved = False
            for i in range(1, len(best_route) - 2):
                for j in range(i + 1, len(best_route)):
                    if j - i == 1:
                        continue
                    new_route = best_route[:i] + best_route[i:j][::-1] + best_route[j:]
                    new_geom = QgsGeometry.fromPolylineXY([all_nodes[point] for point in new_route])
                    if new_geom.within(boundary_geom):
                        new_distance = sum(self.calculate_distance(all_nodes[new_route[k]], all_nodes[new_route[k + 1]]) 
                                         for k in range(len(new_route) - 1))
                        old_distance = sum(self.calculate_distance(all_nodes[best_route[k]], all_nodes[best_route[k + 1]]) 
                                         for k in range(len(best_route) - 1))
                        if new_distance < old_distance:
                            best_route = new_route
                            improved = True
                    iterations += 1
                    progress = 70 + min(int((iterations / max_iterations) * 30), 30)
                    self.progress_bar.setValue(progress)
            if not improved:
                break
        return best_route

    def create_route_layer(self, point_layer, route, all_nodes, boundary_geom):
        crs = point_layer.crs().authid()
        route_layer = QgsVectorLayer(f"LineString?crs={crs}", "TSP_Route_Boundary", "memory")
        provider = route_layer.dataProvider()
        feature = QgsFeature()

        optimized_route = self.two_opt_optimize(route, all_nodes, boundary_geom)
        route_points = [all_nodes[i] for i in optimized_route]
        geometry = QgsGeometry.fromPolylineXY(route_points)

        corrected_points = []
        boundary_vertices = self.get_boundary_vertices(boundary_geom)
        boundary_graph = {i: {} for i in range(len(boundary_vertices))}
        for i in range(len(boundary_vertices)):
            for j in range(i + 1, len(boundary_vertices)):
                line = QgsGeometry.fromPolylineXY([boundary_vertices[i], boundary_vertices[j]])
                if not self.line_intersects_boundary(boundary_vertices[i], boundary_vertices[j], boundary_geom):
                    distance = self.calculate_distance(boundary_vertices[i], boundary_vertices[j])
                    boundary_graph[i][j] = distance
                    boundary_graph[j][i] = distance

        for i in range(len(route_points) - 1):
            seg = QgsGeometry.fromPolylineXY([route_points[i], route_points[i + 1]])
            if seg.intersects(boundary_geom) and not seg.within(boundary_geom):
                try:
                    intersect_geom = seg.intersection(boundary_geom)
                    if intersect_geom.type() == QgsWkbTypes.PointGeometry:
                        intersect_point = intersect_geom.asPoint()
                    elif intersect_geom.type() == QgsWkbTypes.MultiPointGeometry:
                        # Use the first point of MultiPointZ if present, log warning
                        points = intersect_geom.asMultiPoint()
                        if points:
                            intersect_point = points[0]
                            QgsMessageLog.logMessage(f"Warning: MultiPointZ intersection detected at segment {i} to {i+1}. Using first point ({intersect_point.x():.6f}, {intersect_point.y():.6f}). Consider simplifying your point layer.", "TSP Route Generator", Qgis.Warning)
                        else:
                            raise ValueError("MultiPointZ intersection has no valid points.")
                    else:
                        raise ValueError(f"Unsupported intersection geometry type: {intersect_geom.typeName()} at segment {i} to {i+1}")
                    
                    min_dist_start = float('inf')
                    min_dist_end = float('inf')
                    nearest_start_idx = None
                    nearest_end_idx = None
                    for idx, vertex in enumerate(boundary_vertices):
                        vert_geom = QgsGeometry.fromPointXY(vertex)
                        dist_start = vert_geom.distance(QgsGeometry.fromPointXY(route_points[i]))
                        dist_end = vert_geom.distance(QgsGeometry.fromPointXY(route_points[i + 1]))
                        if dist_start < min_dist_start:
                            min_dist_start = dist_start
                            nearest_start_idx = idx
                        if dist_end < min_dist_end:
                            min_dist_end = dist_end
                            nearest_end_idx = idx
                    if nearest_start_idx is not None and nearest_end_idx is not None:
                        path = self.dijkstra(boundary_graph, nearest_start_idx, nearest_end_idx, len(boundary_vertices))
                        if path:
                            corrected_points.extend([route_points[i]] + [boundary_vertices[p] for p in path] + [route_points[i + 1]])
                        else:
                            corrected_points.extend([route_points[i], route_points[i + 1]])
                    else:
                        corrected_points.extend([route_points[i], route_points[i + 1]])
                except Exception as e:
                    QgsMessageLog.logMessage(f"Error processing segment {i} to {i+1}: {str(e)}. Skipping correction for this segment.", "TSP Route Generator", Qgis.Critical)
                    corrected_points.extend([route_points[i], route_points[i + 1]])
            else:
                corrected_points.append(route_points[i])
        corrected_points.append(route_points[-1])
        geometry = QgsGeometry.fromPolylineXY(corrected_points)

        feature.setGeometry(geometry)
        provider.addFeature(feature)
        self.progress_bar.setValue(100)
        QgsProject.instance().addMapLayer(route_layer)
        self.route_layer = route_layer
        self.save_button.setEnabled(True)
        return route_layer

    def save_route(self):
        if not self.route_layer:
            QgsMessageLog.logMessage("No route layer to save. Please generate a route first.", "TSP Route Generator", Qgis.Critical)
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
                QgsMessageLog.logMessage("Unsupported file format. Please use .gpkg, .shp, or .geojson.", "TSP Route Generator", Qgis.Critical)
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
                "TSP Route Generator",
                Qgis.Critical
            )
        else:
            QgsMessageLog.logMessage(
                f"Route saved successfully to {file_path} (layer: {options.layerName})",
                "TSP Route Generator",
                Qgis.Info
            )

    def update_slider_from_input(self):
        try:
            value = float(self.buffer_input.text()) * 1000
            self.buffer_slider.setValue(int(value))
        except ValueError:
            QgsMessageLog.logMessage("Error: Buffer distance must be a valid number. Please enter a numeric value.", "TSP Route Generator", Qgis.Warning)
            self.buffer_input.setText("0.1")  # Reset to default

    def update_input_from_slider(self):
        value = self.buffer_slider.value() / 1000
        self.buffer_input.setText(f"{value:.3f}")

    def run_tsp(self):
        self.progress_bar.setValue(0)
        poi_layer = self.poi_combo.currentData()
        boundary_layer = self.boundary_combo.currentData()
        if not poi_layer or not boundary_layer:
            QgsMessageLog.logMessage("Error: Please select both a point layer and a boundary layer.", "TSP Route Generator", Qgis.Critical)
            return

        try:
            buffer_dist = float(self.buffer_input.text())
            start_index = int(self.start_input.text())
        except ValueError as e:
            QgsMessageLog.logMessage(f"Error: Invalid input - Buffer distance must be a number, and Start index must be an integer. Details: {str(e)}", "TSP Route Generator", Qgis.Critical)
            return

        # CRS Validation
        if poi_layer.crs() != boundary_layer.crs():
            QgsMessageLog.logMessage(f"Warning: Layers have different CRS ({poi_layer.crs().authid()} vs {boundary_layer.crs().authid()}). Results may be inaccurate. Consider reprojecting layers to match.", "TSP Route Generator", Qgis.Warning)
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
                    QgsMessageLog.logMessage(f"Converted MultiPointZ feature at index {feature.id()} to centroid ({centroid.x():.6f}, {centroid.y():.6f}).", "TSP Route Generator", Qgis.Info)
                else:
                    QgsMessageLog.logMessage(f"Warning: Skipping empty MultiPointZ feature at index {feature.id()}.", "TSP Route Generator", Qgis.Warning)
            else:
                QgsMessageLog.logMessage(f"Warning: Skipping feature with geometry type {geom.typeName()} at index {feature.id()}. Only Point and MultiPoint geometries are supported.", "TSP Route Generator", Qgis.Warning)
        if not points:
            QgsMessageLog.logMessage("Error: No valid point features found in the point layer. Ensure the layer contains Point or MultiPoint geometries.", "TSP Route Generator", Qgis.Critical)
            return
        if start_index < 0 or start_index >= len(points):
            QgsMessageLog.logMessage(f"Error: Invalid start_point_index {start_index}. Must be between 0 and {len(points) - 1}.", "TSP Route Generator", Qgis.Critical)
            return

        boundary_geom = next(boundary_layer.getFeatures(), None)
        if not boundary_geom or not boundary_geom.geometry().isGeosValid():
            QgsMessageLog.logMessage("Error: Boundary geometry is invalid or not found. Run 'Fix Geometries' in QGIS or ensure the boundary layer has valid polygon features.", "TSP Route Generator", Qgis.Critical)
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
            QgsMessageLog.logMessage(f"Warning: Points not within or on the boundary (buffered by {buffer_dist} units):", "TSP Route Generator", Qgis.Warning)
            for idx, x, y, dist in invalid_points:
                QgsMessageLog.logMessage(f"Point {idx}: ({x:.6f}, {y:.6f}), Distance from boundary: {dist:.6f}", "TSP Route Generator", Qgis.Warning)
            QgsMessageLog.logMessage("Some points are outside the boundary. Adjust buffer distance or check layer data.", "TSP Route Generator", Qgis.Critical)
            return

        boundary_vertices = self.get_boundary_vertices(boundary_geom)
        try:
            route, all_nodes = self.find_tsp_route(points, boundary_vertices, boundary_geom, buffered_boundary, start_index)
            if not route:
                raise ValueError("Could not find a valid route. Check if points are connected within the boundary.")
        except Exception as e:
            QgsMessageLog.logMessage(f"Error during route calculation: {str(e)}. Ensure all points are within the buffered boundary and the start index is valid.", "TSP Route Generator", Qgis.Critical)
            return

        try:
            self.create_route_layer(poi_layer, route, all_nodes, boundary_geom)
            total_distance = sum(self.calculate_distance(all_nodes[route[i]], all_nodes[route[i + 1]]) 
                               for i in range(len(route) - 1))
            self.distance_output.setText(f"{total_distance:.2f} units")
            QgsMessageLog.logMessage(f"TSP route created. Total distance: {total_distance:.2f}", "TSP Route Generator", Qgis.Info)
        except Exception as e:
            QgsMessageLog.logMessage(f"Error creating route layer: {str(e)}. Check geometry validity or layer CRS.", "TSP Route Generator", Qgis.Critical)