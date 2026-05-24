"""Perlin ノイズによるバイオーム判定（rich / poor）。"""
import math
from typing import Literal

BiomeType = Literal["rich", "poor"]

try:
    from noise import pnoise2 as _perlin_noise2d
    _HAS_NOISE_LIB = True
except ImportError:
    _perlin_noise2d = None
    _HAS_NOISE_LIB = False


def _hash2d(ix: int, iy: int, seed: int) -> float:
    n = ix * 374761393 + iy * 668265263 + seed * 982451653
    n = (n ^ (n >> 13)) * 1274126177
    n = n ^ (n >> 16)
    return (n & 0x7FFFFFFF) / 0x7FFFFFFF


def _smooth(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def _value_noise(x: float, y: float, seed: int) -> float:
    x0, y0 = int(math.floor(x)), int(math.floor(y))
    x1, y1 = x0 + 1, y0 + 1
    sx = _smooth(x - x0)
    sy = _smooth(y - y0)

    n00 = _hash2d(x0, y0, seed)
    n10 = _hash2d(x1, y0, seed)
    n01 = _hash2d(x0, y1, seed)
    n11 = _hash2d(x1, y1, seed)

    ix0 = n00 + (n10 - n00) * sx
    ix1 = n01 + (n11 - n01) * sx
    return ix0 + (ix1 - ix0) * sy


def _fallback_fractal_noise2d(
    x: float,
    y: float,
    *,
    octaves: int,
    persistence: float,
    lacunarity: float,
    seed: int,
) -> float:
    """noise 未インストール時の簡易フラクタル（おおよそ [-1, 1]）。"""
    total = 0.0
    amplitude = 1.0
    frequency = 1.0
    max_amp = 0.0
    for _ in range(max(1, octaves)):
        total += (_value_noise(x * frequency, y * frequency, seed) * 2.0 - 1.0) * amplitude
        max_amp += amplitude
        amplitude *= persistence
        frequency *= lacunarity
    if max_amp <= 0:
        return 0.0
    return max(-1.0, min(1.0, total / max_amp))


class BiomeNoise:
    """Perlin ノイズでワールド座標のバイオーム（rich / poor）を決定する。"""

    def __init__(
        self,
        *,
        scale: float = 0.018,
        octaves: int = 4,
        persistence: float = 0.55,
        lacunarity: float = 2.2,
        threshold: float = 0.5,
        seed: int = 0,
    ):
        self.scale = float(scale)
        self.octaves = int(octaves)
        self.persistence = float(persistence)
        self.lacunarity = float(lacunarity)
        self.threshold = float(threshold)
        self.seed = int(seed)
        self._use_perlin = _HAS_NOISE_LIB

    def get_noise_value(self, x: float, y: float) -> float:
        """ワールド座標のノイズ値を 0.0〜1.0 で返す。"""
        nx = float(x) * self.scale
        ny = float(y) * self.scale

        if self._use_perlin:
            raw = _perlin_noise2d(
                nx,
                ny,
                octaves=self.octaves,
                persistence=self.persistence,
                lacunarity=self.lacunarity,
                repeatx=4096,
                repeaty=4096,
                base=self.seed,
            )
        else:
            raw = _fallback_fractal_noise2d(
                nx,
                ny,
                octaves=self.octaves,
                persistence=self.persistence,
                lacunarity=self.lacunarity,
                seed=self.seed,
            )

        return max(0.0, min(1.0, (float(raw) + 1.0) * 0.5))

    def get_biome_type(self, x: float, y: float) -> BiomeType:
        """ノイズが threshold 以上なら rich、未満なら poor。"""
        if self.get_noise_value(x, y) >= self.threshold:
            return "rich"
        return "poor"

    @classmethod
    def from_config(cls, cfg: dict, *, default_seed: int = 0) -> "BiomeNoise":
        """world.json の biome_noise セクションから生成。"""
        return cls(
            scale=float(cfg.get("scale", 0.018)),
            octaves=int(cfg.get("octaves", 4)),
            persistence=float(cfg.get("persistence", 0.55)),
            lacunarity=float(cfg.get("lacunarity", 2.2)),
            threshold=float(cfg.get("threshold", 0.5)),
            seed=int(cfg.get("seed", default_seed)),
        )
