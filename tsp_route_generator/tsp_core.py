# -*- coding: utf-8 -*-
"""Pure-Python TSP solving core for Plover.

No QGIS imports in this module: everything operates on plain numbers, dicts
and lists, so it can be unit-tested with any Python interpreter.

Pipeline overview:

    visibility graph (geometry_utils.py)
        -> waypoint_matrix()      shortest path between every waypoint pair
        -> solve_order()          multi-start nearest-neighbour + 2-opt + Or-opt
        -> stitching (route_task.py) expands the order with the cached paths
"""

from heapq import heappush, heappop

INF = float("inf")

# Improvement moves smaller than this are treated as float noise. Coordinates
# are map units (normally metres), so a nanometre threshold is safely inert.
EPS = 1e-9


class TSPCancelled(Exception):
    """Raised internally when the caller's cancel callback returns True."""


class RoutingError(Exception):
    """A routing problem the user can act on (e.g. unreachable waypoints)."""


def dijkstra(adjacency, source, targets=None):
    """Single-source shortest paths over a dict-of-dicts adjacency.

    adjacency: {node: {neighbour: weight}}. Returns (dist, prev) dicts where
    dist maps reached nodes to their cost and prev maps each reached node to
    its predecessor. If ``targets`` (a set) is given, the search stops as soon
    as every target has been settled.
    """
    dist = {source: 0.0}
    prev = {}
    remaining = set(targets) - {source} if targets is not None else None
    settled = set()
    pq = [(0.0, source)]
    while pq:
        d, u = heappop(pq)
        if u in settled:
            continue
        settled.add(u)
        if remaining is not None:
            remaining.discard(u)
            if not remaining:
                break
        for v, w in adjacency.get(u, {}).items():
            if v in settled:
                continue
            nd = d + w
            if nd < dist.get(v, INF):
                dist[v] = nd
                prev[v] = u
                heappush(pq, (nd, v))
    return dist, prev


def reconstruct_path(prev, source, target):
    """Rebuild the node sequence source..target from a predecessor map."""
    if target == source:
        return [source]
    if target not in prev:
        return None
    path = [target]
    while path[-1] != source:
        path.append(prev[path[-1]])
    path.reverse()
    return path


def waypoint_matrix(adjacency, n_waypoints, progress=None, should_cancel=None):
    """All-pairs shortest paths among waypoints (nodes 0 .. n_waypoints-1).

    One Dijkstra per waypoint instead of one per *pair*: the run from waypoint
    i yields distances and paths to every later waypoint at once, and symmetry
    fills the mirrored entries.

    Returns (dist, paths): dist is an n x n list-of-lists (INF = unreachable),
    paths[(i, j)] is the visibility-graph node sequence from i to j.
    """
    dist = [[INF] * n_waypoints for _ in range(n_waypoints)]
    paths = {}
    for i in range(n_waypoints):
        dist[i][i] = 0.0
    for i in range(n_waypoints - 1):
        if should_cancel and should_cancel():
            raise TSPCancelled
        targets = set(range(i + 1, n_waypoints))
        d, prev = dijkstra(adjacency, i, targets)
        for j in targets:
            dj = d.get(j, INF)
            if dj < INF:
                path = reconstruct_path(prev, i, j)
                dist[i][j] = dist[j][i] = dj
                paths[(i, j)] = path
                paths[(j, i)] = path[::-1]
        if progress:
            progress((i + 1) / max(n_waypoints - 1, 1))
    return dist, paths


def unreachable_from(dist, start):
    """Waypoint indices that cannot be reached from ``start``."""
    return [j for j in range(len(dist)) if dist[start][j] == INF]


def tour_length(order, dist, closed):
    """Total cost of visiting ``order``; adds the wrap edge when closed."""
    total = 0.0
    for k in range(len(order) - 1):
        total += dist[order[k]][order[k + 1]]
    if closed and len(order) > 1:
        total += dist[order[-1]][order[0]]
    return total


def nearest_neighbour(dist, start):
    """Greedy construction: always walk to the closest unvisited waypoint."""
    n = len(dist)
    order = [start]
    unvisited = set(range(n))
    unvisited.discard(start)
    current = start
    while unvisited:
        row = dist[current]
        nxt = min(unvisited, key=lambda c: row[c])
        if row[nxt] == INF:
            raise RoutingError(
                "Waypoint graph is disconnected; some points cannot be reached."
            )
        order.append(nxt)
        unvisited.discard(nxt)
        current = nxt
    return order


