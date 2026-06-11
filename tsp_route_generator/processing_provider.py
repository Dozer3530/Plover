# -*- coding: utf-8 -*-
"""Processing provider so Plover can run from the Processing Toolbox,
the Model Designer, and batch mode."""

import os

from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    Qgis,
    QgsCoordinateTransform,
    QgsFeature,
    QgsFeatureSink,
    QgsGeometry,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDistance,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsProcessingProvider,
    QgsVectorLayer,
    QgsWkbTypes,
)

from . import tsp_core
from .geometry_utils import collect_boundary_geometry, points_outside_region
from .route_task import compute_route

# Source-type enums moved between QGIS 3 and QGIS 4.
try:
    _TYPE_POINT = QgsProcessing.TypeVectorPoint
    _TYPE_POLYGON = QgsProcessing.TypeVectorPolygon
    _TYPE_LINE = QgsProcessing.TypeVectorLine
except AttributeError:
    _TYPE_POINT = Qgis.ProcessingSourceType.VectorPoint
    _TYPE_POLYGON = Qgis.ProcessingSourceType.VectorPolygon
    _TYPE_LINE = Qgis.ProcessingSourceType.VectorLine

try:
    _NUM_INTEGER = QgsProcessingParameterNumber.Integer
except AttributeError:
    _NUM_INTEGER = Qgis.ProcessingNumberParameterType.Integer

try:
    _WKB_LINESTRING = Qgis.WkbType.LineString
    _WKB_POINT = Qgis.WkbType.Point
except AttributeError:
    _WKB_LINESTRING = QgsWkbTypes.LineString
    _WKB_POINT = QgsWkbTypes.Point


def _fields_from_uri(uri):
    """Build a QgsFields via a scratch memory layer URI — sidesteps the
    QgsField/QVariant constructor differences between Qt5 and Qt6."""
    return QgsVectorLayer(uri, "fields_template", "memory").fields()


