# -*- coding: utf-8 -*-
"""Route computation pipeline and its QgsTask wrapper.

``compute_route`` is the single entry point shared by the dialog (via
PloverRouteTask, off the UI thread) and the Processing algorithm (which runs
inside Processing's own task). It touches no layers and no widgets — only
geometries and plain data — so it is safe off the main thread.
"""

import traceback

from qgis.core import Qgis, QgsGeometry, QgsTask

from . import tsp_core
from .geometry_utils import (
    build_visibility_adjacency,
    stitch_route,
    useful_boundary_vertices,
)

# QgsTask flags moved namespaces between QGIS 3 (QgsTask.CanCancel) and
# QGIS 4 / Qt6 (Qgis.TaskFlag.CanCancel).
try:
    _CAN_CANCEL = QgsTask.CanCancel
except AttributeError:
    _CAN_CANCEL = Qgis.TaskFlag.CanCancel


class RouteResult:
    """Plain container for a finished route."""

    def __init__(self, order, route_points, total_length, leg_lengths,
                 node_count, edge_count):
        self.order = order                  # waypoint indices, starting at start
        self.route_points = route_points    # full stitched QgsPointXY sequence
        self.total_length = total_length
        self.leg_lengths = leg_lengths
        self.node_count = node_count        # visibility-graph size (diagnostic)
        self.edge_count = edge_count


def compute_route(points, boundary_geom, buffer_dist, start_index,
                  closed=True, set_progress=None, should_cancel=None):
    """Run the full pipeline: graph -> matrix -> order -> stitched route.

    points: list[QgsPointXY] already validated to lie inside the buffered
    boundary and already in the boundary CRS. Raises tsp_core.RoutingError for
    user-actionable problems and tsp_core.TSPCancelled on cancellation.
    """
    progress = set_progress or (lambda value: None)

    # A zero buffer would reject segments that run exactly along the boundary
    # edge (GEOS 'contains' excludes the boundary itself), so always allow a
    # whisker of tolerance.
    region = boundary_geom.buffer(max(buffer_dist, 1e-6), 8)

    vertices = useful_boundary_vertices(boundary_geom)
    nodes = list(points) + vertices

    adjacency = build_visibility_adjacency(
        nodes, region,
        progress=lambda f: progress(45.0 * f),
        should_cancel=should_cancel,
    )
    edge_count = sum(len(nbrs) for nbrs in adjacency.values()) // 2

    n_waypoints = len(points)
    dist, paths = tsp_core.waypoint_matrix(
        adjacency, n_waypoints,
        progress=lambda f: progress(45.0 + 25.0 * f),
        should_cancel=should_cancel,
    )

    bad = tsp_core.unreachable_from(dist, start_index)
    if bad:
        shown = ", ".join(str(b + 1) for b in bad[:12])
        more = "…" if len(bad) > 12 else ""
        raise tsp_core.RoutingError(
            f"{len(bad)} point(s) cannot be reached from the start point "
            f"(point number {shown}{more}). They are likely separated by a "
            "hole/exclusion zone or a pinched-off part of the boundary. "
            "Increase the buffer distance or check the boundary geometry."
        )

    order, total = tsp_core.solve_order(
        dist, start_index, closed,
        progress=lambda f: progress(70.0 + 25.0 * f),
        should_cancel=should_cancel,
    )

    route_points, leg_lengths = stitch_route(order, paths, nodes, closed)
    progress(100.0)
    return RouteResult(order, route_points, total, leg_lengths,
                       len(nodes), edge_count)


class PloverRouteTask(QgsTask):
    """Background QgsTask so QGIS stays responsive during long solves.

    On completion ``finished`` (main thread) invokes ``on_done(task)``; the
    outcome is in ``task.result`` (RouteResult), ``task.user_error`` (str, a
    problem the user can fix) or ``task.exception`` (unexpected traceback).
    """

    def __init__(self, points, boundary_geom, buffer_dist, start_index,
                 closed, on_done, description="Plover: computing route"):
        super().__init__(description, _CAN_CANCEL)
        self._points = list(points)
        self._boundary = QgsGeometry(boundary_geom)  # private copy for the worker thread
        self._buffer = buffer_dist
        self._start = start_index
        self._closed = closed
        self._on_done = on_done
        self.result = None
        self.user_error = None
        self.exception = None

    def run(self):
        try:
            self.result = compute_route(
                self._points, self._boundary, self._buffer, self._start,
                self._closed,
                set_progress=self.setProgress,
                should_cancel=self.isCanceled,
            )
            return True
        except tsp_core.TSPCancelled:
            return False
        except tsp_core.RoutingError as exc:
            self.user_error = str(exc)
            return False
        except Exception:  # noqa: BLE001 — report, never crash QGIS
            self.exception = traceback.format_exc()
            return False

    def finished(self, ok):  # runs on the main thread
        if self._on_done is not None:
            self._on_done(self)
