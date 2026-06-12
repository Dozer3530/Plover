# -*- coding: utf-8 -*-
"""QGIS-dependent geometry helpers for Plover.

Everything here takes/returns QGIS geometry objects but contains no UI code,
so it can run inside a background QgsTask or a Processing algorithm.
"""

import math

from qgis.core import (
    QgsGeometry,
    QgsLineString,
    QgsPoint,
    QgsPointXY,
    QgsWkbTypes,
)

from .tsp_core import TSPCancelled


def collect_boundary_geometry(geometries):
    """Merge polygon features into one routing region.

    Features wholly contained inside another feature are treated as exclusion
    zones and subtracted (people often digitize sloughs as separate polygons
    instead of rings); everything else is unioned. Returns
    (region QgsGeometry, notes list[str]).
    """
    notes = []
    polys = []
    for geom in geometries:
        if geom is None or geom.isEmpty():
            continue
        if geom.type() != QgsWkbTypes.PolygonGeometry:
            continue
        if not geom.isGeosValid():
            fixed = geom.makeValid()
            if fixed is not None and not fixed.isEmpty():
                notes.append("Repaired an invalid boundary polygon with makeValid().")
                geom = fixed
            else:
                notes.append("Skipped an invalid boundary polygon that could not be repaired.")
                continue
        polys.append(QgsGeometry(geom))

    if not polys:
        return None, notes

    polys.sort(key=lambda g: g.area(), reverse=True)
    region = polys[0]
    for geom in polys[1:]:
        if region.contains(geom):
            region = region.difference(geom)
            notes.append("Treated a fully-enclosed boundary feature as an exclusion zone (hole).")
        else:
            region = region.combine(geom)
    return region, notes


def _ring_points(ring):
    """Ring as an open list of QgsPointXY (drop the closing duplicate)."""
    pts = [QgsPointXY(p) for p in ring]
    if len(pts) >= 2 and pts[0].x() == pts[-1].x() and pts[0].y() == pts[-1].y():
        pts.pop()
    return pts


def _ring_orientation(pts):
    """+1 for counter-clockwise rings, -1 for clockwise (shoelace sign)."""
    area2 = 0.0
    n = len(pts)
    for k in range(n):
        a, b = pts[k], pts[(k + 1) % n]
        area2 += a.x() * b.y() - b.x() * a.y()
    return 1 if area2 >= 0 else -1


def _useful_ring_vertices(pts, is_exterior):
    """Vertices of one ring where a taut shortest path can turn.

    Shortest paths in a polygon-with-holes only ever bend at vertices that are
    reflex with respect to the free space: concave corners of the outer ring,
    convex corners of holes. Everything else (convex field corners, straight
    in-line vertices) can never appear on an optimal path, so dropping them
    shrinks the visibility graph without changing any shortest path.
    """
    n = len(pts)
    if n < 3:
        return []
    sign = _ring_orientation(pts)
    keep = []
    for k in range(n):
        u, v, w = pts[k - 1], pts[k], pts[(k + 1) % n]
        ax, ay = v.x() - u.x(), v.y() - u.y()
        bx, by = w.x() - v.x(), w.y() - v.y()
        cross = ax * by - ay * bx
        # Collinear vertices are never turn points; threshold is relative to
        # the edge lengths so it is unit-scale independent.
        if abs(cross) <= 1e-9 * math.hypot(ax, ay) * math.hypot(bx, by):
            continue
        if is_exterior:
            if sign * cross < 0:  # concave corner of the field
                keep.append(v)
        else:
            if sign * cross > 0:  # corner of a hole sticking into the field
                keep.append(v)
    return keep


def useful_boundary_vertices(boundary_geom):
    """Reflex-vertex set of the boundary, deduplicated.

    For a convex field with no holes this is empty — waypoints alone are
    enough, and the visibility graph stays tiny.
    """
    if boundary_geom.isMultipart():
        parts = boundary_geom.asMultiPolygon()
    else:
        parts = [boundary_geom.asPolygon()]

    vertices = []
    seen = set()
    for part in parts:
        for ring_idx, ring in enumerate(part):
            pts = _ring_points(ring)
            for v in _useful_ring_vertices(pts, is_exterior=(ring_idx == 0)):
                key = (round(v.x(), 9), round(v.y(), 9))
                if key not in seen:
                    seen.add(key)
                    vertices.append(v)
    return vertices