class PloverRouteAlgorithm(QgsProcessingAlgorithm):
    POINTS = "POINTS"
    BOUNDARY = "BOUNDARY"
    BUFFER = "BUFFER"
    START_INDEX = "START_INDEX"
    ROUND_TRIP = "ROUND_TRIP"
    OUTPUT_ROUTE = "OUTPUT_ROUTE"
    OUTPUT_ORDER = "OUTPUT_ORDER"

    def name(self):
        return "tsproute"

    def displayName(self):
        return "Boundary-aware TSP route"

    def shortHelpString(self):
        return (
            "Computes the shortest tour visiting every input point while "
            "staying inside the boundary polygon and routing around its "
            "holes (exclusion zones).\n\n"
            "The boundary buffer lets the route pass slightly outside the "
            "strict boundary (and into exclusion zones) — useful when points "
            "sit exactly on the field edge.\n\n"
            "Outputs the route line plus an optional point layer numbered in "
            "visiting order. Layers must use a projected CRS."
        )

    def createInstance(self):
        return PloverRouteAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.POINTS, "Points to visit", [_TYPE_POINT]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.BOUNDARY, "Boundary polygon(s)", [_TYPE_POLYGON]))
        self.addParameter(QgsProcessingParameterDistance(
            self.BUFFER, "Boundary buffer", defaultValue=0.5,
            parentParameterName=self.BOUNDARY, minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.START_INDEX, "Start point index (order of the input layer)",
            _NUM_INTEGER, defaultValue=0, minValue=0))
        self.addParameter(QgsProcessingParameterBoolean(
            self.ROUND_TRIP, "Return to start (round trip)", defaultValue=True))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT_ROUTE, "Route", _TYPE_LINE))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT_ORDER, "Visit order", _TYPE_POINT, optional=True,
            createByDefault=True))

    def processAlgorithm(self, parameters, context, feedback):
        point_source = self.parameterAsSource(parameters, self.POINTS, context)
        boundary_source = self.parameterAsSource(parameters, self.BOUNDARY, context)
        buffer_dist = self.parameterAsDouble(parameters, self.BUFFER, context)
        start_index = self.parameterAsInt(parameters, self.START_INDEX, context)
        closed = self.parameterAsBoolean(parameters, self.ROUND_TRIP, context)

        boundary_crs = boundary_source.sourceCrs()
        if boundary_crs.isGeographic():
            raise QgsProcessingException(
                "The boundary layer uses a geographic CRS (degrees); "
                "reproject to a projected CRS (e.g. UTM) first.")

        geoms = [f.geometry() for f in boundary_source.getFeatures() if f.hasGeometry()]
        boundary_geom, notes = collect_boundary_geometry(geoms)
        for note in notes:
            feedback.pushInfo(note)
        if boundary_geom is None:
            raise QgsProcessingException("Boundary layer contains no usable polygons.")

        transform = None
        if point_source.sourceCrs() != boundary_crs:
            transform = QgsCoordinateTransform(
                point_source.sourceCrs(), boundary_crs, context.transformContext())

        points, fids = [], []
        for feature in point_source.getFeatures():
            geom = feature.geometry()
            if geom is None or geom.isEmpty() or geom.type() != QgsWkbTypes.PointGeometry:
                continue
            point = geom.centroid().asPoint() if geom.isMultipart() else geom.asPoint()
            if transform is not None:
                point = transform.transform(point)
            points.append(QgsPointXY(point))
            fids.append(feature.id())

        if len(points) < 2:
            raise QgsProcessingException("Need at least two point features.")
        if not 0 <= start_index < len(points):
            raise QgsProcessingException(
                f"Start point index must be between 0 and {len(points) - 1}.")

        region = boundary_geom.buffer(max(buffer_dist, 1e-6), 8)
        outside = points_outside_region(points, region)
        if outside:
            shown = ", ".join(str(fids[i]) for i in outside[:12])
            raise QgsProcessingException(
                f"{len(outside)} point(s) are outside the buffered boundary "
                f"(feature ids: {shown}{'…' if len(outside) > 12 else ''}). "
                "Increase the buffer or fix the data.")

        try:
            result = compute_route(
                points, boundary_geom, buffer_dist, start_index, closed,
                set_progress=feedback.setProgress,
                should_cancel=feedback.isCanceled,
            )
        except tsp_core.RoutingError as exc:
            raise QgsProcessingException(str(exc)) from exc

        route_fields = _fields_from_uri(
            "LineString?field=length:double&field=stops:integer&field=round_trip:string(3)")
        (route_sink, route_id) = self.parameterAsSink(
            parameters, self.OUTPUT_ROUTE, context,
            route_fields, _WKB_LINESTRING, boundary_crs)
        if route_sink is None:
            raise QgsProcessingException(
                self.invalidSinkError(parameters, self.OUTPUT_ROUTE))
        route_feature = QgsFeature(route_fields)
        route_feature.setGeometry(QgsGeometry.fromPolylineXY(result.route_points))
        route_feature.setAttributes([
            float(result.total_length), len(result.order), "yes" if closed else "no"])
        route_sink.addFeature(route_feature, QgsFeatureSink.FastInsert)

        outputs = {self.OUTPUT_ROUTE: route_id}

        order_fields = _fields_from_uri(
            "Point?field=visit_order:integer&field=source_fid:integer&field=leg_length:double")
        (order_sink, order_id) = self.parameterAsSink(
            parameters, self.OUTPUT_ORDER, context,
            order_fields, _WKB_POINT, boundary_crs)
        if order_sink is not None:
            for rank, wp_index in enumerate(result.order):
                f = QgsFeature(order_fields)
                f.setGeometry(QgsGeometry.fromPointXY(points[wp_index]))
                leg = result.leg_lengths[rank] if rank < len(result.leg_lengths) else 0.0
                f.setAttributes([rank + 1, int(fids[wp_index]), float(leg)])
                order_sink.addFeature(f, QgsFeatureSink.FastInsert)
            outputs[self.OUTPUT_ORDER] = order_id

        feedback.pushInfo(
            f"Route: {len(result.order)} stops, {result.total_length:.2f} units "
            f"({'round trip' if closed else 'one-way'}).")
        return outputs


class PloverProcessingProvider(QgsProcessingProvider):
    def id(self):
        return "plover"

    def name(self):
        return "Plover"

    def icon(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        return QIcon(icon_path)

    def loadAlgorithms(self):
        self.addAlgorithm(PloverRouteAlgorithm())
