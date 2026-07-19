import hashlib
import numpy as np

def _u64_from_hash(s: bytes) -> int:
    h = hashlib.blake2b(s, digest_size=8).digest()
    return int.from_bytes(h, "little", signed=False)

def make_rng(global_seed: int, stream: str) -> np.random.Generator:
    # Stable per-stream RNG derived from global_seed + stream label
    key = f"{global_seed}:{stream}".encode("utf-8")
    seed64 = _u64_from_hash(key)
    return np.random.default_rng(seed64)