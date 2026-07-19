from generate_region import generate_and_export
import secrets
global_seed = secrets.randbits(64)
generate_and_export(global_seed=global_seed , cells_x=2, cells_y=2, out_dir="./out")