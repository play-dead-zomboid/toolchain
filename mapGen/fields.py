from __future__ import annotations

import numpy as np
from util import hex_rgb, clamp01, normalize01, max_filter
from noise import fbm

# --- Exact surface palette (hex you gave) ---
SURF = {
    "DARK_GRASS": hex_rgb("5a6423"),
    "MED_GRASS": hex_rgb("75752f"),
    "LIGHT_GRASS": hex_rgb("91873c"),
    "SAND": hex_rgb("d2c8a0"),
    "ASPHALT_DARK": hex_rgb("646464"),
    "ASPHALT_MED": hex_rgb("787878"),
    "ASPHALT_LIGHT": hex_rgb("a5a08c"),
    "DIRT": hex_rgb("784614"),
    "WATER": hex_rgb("008aff"),
    "POTHOLE_DARK": hex_rgb("6e6464"),
    "POTHOLE_LIGHT": hex_rgb("827878"),
}

# --- Exact vegetation palette (hex you gave) ---
VEG = {
    "TALL_GRASS": hex_rgb("00ff00"),
    "TREES": hex_rgb("ff0000"),
    "TREES_DG": hex_rgb("7f0000"),
    "LESS_TREES": hex_rgb("400000"),
    "LOT_GRASS_TREES": hex_rgb("008000"),
    "BUSH_TREES_DG": hex_rgb("ff00ff"),
}


def _distance_approx(binary: np.ndarray, iters: int) -> np.ndarray:
    """
    Cheap distance-like field: iterative expansion.
    Output is "steps to reach binary == True", clipped.
    """
    h, w = binary.shape
    dist = np.full((h, w), 9999, dtype=np.int32)
    frontier = binary.astype(bool, copy=False)
    dist[frontier] = 0
    for i in range(1, iters + 1):
        pad = np.pad(frontier.astype(np.uint8), 1, mode="edge")
        neigh = (
            pad[0:h, 0:w] | pad[0:h, 1 : w + 1] | pad[0:h, 2 : w + 2]
            | pad[1 : h + 1, 0:w] | pad[1 : h + 1, 1 : w + 1] | pad[1 : h + 1, 2 : w + 2]
            | pad[2 : h + 2, 0:w] | pad[2 : h + 2, 1 : w + 1] | pad[2 : h + 2, 2 : w + 2]
        ).astype(bool)
        new = neigh & (dist > 9000)
        if not new.any():
            break
        dist[new] = i
        frontier = new
    return dist.astype(np.float32)


