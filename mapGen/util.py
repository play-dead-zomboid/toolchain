from __future__ import annotations

from dataclasses import dataclass
import numpy as np


def hex_rgb(hex_str: str) -> tuple[int, int, int]:
    s = hex_str.strip().lower()
    if s.startswith("#"):
        s = s[1:]
    if len(s) != 6:
        raise ValueError(f"Expected 6-digit hex RGB, got: {hex_str}")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def normalize01(a: np.ndarray) -> np.ndarray:
    a = a.astype(np.float32, copy=False)
    lo = float(a.min())
    hi = float(a.max())
    if hi - lo < 1e-8:
        return np.zeros_like(a, dtype=np.float32)
    return (a - lo) / (hi - lo)


def clamp01(a: np.ndarray) -> np.ndarray:
    return np.clip(a, 0.0, 1.0).astype(np.float32, copy=False)


def max_filter(binary: np.ndarray, r: int) -> np.ndarray:
    """
    Binary dilation-ish: any neighbor within (2r+1)x(2r+1) becomes True.
    """
    if r <= 0:
        return binary.astype(bool, copy=False)
    b = binary.astype(np.uint8, copy=False)
    h, w = b.shape
    pad = np.pad(b, r, mode="edge")
    out = np.zeros((h, w), dtype=np.uint8)
    for dy in range(2 * r + 1):
        for dx in range(2 * r + 1):
            out |= pad[dy : dy + h, dx : dx + w]
    return out.astype(bool)


def min_filter(binary: np.ndarray, r: int) -> np.ndarray:
    """
    Binary erosion-ish: all neighbors within window must be True.
    """
    if r <= 0:
        return binary.astype(bool, copy=False)
    b = binary.astype(np.uint8, copy=False)
    h, w = b.shape
    pad = np.pad(b, r, mode="edge")
    out = np.ones((h, w), dtype=np.uint8)
    for dy in range(2 * r + 1):
        for dx in range(2 * r + 1):
            out &= pad[dy : dy + h, dx : dx + w]
    return out.astype(bool)

def min_filter(binary: np.ndarray, r: int) -> np.ndarray:
    """
    Binary erosion: pixel survives only if all neighbors in window are True.
    """
    if r <= 0:
        return binary.astype(bool, copy=False)

    b = binary.astype(np.uint8, copy=False)
    h, w = b.shape
    pad = np.pad(b, r, mode="edge")
    out = np.ones((h, w), dtype=np.uint8)

    for dy in range(2 * r + 1):
        for dx in range(2 * r + 1):
            out &= pad[dy:dy+h, dx:dx+w]

    return out.astype(bool)