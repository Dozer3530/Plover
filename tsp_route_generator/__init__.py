# -*- coding: utf-8 -*-
"""Plover — boundary-aware TSP routing for QGIS.

This package is the QGIS plugin; ``classFactory`` is the entry point QGIS
calls when loading it. The folder name ``tsp_route_generator`` is the plugin's
on-disk identity and must not change, or existing installs would be orphaned.
"""


def classFactory(iface):
    """Load the plugin class.

    :param iface: A QGIS interface instance (QgisInterface).
    """
    from .tsp_route_generator import TSPRouteGenerator
    return TSPRouteGenerator(iface)
