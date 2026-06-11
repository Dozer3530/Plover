# -*- coding: utf-8 -*-
"""Unit tests for the pure-Python solver core. No QGIS required:

    python -m unittest tsp_route_generator.test.test_tsp_core -v
"""

import itertools
import math
import unittest

from tsp_route_generator import tsp_core
from tsp_route_generator.tsp_core import (
    INF,
    RoutingError,
    dijkstra,
    nearest_neighbour,
    or_opt,
    reconstruct_path,
    solve_order,
    tour_length,
    two_opt,
    unreachable_from,
    waypoint_matrix,
)


def euclidean_matrix(coords):
    n = len(coords)
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = math.dist(coords[i], coords[j])
            dist[i][j] = dist[j][i] = d
    return dist


def brute_force(dist, start, closed):
    n = len(dist)
    best_len, best_order = INF, None
    for perm in itertools.permutations(r for r in range(n) if r != start):
        order = [start] + list(perm)
        length = tour_length(order, dist, closed)
        if length < best_len:
            best_len, best_order = length, order
    return best_order, best_len


class DijkstraTests(unittest.TestCase):
    GRAPH = {
        0: {1: 1.0, 2: 4.0},
        1: {0: 1.0, 2: 1.0, 3: 6.0},
        2: {0: 4.0, 1: 1.0, 3: 1.0},
        3: {1: 6.0, 2: 1.0},
        4: {},  # isolated
    }

    def test_shortest_distances_and_path(self):
        dist, prev = dijkstra(self.GRAPH, 0)
        self.assertAlmostEqual(dist[3], 3.0)  # 0-1-2-3
        self.assertEqual(reconstruct_path(prev, 0, 3), [0, 1, 2, 3])

    def test_unreachable_node(self):
        dist, prev = dijkstra(self.GRAPH, 0)
        self.assertNotIn(4, dist)
        self.assertIsNone(reconstruct_path(prev, 0, 4))

    def test_early_exit_with_targets(self):
        dist, _ = dijkstra(self.GRAPH, 0, targets={1})
        self.assertAlmostEqual(dist[1], 1.0)

    def test_path_to_self(self):
        _, prev = dijkstra(self.GRAPH, 2)
        self.assertEqual(reconstruct_path(prev, 2, 2), [2])


class WaypointMatrixTests(unittest.TestCase):
    def test_routes_through_steiner_node(self):
        # Waypoints 0 and 1 are only connected via non-waypoint node 2
        # (a "boundary vertex"), like a path bending around a hole corner.
        adjacency = {
            0: {2: 5.0},
            1: {2: 5.0},
            2: {0: 5.0, 1: 5.0},
        }
        dist, paths = waypoint_matrix(adjacency, 2)
        self.assertAlmostEqual(dist[0][1], 10.0)
        self.assertEqual(paths[(0, 1)], [0, 2, 1])
        self.assertEqual(paths[(1, 0)], [1, 2, 0])

    def test_symmetry_and_diagonal(self):
        coords = [(0, 0), (3, 0), (3, 4), (0, 4)]
        adjacency = {
            i: {j: math.dist(coords[i], coords[j])
                for j in range(4) if j != i}
            for i in range(4)
        }
        dist, _ = waypoint_matrix(adjacency, 4)
        for i in range(4):
            self.assertEqual(dist[i][i], 0.0)
            for j in range(4):
                self.assertAlmostEqual(dist[i][j], dist[j][i])

    def test_unreachable_pair_reported(self):
        adjacency = {0: {1: 1.0}, 1: {0: 1.0}, 2: {}}
        dist, paths = waypoint_matrix(adjacency, 3)
        self.assertEqual(dist[0][2], INF)
        self.assertNotIn((0, 2), paths)
        self.assertEqual(unreachable_from(dist, 0), [2])


