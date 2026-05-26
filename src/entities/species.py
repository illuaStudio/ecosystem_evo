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
    "hunger_threshold",
    "starvation_threshold",
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
    "hunger_threshold": 0.50,
    "starvation_threshold": 0.72,
}


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
    """JSON の traits を身体特性のみに正規化し、欠損キーにデフォルトを補う。"""
    traits = {k: raw[k] for k in ESSENTIAL_TRAIT_KEYS if k in raw}
    for key, default in TRAIT_DEFAULTS.items():
        traits.setdefault(key, default)
    # max_size 未指定時は base_size と同じ（成長なし種用）
    if "max_size" not in raw and "base_size" in raw:
        traits["max_size"] = float(raw["base_size"])
    return traits


class Species:
    @classmethod
    def create(cls, name: str = "Amoeba"):
        data = config.get_species(name)
        return cls(data)

    def __init__(self, data: dict):
        self.name = data["name"]
        self.color = tuple(data.get("color", [120, 200, 120]))
        self.traits = normalize_traits(data.get("traits", {}))
        self.life_cycle = normalize_life_cycle(data.get("life_cycle", {}))
        self.mind_data = data.get("mind", {"type": "priority", "actions": []})
        self.colony_data = data.get("colony", {})
        self.description = data.get("description", "")
