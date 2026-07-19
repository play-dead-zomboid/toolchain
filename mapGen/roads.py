from __future__ import annotations
import numpy as np


# ============================================================
# Public Entry
# ============================================================

def generate_roads(height, slope, water, rng):
    h, w = height.shape

    roads = np.zeros((h, w), dtype=np.float32)
    road_class = np.zeros((h, w), dtype=np.uint8)

    arterials = _build_arterials(h, w, rng)
    grids = _build_urban_grids(h, w, rng)
    tertiaries = _subdivide_blocks_connected(grids, rng)

    arterials, grids, tertiaries = _prune_disconnected_segments(
        arterials,
        grids,
        tertiaries,
        water=water,
        h=h,
        w=w,
    )

    # Tertiary (cls=3)
    for poly in tertiaries:
        _raster_polyline(roads, road_class, poly, width=6, cls=3, water=water)

    # Secondary (cls=2)
    for poly in grids:
        _raster_polyline(roads, road_class, poly, width=6, cls=2, water=water)

    # Primary (cls=1)
    for poly in arterials:
        _raster_polyline(roads, road_class, poly, width=8, cls=1, water=water)

    return roads, road_class

# ============================================================
# Arterials (Highways)
# ============================================================

def _build_arterials(h, w, rng):
    lines = []
    count = rng.integers(2, 4)

    for _ in range(count):
        t = rng.random()

        if t < 0.25:
            y = int(rng.integers(int(h*0.2), int(h*0.8)))
            lines.append(np.array([[y, 0], [y, w-1]], dtype=np.float32))

        elif t < 0.5:
            x = int(rng.integers(int(w*0.2), int(w*0.8)))
            lines.append(np.array([[0, x], [h-1, x]], dtype=np.float32))

        elif t < 0.75:
            lines.append(np.array([[0, 0], [h-1, w-1]], dtype=np.float32))

        else:
            lines.append(np.array([[h-1, 0], [0, w-1]], dtype=np.float32))

    return lines

# ============================================================
# Urban Grids
# ============================================================

def _build_urban_grids(h, w, rng):
    grids = []

    margin_y = int(h * 0.15)
    margin_x = int(w * 0.15)

    y0 = margin_y
    y1 = h - margin_y
    x0 = margin_x
    x1 = w - margin_x

    # --- Variable vertical streets ---
    verticals = []
    x = x0
    while x < x1:
        grids.append(np.array([[y0, x], [y1, x]], dtype=np.float32))
        verticals.append(x)
        x += int(rng.integers(50, 110))

    # --- Variable horizontal streets ---
    horizontals = []
    y = y0
    while y < y1:
        grids.append(np.array([[y, x0], [y, x1]], dtype=np.float32))
        horizontals.append(y)
        y += int(rng.integers(50, 110))

    # --- Secondary diagonals (45° only) ---
    diag_attempts = rng.integers(1, 4)

    for _ in range(diag_attempts):
        if len(verticals) < 4 or len(horizontals) < 4:
            break

        if rng.random() < 0.4:

            xi = rng.integers(0, len(verticals) - 3)
            yi = rng.integers(0, len(horizontals) - 3)

            span = rng.integers(2, 4)

            xi2 = min(xi + span, len(verticals) - 1)
            yi2 = min(yi + span, len(horizontals) - 1)

            x0 = verticals[xi]
            x1 = verticals[xi2]
            y0 = horizontals[yi]
            y1 = horizontals[yi2]

            # enforce true 45°
            dx = x1 - x0
            dy = y1 - y0
            d = min(dx, dy)

            x1 = x0 + d
            y1 = y0 + d

            if rng.random() < 0.5:
                grids.append(np.array([[y0, x0], [y1, x1]], dtype=np.float32))
            else:
                grids.append(np.array([[y1, x0], [y0, x1]], dtype=np.float32))

    return grids


# ============================================================
# Rasterization
# ============================================================

def _raster_polyline(roads, road_class, poly, width, cls, water=None):
    h, w = roads.shape
    r = width // 2

    for i in range(len(poly) - 1):
        y0, x0 = poly[i]
        y1, x1 = poly[i + 1]

        steps = int(max(abs(y1 - y0), abs(x1 - x0))) + 1

        for t in np.linspace(0, 1, steps):
            y = int(round(y0 * (1 - t) + y1 * t))
            x = int(round(x0 * (1 - t) + x1 * t))

            if not (0 <= y < h and 0 <= x < w):
                continue

            # Stop non-primary roads at water (terminate, do not skip/resume)
            if cls != 1 and water is not None and water[y, x]:
                break

            ys = slice(max(0, y - r), min(h, y + r + 1))
            xs = slice(max(0, x - r), min(w, x + r + 1))

            roads[ys, xs] = 1.0

            existing = road_class[ys, xs]
            road_class[ys, xs] = np.where(
                existing == 0,
                cls,
                np.minimum(existing, cls)
            ).astype(np.uint8)