class LocalSearchTests(unittest.TestCase):
    def test_two_opt_uncrosses_square(self):
        coords = [(0, 0), (10, 0), (10, 10), (0, 10)]
        dist = euclidean_matrix(coords)
        crossed = [0, 2, 1, 3]  # both diagonals
        fixed = two_opt(crossed, dist, closed=True)
        self.assertAlmostEqual(tour_length(fixed, dist, True), 40.0)

    def test_two_opt_open_path_tail_reversal(self):
        # 0 at origin; tail visits far point before near point. Reversing the
        # tail (a move only valid for open paths) shortens it.
        coords = [(0, 0), (1, 0), (10, 0), (2, 0)]
        dist = euclidean_matrix(coords)
        order = two_opt([0, 1, 2, 3], dist, closed=False)
        self.assertEqual(order[0], 0)
        self.assertAlmostEqual(tour_length(order, dist, False), 10.0)  # 0-1-3-2

    def test_or_opt_relocates_stranded_stop(self):
        # Collinear points with the far point (4) visited prematurely; a
        # single-stop relocation to the tour end shortens 24 -> 20.
        coords = [(0, 0), (1, 0), (2, 0), (3, 0), (10, 0)]
        dist = euclidean_matrix(coords)
        bad = [0, 4, 1, 2, 3]
        self.assertAlmostEqual(tour_length(bad, dist, True), 24.0)
        better = or_opt(bad, dist, closed=True)
        self.assertAlmostEqual(tour_length(better, dist, True), 20.0)
        self.assertEqual(sorted(better), [0, 1, 2, 3, 4])
        self.assertEqual(better[0], 0)

    def test_moves_preserve_permutation(self):
        coords = [(3, 1), (0, 0), (7, 2), (4, 6), (1, 5), (6, 5), (2, 2)]
        dist = euclidean_matrix(coords)
        for closed in (True, False):
            order = nearest_neighbour(dist, 0)
            order = two_opt(order, dist, closed)
            order = or_opt(order, dist, closed)
            self.assertEqual(sorted(order), list(range(7)))
            self.assertEqual(order[0], 0)


class SolveOrderTests(unittest.TestCase):
    def test_circle_reaches_optimum(self):
        coords = [(math.cos(2 * math.pi * k / 12) * 100,
                   math.sin(2 * math.pi * k / 12) * 100) for k in range(12)]
        dist = euclidean_matrix(coords)
        optimal = 12 * math.dist(coords[0], coords[1])
        order, length = solve_order(dist, start=5, closed=True)
        self.assertEqual(order[0], 5)
        self.assertAlmostEqual(length, optimal, places=6)

    def test_matches_brute_force_closed(self):
        coords = [(0, 0), (9, 2), (4, 7), (8, 8), (1, 6), (6, 1), (3, 3), (7, 5)]
        dist = euclidean_matrix(coords)
        _, best_len = brute_force(dist, 0, closed=True)
        order, length = solve_order(dist, start=0, closed=True)
        self.assertEqual(order[0], 0)
        self.assertEqual(sorted(order), list(range(8)))
        self.assertLessEqual(length, best_len * 1.05 + 1e-9)

    def test_matches_brute_force_open(self):
        coords = [(0, 0), (9, 2), (4, 7), (8, 8), (1, 6), (6, 1), (3, 3)]
        dist = euclidean_matrix(coords)
        _, best_len = brute_force(dist, 2, closed=False)
        order, length = solve_order(dist, start=2, closed=False)
        self.assertEqual(order[0], 2)
        self.assertLessEqual(length, best_len * 1.05 + 1e-9)

    def test_open_path_collinear_is_a_sweep(self):
        coords = [(0, 0), (40, 0), (10, 0), (30, 0), (20, 0)]
        dist = euclidean_matrix(coords)
        order, length = solve_order(dist, start=0, closed=False)
        self.assertEqual(order, [0, 2, 4, 3, 1])
        self.assertAlmostEqual(length, 40.0)

    def test_two_points(self):
        dist = euclidean_matrix([(0, 0), (5, 0)])
        order, length = solve_order(dist, 0, closed=True)
        self.assertEqual(order, [0, 1])
        self.assertAlmostEqual(length, 10.0)
        order, length = solve_order(dist, 0, closed=False)
        self.assertAlmostEqual(length, 5.0)

    def test_disconnected_raises(self):
        dist = [[0.0, 1.0, INF], [1.0, 0.0, INF], [INF, INF, 0.0]]
        with self.assertRaises(RoutingError):
            nearest_neighbour(dist, 0)

    def test_cancellation(self):
        coords = [(k, k % 3) for k in range(10)]
        dist = euclidean_matrix(coords)
        with self.assertRaises(tsp_core.TSPCancelled):
            solve_order(dist, 0, closed=True, should_cancel=lambda: True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
