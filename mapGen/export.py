from __future__ import annotations

import os
import numpy as np
from PIL import Image


def export_master(
    out_dir: str,
    surface: np.ndarray,
    vegetation: np.ndarray,
    zombies_30: np.ndarray,
):
    os.makedirs(out_dir, exist_ok=True)
    Image.fromarray(surface, mode="RGB").save(os.path.join(out_dir, "MASTER_surface.png"))
    Image.fromarray(vegetation, mode="RGB").save(os.path.join(out_dir, "MASTER_vegetation.png"))
    Image.fromarray(zombies_30, mode="L").save(os.path.join(out_dir, "MASTER_zombies.png"))


def slice_and_export(
    out_dir: str,
    cells_x: int,
    cells_y: int,
    cell_size: int,
    surface: np.ndarray,
    vegetation: np.ndarray,
    zombies_30: np.ndarray,
    prefix: str = "cell",
    write_master: bool = True,
):
    os.makedirs(out_dir, exist_ok=True)

    if write_master:
        export_master(out_dir, surface, vegetation, zombies_30)

    for cy in range(cells_y):
        for cx in range(cells_x):
            x0 = cx * cell_size
            y0 = cy * cell_size
            x1 = x0 + cell_size
            y1 = y0 + cell_size

            surf_cell = surface[y0:y1, x0:x1]
            veg_cell = vegetation[y0:y1, x0:x1]

            # zombie map uses 10:1 downsample (300->30)
            zx0 = cx * (cell_size // 10)
            zy0 = cy * (cell_size // 10)
            zx1 = zx0 + (cell_size // 10)
            zy1 = zy0 + (cell_size // 10)
            zom_cell = zombies_30[zy0:zy1, zx0:zx1]

            base = f"{prefix}_{cy:02d}_{cx:02d}"
            Image.fromarray(surf_cell, mode="RGB").save(os.path.join(out_dir, f"{base}.png"))
            Image.fromarray(veg_cell, mode="RGB").save(os.path.join(out_dir, f"{base}_veg.png"))
            Image.fromarray(zom_cell, mode="L").save(os.path.join(out_dir, f"{base}_zombies_30x30.png"))