def two_opt(order, dist, closed, should_cancel=None, max_passes=60):
    """First-improvement 2-opt. Position 0 stays fixed.

    Closed tours include the wrap edge (last -> first) in every delta. Open
    paths leave the far end free, which additionally allows plain tail
    reversals (j == n-1 with no successor edge).
    """
    order = order[:]
    n = len(order)
    if n < 3:
        return order
    improved = True
    passes = 0
    while improved and passes < max_passes:
        improved = False
        passes += 1
        for i in range(1, n - 1):
            if should_cancel and should_cancel():
                raise TSPCancelled
            a, b = order[i - 1], order[i]
            d_ab = dist[a][b]
            for j in range(i + 1, n):
                c = order[j]
                if j == n - 1 and not closed:
                    delta = dist[a][c] - d_ab
                else:
                    nxt = order[0] if j == n - 1 else order[j + 1]
                    delta = dist[a][c] + dist[b][nxt] - d_ab - dist[c][nxt]
                if delta < -EPS:
                    order[i:j + 1] = reversed(order[i:j + 1])
                    improved = True
                    b = order[i]
                    d_ab = dist[a][b]
    return order


def or_opt(order, dist, closed, should_cancel=None, max_passes=30):
    """Relocate runs of 1-3 consecutive stops to a better spot (Or-opt).

    Catches improvements 2-opt cannot express, e.g. pulling one stop out of a
    detour and reinserting it between two stops elsewhere. Position 0 stays
    fixed; for closed tours the wrap edge (last -> first) participates both as
    a removal site and as an insertion site.
    """
    order = order[:]
    n = len(order)
    if n < 4:
        return order

    improved = True
    passes = 0
    while improved and passes < max_passes:
        improved = False
        passes += 1
        for seg_len in (1, 2, 3):
            i = 1
            while i + seg_len <= n:
                if should_cancel and should_cancel():
                    raise TSPCancelled
                prev_node = order[i - 1]
                first = order[i]
                last = order[i + seg_len - 1]
                if i + seg_len < n:
                    after = order[i + seg_len]
                elif closed:
                    after = order[0]
                else:
                    after = None
                # Cost freed by cutting the segment out of the tour.
                if after is not None:
                    gain = (dist[prev_node][first] + dist[last][after]
                            - dist[prev_node][after])
                else:
                    gain = dist[prev_node][first]

                best_delta = -EPS
                best_move = None
                for q in range(n):
                    # Skip the segment itself and the edge feeding into it
                    # (q == i-1 would reinsert in place).
                    if i - 1 <= q <= i + seg_len - 1:
                        continue
                    u = order[q]
                    if q + 1 < n:
                        v = order[q + 1]
                    elif closed:
                        v = order[0]
                    else:
                        v = None
                    removed = dist[u][v] if v is not None else 0.0
                    if v is not None:
                        fwd = dist[u][first] + dist[last][v] - removed
                        rev = dist[u][last] + dist[first][v] - removed
                    else:
                        fwd = dist[u][first]
                        rev = dist[u][last]
                    for delta_ins, flip in ((fwd, False), (rev, True)):
                        delta = delta_ins - gain
                        if delta < best_delta:
                            best_delta = delta
                            best_move = (q, flip)

                if best_move is not None:
                    q, flip = best_move
                    seg = order[i:i + seg_len]
                    if flip:
                        seg.reverse()
                    rest = order[:i] + order[i + seg_len:]
                    u_idx = q if q < i else q - seg_len
                    rest[u_idx + 1:u_idx + 1] = seg
                    order = rest
                    improved = True
                    # Re-examine the same position with the new layout.
                    continue
                i += 1
    return order


def _start_candidates(n, start, closed):
    """Start indices for multi-start NN, spread evenly across the waypoints.

    A closed tour's length does not depend on where the cycle starts, so other
    construction starts are legitimate; the winning cycle is rotated back to
    the user's start afterwards. Open paths must begin at ``start``.
    """
    if not closed or n <= 3:
        return [start]
    if n <= 150:
        n_starts = 8
    elif n <= 400:
        n_starts = 4
    else:
        n_starts = 2
    step = max(1, n // n_starts)
    spread = list(range(0, n, step))[:n_starts]
    return [start] + [s for s in spread if s != start]


def solve_order(dist, start, closed=True, progress=None, should_cancel=None):
    """Best tour/path over the waypoint distance matrix.

    Multi-start nearest-neighbour construction, each candidate polished by
    alternating 2-opt and Or-opt until neither improves. Returns
    (order, length) where order is a list of waypoint indices beginning at
    ``start`` (no duplicate of the start at the end; the wrap edge is implied
    when closed).
    """
    n = len(dist)
    if n == 0:
        return [], 0.0
    if n == 1:
        return [start], 0.0

    starts = _start_candidates(n, start, closed)
    best_order = None
    best_len = INF
    for idx, s in enumerate(starts):
        if should_cancel and should_cancel():
            raise TSPCancelled
        order = nearest_neighbour(dist, s)
        length = tour_length(order, dist, closed)
        while True:
            order = two_opt(order, dist, closed, should_cancel)
            order = or_opt(order, dist, closed, should_cancel)
            new_len = tour_length(order, dist, closed)
            if new_len > length - EPS:
                break
            length = new_len
        if length < best_len - EPS:
            best_len = length
            best_order = order
        if progress:
            progress((idx + 1) / len(starts))

    if closed:
        k = best_order.index(start)
        best_order = best_order[k:] + best_order[:k]
    return best_order, tour_length(best_order, dist, closed)
