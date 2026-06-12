# -*- coding: utf-8 -*-
"""Offscreen smoke tests for the dialog: construct it, feed it a synthetic
route result, and check the output layers it builds. Needs a QGIS Python:

    "C:/Program Files/QGIS 4.0.1/bin/python-qgis.bat" -m unittest \
        tsp_route_generator.test.test_dialog_smoke -v
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from qgis.core import QgsApplication
    HAVE_QGIS = True
except ImportError:
    HAVE_QGIS = False

_APP = None
if HAVE_QGIS:
    _APP = QgsApplication.instance()
    if _APP is None:
        _APP = QgsApplication([], True)
        _APP.initQgis()

    from qgis.core import QgsPointXY, QgsProject

    from tsp_route_generator.route_task import RouteResult
    from tsp_route_generator.tsp_route_generator_dialog import (
        TSPRouteGeneratorDialog,
    )


@unittest.skipUnless(HAVE_QGIS, "QGIS not available")
class DialogSmokeTests(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().removeAllMapLayers()
        self.dialog = TSPRouteGeneratorDialog(None)

    def tearDown(self):
        self.dialog.close()
        self.dialog = None
        QgsProject.instance().removeAllMapLayers()

    def test_constructs_with_expected_defaults(self):
        d = self.dialog
        self.assertFalse(d.save_button.isEnabled())
        self.assertTrue(d.run_button.isEnabled())
        self.assertFalse(d.cancel_button.isEnabled())
        self.assertTrue(d.round_trip.isChecked())
        self.assertGreaterEqual(d.buffer_spin.value(), 0.0)

    def test_run_without_layers_reports_error(self):
        # Boundary is optional, but a point layer is still required.
        self.dialog.run_tsp()
        self.assertIn("point layer", self.dialog.status_label.text())

    def test_output_layers_built_from_result(self):
        points = [QgsPointXY(0, 0), QgsPointXY(100, 0), QgsPointXY(100, 50)]
        order = [0, 1, 2]
        route_points = points + [points[0]]  # closed triangle
        legs = [100.0, 50.0, 111.8]
        result = RouteResult(order, route_points, sum(legs), legs,
                             node_count=3, edge_count=3)
        meta = {
            "poi_layer": None,
            "crs_authid": "EPSG:32612",
            "fids": [11, 22, 33],
            "points": points,
            "closed": True,
        }
        self.dialog.make_order_layer.setChecked(True)
        self.dialog._build_output_layers(result, meta)

        route_layer = self.dialog.route_layer
        self.assertIsNotNone(route_layer)
        self.assertTrue(route_layer.isValid())
        self.assertEqual(route_layer.featureCount(), 1)
        feature = next(route_layer.getFeatures())
        self.assertAlmostEqual(feature.geometry().length(), 261.8, places=1)
        self.assertEqual(feature["stops"], 3)
        self.assertEqual(feature["round_trip"], "yes")

        order_layer = self.dialog.order_layer
        self.assertIsNotNone(order_layer)
        self.assertEqual(order_layer.featureCount(), 3)
        ranks = sorted(f["visit_order"] for f in order_layer.getFeatures())
        self.assertEqual(ranks, [1, 2, 3])
        fids = [f["source_fid"] for f in order_layer.getFeatures()]
        self.assertEqual(sorted(fids), [11, 22, 33])
        # Visit-order layer is styled: numbered labels enabled on the field.
        self.assertTrue(order_layer.labelsEnabled())
        self.assertEqual(order_layer.labeling().settings().fieldName, "visit_order")

        names = {layer.name() for layer in
                 QgsProject.instance().mapLayers().values()}
        self.assertIn("Plover route", names)
        self.assertIn("Plover visit order", names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
