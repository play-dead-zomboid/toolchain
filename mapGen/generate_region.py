from __future__ import annotations

from config import RegionConfig
from rng import make_rng
from terrain import generate_height, slope_magnitude, moisture_proxy
from hydro import generate_water_and_sand
from roads import generate_roads
from fields import build_fields
from export import slice_and_export


def generate_and_export(global_seed: int, cells_x: int, cells_y: int, out_dir: str):
    cfg = RegionConfig(cells_x=cells_x, cells_y=cells_y)
    w, h = cfg.width, cfg.height

    rng_terrain = make_rng(global_seed, "terrain")
    rng_hydro = make_rng(global_seed, "hydro")
    rng_roads = make_rng(global_seed, "roads")
    rng_fields = make_rng(global_seed, "fields")

    height = generate_height(w, h, rng_terrain)
    slope = slope_magnitude(height)
    moisture = moisture_proxy(height, slope)

    water, sand = generate_water_and_sand(height, slope, rng_hydro)

    roads, road_class = generate_roads(height, slope, water, rng_roads)

    surface, vegetation, zombies_30 = build_fields(
        height=height,
        slope=slope,
        moisture=moisture,
        water=water,
        sand=sand,
        roads=roads,
        road_class=road_class,
        rng=rng_fields,
    )

    slice_and_export(
        out_dir=out_dir,
        cells_x=cfg.cells_x,
        cells_y=cfg.cells_y,
        cell_size=cfg.cell_size,
        surface=surface,
        vegetation=vegetation,
        zombies_30=zombies_30,
        prefix="pz",
        write_master=True,
    )