def _subdivide_blocks_connected(grids, rng):
    tertiary = []

    verticals = sorted(set(int(line[0][1]) for line in grids if line[0][1] == line[1][1]))
    horizontals = sorted(set(int(line[0][0]) for line in grids if line[0][0] == line[1][0]))

    for i in range(len(verticals) - 1):
        for j in range(len(horizontals) - 1):

            x0 = verticals[i]
            x1 = verticals[i+1]
            y0 = horizontals[j]
            y1 = horizontals[j+1]

            if rng.random() < 0.35:

                if rng.random() < 0.5:
                    x = int(rng.integers(x0 + 15, x1 - 15))
                    tertiary.append(
                        np.array([[y0, x], [y1, x]], dtype=np.float32)
                    )
                else:
                    y = int(rng.integers(y0 + 15, y1 - 15))
                    tertiary.append(
                        np.array([[y, x0], [y, x1]], dtype=np.float32)
                    )

    return tertiary


# ============================================================
# Connectivity Pruning (Implicit -> Explicit-ish)
#
# Minimal graph pass: treat each 2-point polyline as a segment.
# Build segment connectivity via intersection / shared endpoints,
# then keep only components that contain a primary.
# Non-primaries are clipped to water before connectivity testing.
# ============================================================


class _UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            self.parent[ra] = rb
        elif self.rank[ra] > self.rank[rb]:
            self.parent[rb] = ra
        else:
            self.parent[rb] = ra
            self.rank[ra] += 1


def _prune_disconnected_segments(arterials, grids, tertiaries, water, h, w):
    segments = []

    for poly in arterials:
        seg = _normalize_segment(poly)
        if seg is not None:
            segments.append((1, seg))

    for poly in grids:
        seg = _clip_segment_to_water(_normalize_segment(poly), water, cls=2, h=h, w=w)
        if seg is not None:
            segments.append((2, seg))

    for poly in tertiaries:
        seg = _clip_segment_to_water(_normalize_segment(poly), water, cls=3, h=h, w=w)
        if seg is not None:
            segments.append((3, seg))

    if not segments:
        return arterials, grids, tertiaries

    uf = _UnionFind(len(segments))

    for i in range(len(segments)):
        _, (p1, p2) = segments[i]
        for j in range(i + 1, len(segments)):
            _, (q1, q2) = segments[j]
            if _segments_intersect(p1, p2, q1, q2):
                uf.union(i, j)

    primary_roots = set()
    for idx, (cls, _) in enumerate(segments):
        if cls == 1:
            primary_roots.add(uf.find(idx))

    if not primary_roots:
        counts = {}
        for idx in range(len(segments)):
            r = uf.find(idx)
            counts[r] = counts.get(r, 0) + 1
        keep_roots = {max(counts, key=counts.get)}
    else:
        keep_roots = primary_roots

    kept_arterials = []
    kept_grids = []
    kept_tertiaries = []

    for idx, (cls, (p1, p2)) in enumerate(segments):
        if uf.find(idx) not in keep_roots:
            continue

        poly = np.array([[p1[0], p1[1]], [p2[0], p2[1]]], dtype=np.float32)

        if cls == 1:
            kept_arterials.append(poly)
        elif cls == 2:
            kept_grids.append(poly)
        else:
            kept_tertiaries.append(poly)

    return kept_arterials, kept_grids, kept_tertiaries


def _normalize_segment(poly):
    if poly is None or len(poly) < 2:
        return None

    y0, x0 = poly[0]
    y1, x1 = poly[1]

    p1 = (int(round(y0)), int(round(x0)))
    p2 = (int(round(y1)), int(round(x1)))

    if p1 == p2:
        return None

    return (p1, p2)


def _clip_segment_to_water(seg, water, cls, h, w):
    if seg is None:
        return None
    if cls == 1 or water is None:
        return seg

    (y0, x0), (y1, x1) = seg
    steps = int(max(abs(y1 - y0), abs(x1 - x0))) + 1
    if steps <= 1:
        if 0 <= y0 < h and 0 <= x0 < w and not water[y0, x0]:
            return seg
        return None

    last = (y0, x0)
    for t in np.linspace(0, 1, steps):
        y = int(round(y0 * (1 - t) + y1 * t))
        x = int(round(x0 * (1 - t) + x1 * t))
        if not (0 <= y < h and 0 <= x < w):
            continue
        if water[y, x]:
            if last == (y0, x0):
                return None
            return ((y0, x0), last)
        last = (y, x)

    return seg


def _segments_intersect(p1, p2, q1, q2):
    def _orient(a, b, c):
        return (b[1] - a[1]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[1] - a[1])

    def _on_segment(a, b, c):
        return (
            min(a[0], b[0]) <= c[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])
        )

    o1 = _orient(p1, p2, q1)
    o2 = _orient(p1, p2, q2)
    o3 = _orient(q1, q2, p1)
    o4 = _orient(q1, q2, p2)

    if o1 == 0 and _on_segment(p1, p2, q1):
        return True
    if o2 == 0 and _on_segment(p1, p2, q2):
        return True
    if o3 == 0 and _on_segment(q1, q2, p1):
        return True
    if o4 == 0 and _on_segment(q1, q2, p2):
        return True

    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)