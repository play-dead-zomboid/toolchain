from __future__ import annotations

import numpy as np
from noise import fbm
from util import normalize01, clamp01


def generate_height(
    w: int,
    h: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Subtle terrain: low-amplitude, low-frequency features.
    Still normalized 0..1; "subtle" is in downstream slope usage.
    """
    base = fbm(w, h, base_grid=140, octaves=4, lacunarity=2.0, gain=0.55, rng=rng)
    detail = fbm(w, h, base_grid=60, octaves=2, lacunarity=2.0, gain=0.5, rng=rng)

    # very light domain-ish warp by blending
    height = 0.85 * base + 0.15 * detail
    height = normalize01(height)
    return height


def slope_magnitude(height: np.ndarray) -> np.ndarray:
    """
    Gradient magnitude, normalized 0..1.
    """
    gy, gx = np.gradient(height.astype(np.float32, copy=False))
    s = np.sqrt(gx * gx + gy * gy).astype(np.float32)
    return normalize01(s)


def moisture_proxy(height: np.ndarray, slope: np.ndarray) -> np.ndarray:
    """
    Cheap, stable proxy:
      - lower elevations tend to be wetter
      - flatter areas retain moisture
    """
    wet = (1.0 - height) * 0.65 + (1.0 - slope) * 0.35
    return clamp01(wet)