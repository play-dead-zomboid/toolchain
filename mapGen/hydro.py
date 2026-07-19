from __future__ import annotations

import numpy as np
from collections import deque
from util import max_filter, min_filter


def _label_components(mask: np.ndarray, min_size: int, max_size: int | None = None) -> np.ndarray:
    h, w = mask.shape
    keep = np.zeros((h, w), dtype=bool)
    visited = np.zeros((h, w), dtype=bool)

    for y in range(h):
        for x in range(w):
            if not mask[y, x] or visited[y, x]:
                continue

            stack = [(y, x)]
            visited[y, x] = True
            comp = [(y, x)]

            while stack:
                cy, cx = stack.pop()

                for ny, nx in (
                    (cy-1, cx), (cy+1, cx),
                    (cy, cx-1), (cy, cx+1)
                ):
                    if 0 <= ny < h and 0 <= nx < w:
                        if mask[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            stack.append((ny, nx))
                            comp.append((ny, nx))

            size = len(comp)

            if size >= min_size and (max_size is None or size <= max_size):
                for (py, px) in comp:
                    keep[py, px] = True

    return keep


def generate_water_and_sand(
    height: np.ndarray,
    slope: np.ndarray,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Basin-ish water:
      - pick a low-percentile water level
      - keep only sufficiently large connected low regions
      - roughen shoreline slightly
      - sand appears as a noisy band near shoreline on flat-ish ground
    """
    h, w = height.shape

    # low percentile water level
    level = float(np.quantile(height, 0.14))
    low = height <= level

    # remove tiny puddles
    water = _label_components(
        low,
        min_size=max(250, (h * w) // 6000),
        max_size=(h * w) // 80
    )
    cell_h = 300
    cell_w = 300

    for cy in range(0, h, cell_h):
        for cx in range(0, w, cell_w):

            sub = water[cy:cy+cell_h, cx:cx+cell_w]

            if not sub.any():
                # find lowest elevation point inside this cell
                elev_sub = height[cy:cy+cell_h, cx:cx+cell_w]
                iy, ix = np.unravel_index(np.argmin(elev_sub), elev_sub.shape)

                # carve a small pond (radius ~10–15)
                ry = cy + iy
                rx = cx + ix

                r = 12
                yy, xx = np.ogrid[-r:r+1, -r:r+1]
                mask = yy*yy + xx*xx <= r*r

                sy = slice(max(0, ry-r), min(h, ry+r+1))
                sx = slice(max(0, rx-r), min(w, rx+r+1))

                submask = mask[
                    (sy.start - (ry-r)):(sy.stop - (ry-r)),
                    (sx.start - (rx-r)):(sx.stop - (rx-r))
                ]

                water[sy, sx][submask] = True

    # roughen shoreline: expand, then subtract core, then jitter add/remove
    water_d = max_filter(water, r=2)
    water_e = min_filter(water_d, r=1)
    water = water_e

    # shoreline band
    shore = water_d & (~water)

    # jitter shoreline by random mask
    jitter = rng.random((h, w), dtype=np.float32)
    water = water | (shore & (jitter > 0.78))
    water = water & (~(shore & (jitter < 0.08)))

    # sand: near water, relatively flat, with noisy thickness
    near = max_filter(water, r=6) & (~water)
    sand_noise = rng.random((h, w), dtype=np.float32)
    sand = near & (slope < 0.35) & (sand_noise > 0.18)

    return water, sand