def all_boundary_vertices(boundary_geom):
    """Every ring vertex, deduplicated. Fallback if reduction is disabled."""
    if boundary_geom.isMultipart():
        parts = boundary_geom.asMultiPolygon()
    else:
        parts = [boundary_geom.asPolygon()]
    vertices = []
    seen = set()
    for part in parts:
        for ring in part:
            for v in _ring_points(ring):
                key = (round(v.x(), 9), round(v.y(), 9))
                if key not in seen:
                    seen.add(key)
                    vertices.append(v)
    return vertices


def prepared_engine(geom):
    """GEOS prepared-geometry engine for fast repeated predicate tests.

    The engine holds a pointer into ``geom``; callers must keep the QgsGeometry
    alive for as long as the engine is used.
    """
    engine = QgsGeometry.createGeometryEngine(geom.constGet())
    engine.prepareGeometry()
    return engine


def points_outside_region(points, region):
    """Indices of points not inside (or on the edge of) the region polygon."""
    engine = prepared_engine(region)
    outside = []
    for idx, p in enumerate(points):
        if not engine.intersects(QgsPoint(p.x(), p.y())):
            outside.append(idx)
    return outside


def build_visibility_adjacency(nodes, region, progress=None, should_cancel=None):
    """Visibility graph over ``nodes`` inside the (buffered) region polygon.

    An edge exists between two nodes when the straight segment between them
    stays inside the region — which automatically routes around holes, since
    holes are not part of the polygon interior. Uses a prepared geometry
    engine, so each test is a fast GEOS predicate instead of an overlay.

    If ``region`` is None there is no boundary constraint: every pair of nodes
    is connected by its straight-line (Euclidean) distance, i.e. an ordinary
    complete-graph TSP with no obstacle avoidance.

    Returns {i: {j: distance}} adjacency.
    """
    n = len(nodes)
    adjacency = {i: {} for i in range(n)}
    qgs_points = [QgsPoint(p.x(), p.y()) for p in nodes]
    engine = prepared_engine(region) if region is not None else None
    total = n * (n - 1) // 2
    done = 0
    for i in range(n):
        if should_cancel and should_cancel():
            raise TSPCancelled
        xi, yi = nodes[i].x(), nodes[i].y()
        for j in range(i + 1, n):
            d = math.hypot(xi - nodes[j].x(), yi - nodes[j].y())
            if d < 1e-12:
                # Coincident nodes (e.g. a waypoint sitting exactly on a kept
                # boundary vertex): free hop, no geometry test needed.
                adjacency[i][j] = adjacency[j][i] = 0.0
            elif engine is None:
                # No boundary: straight line between every pair is allowed.
                adjacency[i][j] = adjacency[j][i] = d
            else:
                seg = QgsLineString([qgs_points[i], qgs_points[j]])
                if engine.contains(seg):
                    adjacency[i][j] = adjacency[j][i] = d
        done += n - i - 1
        if progress and total:
            progress(done / total)
    return adjacency


def stitch_route(order, paths, nodes, closed):
    """Expand a waypoint order into the full point sequence via cached paths.

    Returns (route_points list[QgsPointXY], leg_lengths list[float]). Raises
    RoutingError never — unreachable pairs are filtered out before solving.
    """
    legs = [(order[k], order[k + 1]) for k in range(len(order) - 1)]
    if closed and len(order) > 1:
        legs.append((order[-1], order[0]))

    route_points = []
    leg_lengths = []
    for i, j in legs:
        path = paths[(i, j)]
        pts = [nodes[t] for t in path]
        length = 0.0
        for k in range(len(pts) - 1):
            length += math.hypot(pts[k + 1].x() - pts[k].x(),
                                 pts[k + 1].y() - pts[k].y())
        leg_lengths.append(length)
        start_at = 1 if route_points else 0
        for p in pts[start_at:]:
            # Guard against zero-length hops producing duplicate vertices.
            if route_points and route_points[-1].x() == p.x() and route_points[-1].y() == p.y():
                continue
            route_points.append(p)
    return route_points, leg_lengths