def build_fields(
    height: np.ndarray,
    slope: np.ndarray,
    moisture: np.ndarray,
    water: np.ndarray,
    sand: np.ndarray,
    roads: np.ndarray,
    road_class: np.ndarray,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Outputs:
      surface RGB (H,W,3)
      vegetation RGB (H,W,3)
      zombies 30x30 (H/10, W/10) uint8
    """
    h, w = height.shape

    # ----- Road materials (3 asphalts + potholes) -----
    is_road = roads > 0.2
    arterial = (road_class == 1) & is_road
    secondary = (road_class == 2) & is_road
    tertiary = (road_class == 3) & is_road

    # Wear field -> potholes: more likely on tertiary/secondary than arterial
    wear_noise = fbm(w, h, base_grid=38, octaves=3, lacunarity=2.0, gain=0.55, rng=rng)
    wear_noise = normalize01(wear_noise)
    dist_to_arterial = _distance_approx(arterial, iters=120)
    dist_to_arterial = normalize01(dist_to_arterial)

    wear = clamp01(0.55 * wear_noise + 0.45 * dist_to_arterial)
    wear += tertiary.astype(np.float32) * 0.20
    wear += secondary.astype(np.float32) * 0.10
    wear -= arterial.astype(np.float32) * 0.15
    wear = clamp01(wear)

    pothole_light = is_road & (wear > 0.62)
    pothole_dark = is_road & (wear > 0.78)

    # ----- Grass tones (must use all 3) -----
    # Bias by elevation + moisture: higher -> lighter; lower/wetter -> darker
    gscore = clamp01(0.60 * height + 0.40 * (1.0 - moisture))
    # subtle sharpening so bands appear
    gscore = clamp01(0.5 * gscore + 0.5 * (gscore * gscore))

    grass_dark = gscore < 0.33
    grass_med = (gscore >= 0.33) & (gscore < 0.66)
    grass_light = gscore >= 0.66

    # Dirt: slightly steeper, not water/sand/roads
    dirt = (slope > 0.55) & (~water) & (~sand) & (~is_road)

    # ----- Surface -----
    surface = np.zeros((h, w, 3), dtype=np.uint8)

    # base grass
    surface[grass_dark] = SURF["DARK_GRASS"]
    surface[grass_med] = SURF["MED_GRASS"]
    surface[grass_light] = SURF["LIGHT_GRASS"]

    # overlays
    surface[sand] = SURF["SAND"]
    surface[dirt] = SURF["DIRT"]
    surface[water] = SURF["WATER"]

    # asphalt by class
    surface[tertiary] = SURF["ASPHALT_DARK"]
    surface[secondary] = SURF["ASPHALT_MED"]
    surface[arterial] = SURF["ASPHALT_LIGHT"]

    # potholes override asphalt
    surface[pothole_light] = SURF["POTHOLE_LIGHT"]
    surface[pothole_dark] = SURF["POTHOLE_DARK"]

        # ----- Vegetation: layered + percentile banding (fixed) -----

    # Distance-to-road influence (gradual, not binary suppression)
    dist_to_roads = _distance_approx(is_road, iters=140)
    dist_to_roads = normalize01(dist_to_roads)

    # Smooth human influence field
    human_influence = np.exp(-dist_to_roads * 4.0).astype(np.float32)

    # Independent correlated noise components
    noise_canopy = normalize01(
        fbm(w, h, base_grid=52, octaves=3, lacunarity=2.0, gain=0.55, rng=rng)
    )
    noise_shrub = normalize01(
        fbm(w, h, base_grid=36, octaves=2, lacunarity=2.0, gain=0.5, rng=rng)
    )

    # Base densities
    grass_density = clamp01(0.65 * moisture + 0.35 * (1.0 - height))
    canopy_density = clamp01(0.6 * moisture + 0.4 * noise_canopy)
    shrub_density = clamp01(0.5 * moisture + 0.5 * noise_shrub)

    # Gradual attenuation near roads
    canopy_density *= (1.0 - 0.55 * human_influence)
    shrub_density *= (1.0 - 0.35 * human_influence)

    # Suppress vegetation in water and sand
    grass_density[water | sand] = 0.0
    shrub_density[water | sand] = 0.0
    canopy_density[water | sand] = 0.0

    # --- Percentile-based banding to guarantee all 6 colors are used ---

    c_lo = np.quantile(canopy_density, 0.35)
    c_mid = np.quantile(canopy_density, 0.55)
    c_hi = np.quantile(canopy_density, 0.75)

    s_mid = np.quantile(shrub_density, 0.60)
    g_hi = np.quantile(grass_density, 0.65)

    vegetation = np.zeros((h, w, 3), dtype=np.uint8)

    # Tall grass (pure grass dominance)
    tall_grass = (grass_density > g_hi) & (canopy_density < c_lo)

    # Less trees, more grass
    less_trees = (canopy_density >= c_lo) & (canopy_density < c_mid)

    # Trees + dark grass
    trees_dg = (canopy_density >= c_mid) & (canopy_density < c_hi) & grass_dark

    # Full trees
    trees = canopy_density >= c_hi

    # Lots of grass + trees
    lot_grass_trees = (trees) & (grass_density > g_hi)

    # Bushes + trees + dark grass
    bush_trees_dg = (
        (shrub_density > s_mid)
        & (canopy_density >= c_mid)
        & grass_dark
    )

    vegetation[tall_grass] = VEG["TALL_GRASS"]
    vegetation[less_trees] = VEG["LESS_TREES"]
    vegetation[trees_dg] = VEG["TREES_DG"]
    vegetation[trees] = VEG["TREES"]
    vegetation[lot_grass_trees] = VEG["LOT_GRASS_TREES"]
    vegetation[bush_trees_dg] = VEG["BUSH_TREES_DG"]
    vegetation[is_road] = (0, 0, 0)

    # ----- Zombies 30x30 -----
    # Derived from human footprint: roads + lower canopy + proximity to roads; water zero
    z = (
        0.55 * normalize01(roads)
        + 0.25 * (1.0 - canopy_density)
        + 0.20 * (1.0 - dist_to_roads)
    ).astype(np.float32)
    z[water] = 0.0
    z = normalize01(z)

    # downsample to 30x30 per 300x300 cell -> assumes 10px per zombie pixel
    z30 = z.reshape(h // 10, 10, w // 10, 10).mean(axis=(1, 3))
    z30_u8 = (z30 * 255.0).clip(0, 255).astype(np.uint8)

    return surface, vegetation, z30_u8