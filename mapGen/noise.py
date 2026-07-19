from __future__ import annotations

import numpy as np


def _fade(t: np.ndarray) -> np.ndarray:
    return t * t * t * (t * (t * 6 - 15) + 10)


def _lerp(a: np.ndarray, b: np.ndarray, t: np.ndarray) -> np.ndarray:
    return a + (b - a) * t


def value_noise(w: int, h: int, grid: int, rng: np.random.Generator) -> np.ndarray:
    gx = (w // grid) + 2
    gy = (h // grid) + 2
    g = rng.random((gy, gx), dtype=np.float32)

    xs = np.arange(w, dtype=np.float32) / grid
    ys = np.arange(h, dtype=np.float32) / grid
    xi = xs.astype(np.int32)
    yi = ys.astype(np.int32)
    xf = _fade(xs - xi)
    yf = _fade(ys - yi)

    x0 = xi
    x1 = xi + 1
    y0 = yi
    y1 = yi + 1

    n00 = g[y0[:, None], x0[None, :]]
    n10 = g[y0[:, None], x1[None, :]]
    n01 = g[y1[:, None], x0[None, :]]
    n11 = g[y1[:, None], x1[None, :]]

    nx0 = _lerp(n00, n10, xf[None, :])
    nx1 = _lerp(n01, n11, xf[None, :])
    nxy = _lerp(nx0, nx1, yf[:, None])
    return nxy


def fbm(
    w: int,
    h: int,
    base_grid: int,
    octaves: int,
    lacunarity: float,
    gain: float,
    rng: np.random.Generator,
) -> np.ndarray:
    amp = 1.0
    freq_grid = float(base_grid)
    out = np.zeros((h, w), dtype=np.float32)
    norm = 0.0
    for _ in range(octaves):
        out += amp * value_noise(w, h, max(1, int(freq_grid)), rng)
        norm += amp
        amp *= gain
        freq_grid /= lacunarity
    out /= max(1e-6, norm)
    return out