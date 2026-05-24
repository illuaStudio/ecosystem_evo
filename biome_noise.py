"""2D ノイズサンプリング（noise パッケージがあれば Perlin、なければ簡易フラクタル）。"""
import math
from typing import Callable


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


def simple_fractal_noise2d(
    x: float,
    y: float,
    *,
    octaves: int = 4,
    persistence: float = 0.55,
    lacunarity: float = 2.2,
    seed: int = 0,
) -> float:
    """おおよそ [-1, 1] の簡易フラクタルノイズ。"""
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


def make_noise_sampler(
    *,
    scale: float = 0.018,
    octaves: int = 4,
    persistence: float = 0.55,
    lacunarity: float = 2.2,
    seed: int = 0,
) -> Callable[[float, float], float]:
    """ワールド座標 (x, y) → 0.0〜1.0 のノイズ値を返すサンプラーを作る。"""
    try:
        from noise import pnoise2

        def sample(x: float, y: float) -> float:
            v = pnoise2(
                x * scale,
                y * scale,
                octaves=octaves,
                persistence=persistence,
                lacunarity=lacunarity,
                repeatx=4096,
                repeaty=4096,
                base=seed,
            )
            return (float(v) + 1.0) * 0.5

        return sample
    except ImportError:
        def sample(x: float, y: float) -> float:
            v = simple_fractal_noise2d(
                x * scale,
                y * scale,
                octaves=octaves,
                persistence=persistence,
                lacunarity=lacunarity,
                seed=seed,
            )
            return (v + 1.0) * 0.5

        return sample
