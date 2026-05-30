import random

from src.config import config

# 身体的・基礎特性のみ（アクション固有値は mind.actions[].params へ）
ESSENTIAL_TRAIT_KEYS = frozenset({
    "base_size",
    "max_size",
    "growth_rate",
    "base_speed",
    "base_vision",
    "max_hp",
    "max_satiety",
    "metabolism_rate",
    "satiety_hungry_below",
    "satiety_full_above",
})

# ESSENTIAL に無くても JSON にあればcreature.traitsへ渡す（CorpseComponent 等が参照）
OPTIONAL_TRAIT_KEYS = frozenset({
    "corpse_decompose_rate",
    "poison_resist",
    "hp_regen_mult",
    "field_immunities",
})

TRAIT_DEFAULTS = {
    "base_size": 9.0,
    "max_size": 9.0,
    "growth_rate": 0.0,
    "base_speed": 1.0,
    "base_vision": 120.0,
    "max_hp": 100.0,
    "max_satiety": 80.0,
    "metabolism_rate": 0.5,
    "satiety_hungry_below": 0.15,
    "satiety_full_above": 0.85,
}

# 全種共通の個体差対象（詳細 UI の表示順と一致）
INDIVIDUAL_TRAIT_DISPLAY_ORDER = (
    "base_speed",
    "base_vision",
    "growth_rate",
    "metabolism_rate",
    "max_hp",
    "max_satiety",
)

# 種 JSON に trait_variance が無い場合の自動生成対象
DEFAULT_INDIVIDUAL_VARIANCE_KEYS = INDIVIDUAL_TRAIT_DISPLAY_ORDER

# 代表値に対する ± 割合（正規分布の std / min-max）
DEFAULT_VARIANCE_SPREAD = 0.12


def normalize_life_cycle(raw: dict) -> dict:
    """JSON の life_cycle を整数化（未指定種は空 dict）。"""
    if not raw:
        return {}
    return {k: int(v) for k, v in raw.items()}


# Amoeba JSON 例（成長=traits、寿命=life_cycle、分裂調整=SplitAction.params）:
# {
#   "life_cycle": { "mature": 280, "elder": 1800, "death": 3500 },
#   "traits": { "base_size": 9.0, "max_size": 18.0, "growth_rate": 0.008, ... },
#   "mind": { "actions": [{ "name": "SplitAction", "params": { "min_reproduce_size": 8.5, ... } }] }
# }


def normalize_traits(raw: dict) -> dict:
    """JSON の traits を正規化し、欠損キーにデフォルトを補う。"""
    allowed = ESSENTIAL_TRAIT_KEYS | OPTIONAL_TRAIT_KEYS
    traits = {k: raw[k] for k in allowed if k in raw}
    if "satiety_hungry_below" not in traits and "hunger_threshold" in raw:
        traits["satiety_hungry_below"] = 1.0 - float(raw["hunger_threshold"])
    for key, default in TRAIT_DEFAULTS.items():
        traits.setdefault(key, default)
    hungry = float(traits["satiety_hungry_below"])
    full = float(traits["satiety_full_above"])
    if full <= hungry:
        full = min(1.0, hungry + 0.05)
    traits["satiety_hungry_below"] = hungry
    traits["satiety_full_above"] = full
    # max_size 未指定時は base_size と同じ（成長なし種用）
    if "max_size" not in raw and "base_size" in raw:
        traits["max_size"] = float(raw["base_size"])
    return traits


def normalize_trait_variance(raw: dict) -> dict:
    """JSON の trait_variance を正規化（未指定種は空 dict）。"""
    if not raw:
        return {}
    result: dict = {}
    for key, spec in raw.items():
        if not isinstance(spec, dict):
            continue
        dist = spec.get("distribution", "uniform")
        if dist not in ("normal", "uniform"):
            continue
        entry: dict = {"distribution": dist}
        if dist == "normal":
            if "std" not in spec:
                continue
            entry["std"] = float(spec["std"])
        if "min" in spec:
            entry["min"] = float(spec["min"])
        if "max" in spec:
            entry["max"] = float(spec["max"])
        if dist == "uniform" and "min" not in entry and "max" not in entry:
            continue
        result[key] = entry
    return result


