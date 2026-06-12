# -*- coding: utf-8 -*-
"""Headless integration tests against the real QGIS API.

Run with a QGIS Python so the qgis module is importable, e.g. on Windows:

    "C:/Program Files/QGIS 4.0.1/bin/python-qgis.bat" -m unittest \
        tsp_route_generator.test.test_qgis_integration -v

Self-skips when QGIS is unavailable so plain-Python test runs still pass.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from qgis.core import QgsApplication  # noqa: F401
    HAVE_QGIS = True
except ImportError:
    HAVE_QGIS = False

_APP = None
if HAVE_QGIS:
    _APP = QgsApplication.instance()
    if _APP is None:
        # GUI-enabled so widget tests can share the same offscreen app.
        _APP = QgsApplication([], True)
        _APP.initQgis()

    from qgis.core import QgsGeometry, QgsPointXY

    from tsp_route_generator.geometry_utils import (
        build_visibility_adjacency,
        collect_boundary_geometry,
        points_outside_region,
        useful_boundary_vertices,
    )
    from tsp_route_generator.route_task import compute_route
    from tsp_route_generator import tsp_core


def rect(x0, y0, x1, y1):
    return [QgsPointXY(x0, y0), QgsPointXY(x1, y0), QgsPointXY(x1, y1),
            QgsPointXY(x0, y1), QgsPointXY(x0, y0)]


def field_with_slough():
    """100 x 60 field with a 20 x 20 slough hole in the middle."""
    return QgsGeometry.fromPolygonXY([
        rect(0, 0, 100, 60),
        rect(40, 20, 60, 40),
    ])


@unittest.skipUnless(HAVE_QGIS, "QGIS not available")
class BoundaryVertexTests(unittest.TestCase):
    def test_convex_field_contributes_no_vertices(self):
        geom = QgsGeometry.fromPolygonXY([rect(0, 0, 100, 60)])
        self.assertEqual(useful_boundary_vertices(geom), [])

    def test_hole_corners_are_kept(self):
        verts = useful_boundary_vertices(field_with_slough())
        coords = sorted((v.x(), v.y()) for v in verts)
        self.assertEqual(coords, [(40.0, 20.0), (40.0, 40.0),
                                  (60.0, 20.0), (60.0, 40.0)])

    def test_concave_field_corner_is_kept(self):
        # L-shaped field: the inner elbow at (50, 30) is the only turn point.
        geom = QgsGeometry.fromPolygonXY([[
            QgsPointXY(0, 0), QgsPointXY(100, 0), QgsPointXY(100, 30),
            QgsPointXY(50, 30), QgsPointXY(50, 60), QgsPointXY(0, 60),
            QgsPointXY(0, 0),
        ]])
        verts = useful_boundary_vertices(geom)
        self.assertEqual([(v.x(), v.y()) for v in verts], [(50.0, 30.0)])


@unittest.skipUnless(HAVE_QGIS, "QGIS not available")
class BoundaryCollectionTests(unittest.TestCase):
    def test_enclosed_feature_becomes_hole(self):
        field = QgsGeometry.fromPolygonXY([rect(0, 0, 100, 60)])
        slough = QgsGeometry.fromPolygonXY([rect(40, 20, 60, 40)])
        region, notes = collect_boundary_geometry([field, slough])
        self.assertAlmostEqual(region.area(), 100 * 60 - 20 * 20)
        self.assertTrue(any("exclusion" in n for n in notes))

    def test_disjoint_features_are_unioned(self):
        a = QgsGeometry.fromPolygonXY([rect(0, 0, 10, 10)])
        b = QgsGeometry.fromPolygonXY([rect(20, 0, 30, 10)])
        region, _ = collect_boundary_geometry([a, b])
        self.assertAlmostEqual(region.area(), 200.0)

    def test_outside_points_flagged(self):
        region = QgsGeometry.fromPolygonXY([rect(0, 0, 10, 10)])
        pts = [QgsPointXY(5, 5), QgsPointXY(15, 5), QgsPointXY(10, 5)]
        # On-edge point (10, 5) counts as inside.
        self.assertEqual(points_outside_region(pts, region), [1])


@unittest.skipUnless(HAVE_QGIS, "QGIS not available")
class VisibilityGraphTests(unittest.TestCase):
    def test_edge_blocked_by_hole(self):
        region = field_with_slough().buffer(0.5, 8)
        nodes = [QgsPointXY(20, 30), QgsPointXY(80, 30)]  # hole between them
        adjacency = build_visibility_adjacency(nodes, region)
        self.assertNotIn(1, adjacency[0])

    def test_clear_edge_allowed(self):
        region = field_with_slough().buffer(0.5, 8)
        nodes = [QgsPointXY(20, 10), QgsPointXY(80, 10)]  # south of the hole
        adjacency = build_visibility_adjacency(nodes, region)
        self.assertIn(1, adjacency[0])
        self.assertAlmostEqual(adjacency[0][1], 60.0)

    def test_edge_hugging_boundary_allowed_with_buffer(self):
        # Points exactly on the field edge: only the buffer makes their
        # connecting segment routable. This was the v2.x unreachability bug.
        region = QgsGeometry.fromPolygonXY([rect(0, 0, 100, 60)]).buffer(0.5, 8)
        nodes = [QgsPointXY(10, 0), QgsPointXY(90, 0)]
        adjacency = build_visibility_adjacency(nodes, region)
        self.assertIn(1, adjacency[0])


@unittest.skipUnless(HAVE_QGIS, "QGIS not available")
class ComputeRouteTests(unittest.TestCase):
    POINTS = [
        QgsPointXY(10, 10), QgsPointXY(90, 10), QgsPointXY(90, 50),
        QgsPointXY(10, 50), QgsPointXY(50, 10), QgsPointXY(50, 50),
        QgsPointXY(20, 30), QgsPointXY(80, 30),
    ]

    def test_round_trip_visits_everything_and_avoids_slough(self):
        boundary = field_with_slough()
        result = compute_route(self.POINTS, boundary, 0.5, 0, closed=True)

        self.assertEqual(sorted(result.order), list(range(8)))
        self.assertEqual(result.order[0], 0)
        self.assertEqual(len(result.leg_lengths), 8)  # k legs incl. wrap
        self.assertAlmostEqual(sum(result.leg_lengths), result.total_length,
                               places=6)

        route = QgsGeometry.fromPolylineXY(result.route_points)
        region = boundary.buffer(0.5, 8)
        outside = route.difference(region)
        self.assertLess(outside.length() if not outside.isEmpty() else 0.0, 1e-6)

        # Route must start and end at the start waypoint (closed loop).
        first, last = result.route_points[0], result.route_points[-1]
        self.assertAlmostEqual(first.x(), 10.0)
        self.assertAlmostEqual(first.y(), 10.0)
        self.assertAlmostEqual(last.x(), 10.0)
        self.assertAlmostEqual(last.y(), 10.0)

    def test_open_path_has_k_minus_1_legs(self):
        result = compute_route(self.POINTS, field_with_slough(), 0.5, 3,
                               closed=False)
        self.assertEqual(result.order[0], 3)
        self.assertEqual(len(result.leg_lengths), 7)
        last = result.route_points[-1]
        end_wp = self.POINTS[result.order[-1]]
        self.assertAlmostEqual(last.x(), end_wp.x())
        self.assertAlmostEqual(last.y(), end_wp.y())

    def test_detour_around_hole_is_longer_than_straight_line(self):
        # Two points straddling the slough: route length must exceed the
        # blocked straight line and should match the taut path around a
        # hole corner.
        pts = [QgsPointXY(20, 30), QgsPointXY(80, 30)]
        result = compute_route(pts, field_with_slough(), 0.5, 0, closed=False)
        import math
        expected = (math.hypot(20, 10) + math.hypot(20, 10) + 20)  # via corners
        self.assertGreater(result.total_length, 60.0)
        self.assertLess(abs(result.total_length - expected), 1.0)

    def test_unreachable_point_reported(self):
        # Two separate fields, no connection: point in the far field is
        # unreachable and must raise a RoutingError naming it.
        a = QgsGeometry.fromPolygonXY([rect(0, 0, 10, 10)])
        b = QgsGeometry.fromPolygonXY([rect(100, 0, 110, 10)])
        region, _ = collect_boundary_geometry([a, b])
        pts = [QgsPointXY(5, 5), QgsPointXY(6, 6), QgsPointXY(105, 5)]
        with self.assertRaises(tsp_core.RoutingError):
            compute_route(pts, region, 0.5, 0, closed=True)

    def test_cancellation_propagates(self):
        with self.assertRaises(tsp_core.TSPCancelled):
            compute_route(self.POINTS, field_with_slough(), 0.5, 0,
                          closed=True, should_cancel=lambda: True)


@unittest.skipUnless(HAVE_QGIS, "QGIS not available")
class ProcessingAlgorithmTests(unittest.TestCase):
    def test_algorithm_parameters_construct(self):
        # Exercises every parameter/enum used by the algorithm definition —
        # this is where Qt5/Qt6 API drift would explode.
        from tsp_route_generator.processing_provider import PloverRouteAlgorithm
        alg = PloverRouteAlgorithm()
        alg.initAlgorithm({})
        names = [p.name() for p in alg.parameterDefinitions()]
        self.assertEqual(
            names, ["POINTS", "BOUNDARY", "BUFFER", "START_INDEX",
                    "ROUND_TRIP", "ON_OUTSIDE", "OUTPUT_ROUTE", "OUTPUT_ORDER"])

    def test_provider_constructs(self):
        from tsp_route_generator.processing_provider import PloverProcessingProvider
        provider = PloverProcessingProvider()
        self.assertEqual(provider.id(), "plover")

    def test_full_processing_run(self):
        from qgis.core import (
            QgsFeature,
            QgsProcessingContext,
            QgsProcessingFeedback,
            QgsVectorLayer,
        )
        from tsp_route_generator.processing_provider import PloverRouteAlgorithm

        crs = "EPSG:32612"
        point_layer = QgsVectorLayer(f"Point?crs={crs}", "pts", "memory")
        coords = [(10, 10), (90, 10), (90, 50), (10, 50), (20, 30), (80, 30)]
        features = []
        for x, y in coords:
            f = QgsFeature()
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            features.append(f)
        point_layer.dataProvider().addFeatures(features)

        boundary_layer = QgsVectorLayer(f"Polygon?crs={crs}", "field", "memory")
        bf = QgsFeature()
        bf.setGeometry(field_with_slough())
        boundary_layer.dataProvider().addFeatures([bf])

        alg = PloverRouteAlgorithm()
        alg.initAlgorithm({})
        context = QgsProcessingContext()
        feedback = QgsProcessingFeedback()
        params = {
            "POINTS": point_layer,
            "BOUNDARY": boundary_layer,
            "BUFFER": 0.5,
            "START_INDEX": 0,
            "ROUND_TRIP": True,
            "OUTPUT_ROUTE": "memory:route",
            "OUTPUT_ORDER": "memory:order",
        }
        results, ok = alg.run(params, context, feedback)
        self.assertTrue(ok)

        route = context.takeResultLayer(results["OUTPUT_ROUTE"])
        self.assertIsNotNone(route)
        self.assertEqual(route.featureCount(), 1)
        route_feature = next(route.getFeatures())
        self.assertEqual(route_feature["stops"], 6)
        self.assertGreater(route_feature.geometry().length(), 0.0)
        # Route must dodge the slough hole.
        region = field_with_slough().buffer(0.5, 8)
        outside = route_feature.geometry().difference(region)
        self.assertLess(outside.length() if not outside.isEmpty() else 0.0, 1e-6)

        order = context.takeResultLayer(results["OUTPUT_ORDER"])
        self.assertIsNotNone(order)
        self.assertEqual(order.featureCount(), 6)
        ranks = sorted(f["visit_order"] for f in order.getFeatures())
        self.assertEqual(ranks, [1, 2, 3, 4, 5, 6])

    def test_skip_mode_routes_only_inside_points(self):
        """One point layer spanning two far-apart fields; with ON_OUTSIDE=skip
        and a boundary on the first field, only the inside points are routed."""
        from qgis.core import (
            QgsFeature,
            QgsProcessingContext,
            QgsProcessingFeedback,
            QgsProcessingException,
            QgsVectorLayer,
        )
        from tsp_route_generator.processing_provider import PloverRouteAlgorithm

        crs = "EPSG:32612"
        point_layer = QgsVectorLayer(f"Point?crs={crs}", "pts", "memory")
        # Four points inside a 0..100 field, three far away near x=10000.
        inside = [(10, 10), (90, 10), (90, 90), (10, 90)]
        outside = [(10000, 10), (10050, 50), (10010, 90)]
        feats = []
        for x, y in inside + outside:
            f = QgsFeature()
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            feats.append(f)
        point_layer.dataProvider().addFeatures(feats)

        boundary_layer = QgsVectorLayer(f"Polygon?crs={crs}", "field", "memory")
        bf = QgsFeature()
        bf.setGeometry(QgsGeometry.fromPolygonXY([rect(0, 0, 100, 100)]))
        boundary_layer.dataProvider().addFeatures([bf])

        base_params = {
            "POINTS": point_layer,
            "BOUNDARY": boundary_layer,
            "BUFFER": 0.5,
            "START_INDEX": 0,
            "ROUND_TRIP": True,
            "OUTPUT_ROUTE": "memory:route",
            "OUTPUT_ORDER": "memory:order",
        }

        # Default (fail) mode must raise because three points are outside.
        alg_fail = PloverRouteAlgorithm()
        alg_fail.initAlgorithm({})
        with self.assertRaises(QgsProcessingException):
            alg_fail.processAlgorithm(
                dict(base_params, ON_OUTSIDE=0),
                QgsProcessingContext(), QgsProcessingFeedback())

        # Skip mode routes only the four inside points.
        alg_skip = PloverRouteAlgorithm()
        alg_skip.initAlgorithm({})
        context = QgsProcessingContext()
        results, ok = alg_skip.run(
            dict(base_params, ON_OUTSIDE=1), context, QgsProcessingFeedback())
        self.assertTrue(ok)
        route = context.takeResultLayer(results["OUTPUT_ROUTE"])
        route_feature = next(route.getFeatures())
        self.assertEqual(route_feature["stops"], 4)
        order = context.takeResultLayer(results["OUTPUT_ORDER"])
        self.assertEqual(order.featureCount(), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