def _default_variance_spec(key: str, base: float) -> dict | None:
    """種テンプレート値から標準的な個体差 spec を生成。"""
    if base <= 0:
        return None
    if key == "growth_rate" and base <= 0:
        return None

    spread = DEFAULT_VARIANCE_SPREAD
    std = max(base * spread * 0.35, base * 1e-4)
    lo = base * (1.0 - spread)
    hi = base * (1.0 + spread)

    if key == "base_speed":
        lo = max(0.01, lo)
    elif key in ("max_hp", "max_satiety", "base_vision"):
        lo = max(0.0, lo)
    elif key == "metabolism_rate":
        lo = max(0.01, lo)
    elif key == "growth_rate":
        lo = max(0.0, lo)

    return {
        "distribution": "normal",
        "std": std,
        "min": lo,
        "max": hi,
    }


def build_default_trait_variance(traits: dict) -> dict:
    """全種に共通のデフォルト個体差（JSON 未指定時）。"""
    result: dict = {}
    for key in DEFAULT_INDIVIDUAL_VARIANCE_KEYS:
        if key not in traits:
            continue
        base = float(traits[key])
        if key == "growth_rate" and base <= 0:
            continue
        spec = _default_variance_spec(key, base)
        if spec is not None:
            result[key] = spec
    return result


def resolve_trait_variance(traits: dict, json_variance: dict) -> dict:
    """デフォルト個体差に JSON の trait_variance を上書きマージ。"""
    merged = build_default_trait_variance(traits)
    merged.update(json_variance)
    return merged


def _sample_trait_value(base: float, spec: dict, rng: random.Random) -> float:
    dist = spec["distribution"]
    if dist == "normal":
        value = rng.gauss(base, float(spec["std"]))
    else:
        lo = float(spec["min"])
        hi = float(spec["max"])
        if hi < lo:
            lo, hi = hi, lo
        value = rng.uniform(lo, hi)
    if "min" in spec:
        value = max(float(spec["min"]), value)
    if "max" in spec:
        value = min(float(spec["max"]), value)
    return value


def clamp_traits(traits: dict) -> dict:
    """サンプリング後の traits に物理制約を適用。"""
    result = dict(traits)
    if "base_size" in result and "max_size" in result:
        result["max_size"] = max(float(result["base_size"]), float(result["max_size"]))
    for key in (
        "growth_rate",
        "metabolism_rate",
        "base_vision",
        "max_hp",
        "max_satiety",
    ):
        if key in result:
            result[key] = max(0.0, float(result[key]))
    if "base_speed" in result:
        result["base_speed"] = max(0.01, float(result["base_speed"]))
    hungry = float(result.get("satiety_hungry_below", TRAIT_DEFAULTS["satiety_hungry_below"]))
    full = float(result.get("satiety_full_above", TRAIT_DEFAULTS["satiety_full_above"]))
    if full <= hungry:
        full = min(1.0, hungry + 0.05)
    result["satiety_hungry_below"] = hungry
    result["satiety_full_above"] = full
    return result


def sample_individual_traits(
    template_traits: dict,
    variance_spec: dict,
    rng: random.Random | None = None,
) -> dict:
    """種テンプレートから個体ごとの traits を独立サンプル（進化・継承なし）。"""
    rng = rng or random.Random()
    traits = dict(template_traits)
    for key, spec in variance_spec.items():
        if key not in traits:
            continue
        traits[key] = _sample_trait_value(float(traits[key]), spec, rng)
    return clamp_traits(traits)


class Species:
    @classmethod
    def create(cls, name: str = "Amoeba"):
        data = config.get_species(name)
        return cls(data)

    def __init__(self, data: dict):
        self.name = data["name"]
        self.color = tuple(data.get("color", [120, 200, 120]))
        self.traits = normalize_traits(data.get("traits", {}))
        json_variance = normalize_trait_variance(data.get("trait_variance", {}))
        self.trait_variance = resolve_trait_variance(self.traits, json_variance)
        self.life_cycle = normalize_life_cycle(data.get("life_cycle", {}))
        self.mind_data = data.get("mind", {"type": "priority", "actions": []})
        self.colony_data = data.get("colony", {})
        self.description = data.get("description", "")
