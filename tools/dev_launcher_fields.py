"""開発ランチャー用: 設定項目定義と JSON 読み書き。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

PathKey = str | int
ValueType = Literal["float", "int", "bool"]


@dataclass(frozen=True)
class FieldSpec:
    """1つの調整可能な設定項目。"""

    field_id: str
    category: str
    label: str
    help_text: str
    config_relpath: str
    value_type: ValueType
    json_path: tuple[PathKey, ...] = ()
    action_name: str = ""
    param_name: str = ""
    profile_id: str = ""
    handler: str = ""
    min_val: float | None = None
    max_val: float | None = None


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def config_path(relpath: str) -> Path:
    return project_root() / "config" / relpath


def load_json(relpath: str) -> dict:
    path = config_path(relpath)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(relpath: str, data: dict) -> None:
    path = config_path(relpath)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _get_nested(data: Any, path: tuple[PathKey, ...]) -> Any:
    cur: Any = data
    for key in path:
        if cur is None:
            return None
        if isinstance(key, int):
            if not isinstance(cur, list) or key < 0 or key >= len(cur):
                return None
            cur = cur[key]
        elif isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return None
    return cur


def _set_nested(data: dict, path: tuple[PathKey, ...], value: Any) -> None:
    cur: Any = data
    for key in path[:-1]:
        if not isinstance(key, str):
            raise TypeError(f"通常パスは str のみです: {path}")
        nxt = cur.setdefault(key, {})
        if not isinstance(nxt, dict):
            raise TypeError(f"パス {path} の途中が dict ではありません")
        cur = nxt
    last = path[-1]
    if not isinstance(last, str):
        raise TypeError(f"通常パスは str のみです: {path}")
    cur[last] = value


def _default_inventory_slot(max_mass: float = 100.0) -> dict:
    return {"max_mass": max_mass, "allowed_kinds": ["biomass"]}


def _read_inventory_handler(data: dict, handler: str) -> Any:
    inv = data.get("inventory") or {}
    slots = list(inv.get("slots") or [])
    if handler == "inventory_slot_count":
        if "slot_count" in inv:
            return int(inv["slot_count"])
        return len(slots)
    if handler == "inventory_uniform_slot_max_mass":
        if not slots:
            return None
        return float(slots[0].get("max_mass", 100.0))
    raise KeyError(f"未知の handler: {handler}")


def _write_inventory_handler(data: dict, handler: str, value: Any) -> None:
    inv = data.setdefault("inventory", {})
    slots = list(inv.get("slots") or [])
    if handler == "inventory_slot_count":
        count = max(0, int(value))
        inv["slot_count"] = count
        default_mass = 100.0
        if slots:
            default_mass = float(slots[0].get("max_mass", 100.0))
        while len(slots) < count:
            slots.append(_default_inventory_slot(default_mass))
        inv["slots"] = slots[:count]
        return
    if handler == "inventory_uniform_slot_max_mass":
        mass = max(0.0, float(value))
        if not slots:
            count = int(inv.get("slot_count", 1))
            slots = [_default_inventory_slot(mass) for _ in range(max(1, count))]
        else:
            for slot in slots:
                slot["max_mass"] = mass
        inv["slots"] = slots
        if "slot_count" not in inv:
            inv["slot_count"] = len(slots)
        return
    raise KeyError(f"未知の handler: {handler}")


def _find_action(data: dict, action_name: str, *, profile_id: str = "") -> dict | None:
    if profile_id:
        actions = data.get(profile_id, {}).get("actions") or []
    else:
        actions = data.get("mind", {}).get("actions") or []
    for action in actions:
        if action.get("name") == action_name:
            return action
    return None


def read_field_value(spec: FieldSpec) -> Any:
    data = load_json(spec.config_relpath)
    if spec.handler:
        return _read_inventory_handler(data, spec.handler)
    if spec.action_name and spec.param_name:
        action = _find_action(data, spec.action_name, profile_id=spec.profile_id)
        if action is None:
            return None
        return (action.get("params") or {}).get(spec.param_name)
    return _get_nested(data, spec.json_path)


def write_field_value(spec: FieldSpec, value: Any) -> None:
    data = load_json(spec.config_relpath)
    if spec.handler:
        _write_inventory_handler(data, spec.handler, value)
    elif spec.action_name and spec.param_name:
        action = _find_action(data, spec.action_name, profile_id=spec.profile_id)
        if action is None:
            raise KeyError(
                f"{spec.config_relpath} に {spec.action_name} が見つかりません"
            )
        action.setdefault("params", {})[spec.param_name] = value
    else:
        _set_nested(data, spec.json_path, value)
    save_json(spec.config_relpath, data)


def coerce_value(spec: FieldSpec, raw: str) -> Any:
    if spec.value_type == "bool":
        return raw in (True, "1", "true", "True", 1)
    if spec.value_type == "int":
        return int(float(raw))
    return float(raw)


def categories() -> list[str]:
    seen: list[str] = []
    for spec in FIELD_SPECS:
        if spec.category not in seen:
            seen.append(spec.category)
    return seen


def fields_for_category(category: str) -> list[FieldSpec]:
    return [s for s in FIELD_SPECS if s.category == category]


FIELD_SPECS: list[FieldSpec] = [
    FieldSpec(
        "queen_max_hp",
        "女王",
        "最大 HP",
        "女王の体力上限。低いと外敵や環境ダメージで早く倒れます。",
        "sim/species/red_ant_queen.json",
        "float",
        ("traits", "max_hp"),
        min_val=50,
        max_val=2000,
    ),
    FieldSpec(
        "queen_max_satiety",
        "女王",
        "最大満腹度",
        "女王が保持できる栄養の上限。巣の備蓄から食事して回復します。",
        "sim/species/red_ant_queen.json",
        "float",
        ("traits", "max_satiety"),
        min_val=50,
        max_val=500,
    ),
    FieldSpec(
        "queen_metabolism",
        "女王",
        "代謝率",
        "1 tick あたりの満腹度減少。高いほど巣の食料を早く消費し、"
        "満腹0%時の HP ダメージ（×飢餓倍率）も大きくなります。",
        "sim/species/red_ant_queen.json",
        "float",
        ("traits", "metabolism_rate"),
        min_val=0.001,
        max_val=0.2,
    ),
    FieldSpec(
        "queen_hp_regen_mult",
        "女王",
        "HP 回復倍率",
        "テリトリー・環境由来の HP 回復に乗算される倍率（未設定時 1.0）。"
        "0 にするとテリトリー回復を受けず、飢餓で HP が減りやすくなります。",
        "sim/species/red_ant_queen.json",
        "float",
        ("traits", "hp_regen_mult"),
        min_val=0.0,
        max_val=2.0,
    ),
    FieldSpec(
        "queen_starvation_hp_mult",
        "女王",
        "飢餓 HP ダメージ倍率",
        "満腹0%で満腹度がマイナスになった超過分×この値が HP ダメージ。"
        "毎 tick 目安 ≈ 代謝率×倍率（例: 0.1×0.12=0.012）。未設定時はシミュ共通の既定値。",
        "sim/species/red_ant_queen.json",
        "float",
        ("traits", "starvation_hp_mult"),
        min_val=0.0,
        max_val=2.0,
    ),
    FieldSpec(
        "queen_hungry_below",
        "女王",
        "飢餓閾値（満腹率）",
        "満腹度がこの割合を下回ると食事が必要と判断し、FeedAtNest が優先されます。",
        "sim/species/red_ant_queen.json",
        "float",
        ("traits", "satiety_hungry_below"),
        min_val=0.05,
        max_val=0.5,
    ),
    FieldSpec(
        "queen_full_above",
        "女王",
        "満腹閾値（満腹率）",
        "満腹度がこの割合を超えると十分食べたとみなし、産卵など他行動が選ばれやすくなります。",
        "sim/species/red_ant_queen.json",
        "float",
        ("traits", "satiety_full_above"),
        min_val=0.5,
        max_val=1.0,
    ),
    FieldSpec(
        "queen_nest_food_init",
        "女王",
        "巣の初期備蓄",
        "ゲーム開始時に巣に入っている食料量。少ないと女王がすぐ飢え、進行が遅れます。",
        "sim/worlds/world.json",
        "float",
        ("colony", "profiles", "red_ant", "initial_stored_food"),
        min_val=0,
        max_val=5000,
    ),
    FieldSpec(
        "queen_nest_food_max",
        "女王",
        "巣の食料上限",
        "巣に貯められる食料の最大量。働きアリの持ち帰り上限にも影響します。",
        "sim/worlds/world.json",
        "float",
        ("colony", "profiles", "red_ant", "max_food"),
        min_val=500,
        max_val=20000,
    ),
    FieldSpec(
        "queen_food_leak",
        "女王",
        "食料漏洩率",
        "備蓄が一定以上あるとき、毎 tick マナへ漏れる割合。高いほど余剰食料が消えやすい。",
        "sim/worlds/world.json",
        "float",
        ("colony", "profiles", "red_ant", "food_leak_rate"),
        min_val=0.0,
        max_val=0.01,
    ),
    FieldSpec(
        "queen_init_feed_bite",
        "女王",
        "初期・巣での食事量",
        "解禁前（survival_feed_only）の女王が1回で回復する満腹度。ゲーム序盤の生存速度に影響。",
        "game/reproduction_profiles.json",
        "float",
        action_name="FeedAtNestAction",
        param_name="bite_gain",
        profile_id="survival_feed_only",
        min_val=0.5,
        max_val=5.0,
    ),
    FieldSpec(
        "queen_territory",
        "女王",
        "テリトリー半径",
        "コロニー勢力圏の半径（px）。大きいほど自勢力エリアが広がります。",
        "sim/worlds/world.json",
        "float",
        ("colony", "profiles", "red_ant", "territory_radius"),
        min_val=50,
        max_val=400,
    ),
    FieldSpec(
        "queen_feed_bite",
        "女王",
        "巣での1回の食事量",
        "FeedAtNestAction の bite_gain。1回の食事で回復する満腹度。",
        "game/reproduction_profiles.json",
        "float",
        action_name="FeedAtNestAction",
        param_name="bite_gain",
        profile_id="queen_feed_and_workers",
        min_val=0.5,
        max_val=5.0,
    ),
    FieldSpec(
        "queen_feed_ratio",
        "女王",
        "巣食事の最大取得率",
        "1回の食事で巣備蓄から取れる最大割合（max_take_ratio）。",
        "game/reproduction_profiles.json",
        "float",
        action_name="FeedAtNestAction",
        param_name="max_take_ratio",
        profile_id="queen_feed_and_workers",
        min_val=0.01,
        max_val=0.5,
    ),
    FieldSpec(
        "queen_repro_food_cost",
        "女王",
        "産卵の食料コスト",
        "働きアリ1匹を産むときに巣から消費する食料量。",
        "game/reproduction_profiles.json",
        "float",
        action_name="ColonyReproduceAction",
        param_name="food_cost",
        profile_id="queen_feed_and_workers",
        min_val=10,
        max_val=200,
    ),
    FieldSpec(
        "queen_repro_reserve",
        "女王",
        "最低食料備蓄",
        "巣穴設置・産卵の両方で、操作後も残しておく必要がある食料。",
        "sim/worlds/world.json",
        "float",
        ("colony", "min_food_reserve"),
        min_val=0,
        max_val=500,
    ),
    FieldSpec(
        "queen_repro_max_members",
        "女王",
        "コロニー個体上限（産卵）",
        "この数を超えると女王は産卵を止めます（member_species の合計）。",
        "game/reproduction_profiles.json",
        "int",
        action_name="ColonyReproduceAction",
        param_name="max_colony_members",
        profile_id="queen_feed_and_workers",
        min_val=1,
        max_val=50,
    ),
    FieldSpec(
        "queen_repro_cooldown",
        "女王",
        "産卵クールダウン（tick）",
        "1匹産んだあと、次の産卵まで待つ tick 数。小さいほど増殖が速い。",
        "game/reproduction_profiles.json",
        "int",
        action_name="ColonyReproduceAction",
        param_name="spawn_cooldown",
        profile_id="queen_feed_and_workers",
        min_val=60,
        max_val=5000,
    ),
    FieldSpec(
        "queen_repro_radius",
        "女王",
        "産卵位置半径",
        "巣の中心から子個体がスポーンする距離。",
        "game/reproduction_profiles.json",
        "float",
        action_name="ColonyReproduceAction",
        param_name="spawn_radius",
        profile_id="queen_feed_and_workers",
        min_val=10,
        max_val=120,
    ),
    FieldSpec(
        "worker_speed",
        "働きアリ",
        "移動速度（空荷）",
        "基本移動速度（traits.base_speed）。運搬中は別パラメータで減速します。",
        "sim/species/red_ant.json",
        "float",
        ("traits", "base_speed"),
        min_val=0.1,
        max_val=2.0,
    ),
    FieldSpec(
        "worker_carry_speed_ref",
        "働きアリ",
        "運搬減速の参照重量",
        "速度倍率 = 1 / (1 + 総重量 / 参照重量)。"
        "大きいほど同じ荷重でも速い（減衰が弱い）。例: 重量80・参照80 → 速度50%。",
        "sim/species/red_ant.json",
        "float",
        ("inventory", "carry_speed_reference_weight"),
        min_val=10,
        max_val=300,
    ),
    FieldSpec(
        "worker_biomass_weight",
        "働きアリ",
        "バイオマス単位重量",
        "運搬量1あたりの重量。大きいほど同量の餌でより遅くなる。",
        "sim/species/red_ant.json",
        "float",
        ("inventory", "biomass_weight_per_unit"),
        min_val=0.1,
        max_val=5.0,
    ),
    FieldSpec(
        "worker_inv_slot_count",
        "働きアリ",
        "インベントリ枠数",
        "運搬スロット数。増やすと一度に拾える死骸チャンクが増えます。",
        "sim/species/red_ant.json",
        "int",
        handler="inventory_slot_count",
        min_val=1,
        max_val=6,
    ),
    FieldSpec(
        "worker_inv_slot_max_mass",
        "働きアリ",
        "スロット上限（各枠）",
        "各スロットに入るバイオマス量の上限。全スロットに同じ値を設定します。",
        "sim/species/red_ant.json",
        "float",
        handler="inventory_uniform_slot_max_mass",
        min_val=10,
        max_val=300,
    ),
    FieldSpec(
        "worker_vision",
        "働きアリ",
        "視界",
        "獲物や死骸を探せる距離。広いほど効率的に狩れます。",
        "sim/species/red_ant.json",
        "float",
        ("traits", "base_vision"),
        min_val=80,
        max_val=500,
    ),
    FieldSpec(
        "worker_max_hp",
        "働きアリ",
        "最大 HP",
        "働きアリの体力。敵や毒エリアでの生存力に影響します。",
        "sim/species/red_ant.json",
        "float",
        ("traits", "max_hp"),
        min_val=20,
        max_val=500,
    ),
    FieldSpec(
        "worker_max_satiety",
        "働きアリ",
        "最大満腹度",
        "満腹度上限。高いほど長く外回りできます。",
        "sim/species/red_ant.json",
        "float",
        ("traits", "max_satiety"),
        min_val=30,
        max_val=300,
    ),
    FieldSpec(
        "worker_metabolism",
        "働きアリ",
        "代謝率",
        "毎 tick の満腹度減少。高いほどこまめに食事が必要です。",
        "sim/species/red_ant.json",
        "float",
        ("traits", "metabolism_rate"),
        min_val=0.01,
        max_val=0.2,
    ),
    FieldSpec(
        "worker_hp_regen_mult",
        "働きアリ",
        "HP 回復倍率",
        "テリトリー・環境由来の HP 回復に乗算される倍率（未設定時 1.0）。",
        "sim/species/red_ant.json",
        "float",
        ("traits", "hp_regen_mult"),
        min_val=0.0,
        max_val=2.0,
    ),
    FieldSpec(
        "worker_starvation_hp_mult",
        "働きアリ",
        "飢餓 HP ダメージ倍率",
        "満腹0%以降、超過した満腹度×この値が HP ダメージ。"
        "未設定時はシミュ共通の既定値を使用。",
        "sim/species/red_ant.json",
        "float",
        ("traits", "starvation_hp_mult"),
        min_val=0.0,
        max_val=2.0,
    ),
    FieldSpec(
        "worker_hunt_attack",
        "働きアリ",
        "狩り攻撃力",
        "HuntAction の attack_power。アメーバなどを倒す速さに影響。",
        "sim/species/red_ant.json",
        "float",
        action_name="HuntAction",
        param_name="attack_power",
        min_val=0.5,
        max_val=5.0,
    ),
    FieldSpec(
        "worker_hunt_speed",
        "働きアリ",
        "狩り移動倍率",
        "HuntAction 中の移動速度倍率。",
        "sim/species/red_ant.json",
        "float",
        action_name="HuntAction",
        param_name="speed_multiplier",
        min_val=0.5,
        max_val=3.0,
    ),
    FieldSpec(
        "worker_hunt_bite",
        "働きアリ",
        "狩り時の食事回復",
        "狩り中にその場で食べたときの満腹回復量（bite_gain）。",
        "sim/species/red_ant.json",
        "float",
        action_name="HuntAction",
        param_name="bite_gain",
        min_val=0.5,
        max_val=5.0,
    ),
    FieldSpec(
        "worker_deposit_radius",
        "働きアリ",
        "巣への搬入半径",
        "ReturnToNestAction の deposit_radius。この距離内で備蓄に入れます。",
        "sim/species/red_ant.json",
        "float",
        action_name="ReturnToNestAction",
        param_name="deposit_radius",
        min_val=10,
        max_val=80,
    ),
    FieldSpec(
        "worker_patrol_radius",
        "働きアリ",
        "巣周辺巡回半径",
        "NestPatrolAction の patrol_radius。巣から離れすぎない範囲。",
        "sim/species/red_ant.json",
        "float",
        action_name="NestPatrolAction",
        param_name="patrol_radius",
        min_val=40,
        max_val=300,
    ),
    FieldSpec(
        "soldier_speed",
        "兵隊アリ",
        "移動速度",
        "基本移動速度。パトロール・戦闘・狩りの各 Action 倍率と組み合わさります。",
        "sim/species/red_ant_soldier.json",
        "float",
        ("traits", "base_speed"),
        min_val=0.1,
        max_val=2.0,
    ),
    FieldSpec(
        "soldier_vision",
        "兵隊アリ",
        "視界",
        "侵入者やクモを検知する距離。",
        "sim/species/red_ant_soldier.json",
        "float",
        ("traits", "base_vision"),
        min_val=80,
        max_val=500,
    ),
    FieldSpec(
        "soldier_max_hp",
        "兵隊アリ",
        "最大 HP",
        "兵隊アリの体力。防衛戦での耐久力。",
        "sim/species/red_ant_soldier.json",
        "float",
        ("traits", "max_hp"),
        min_val=20,
        max_val=500,
    ),
    FieldSpec(
        "soldier_max_satiety",
        "兵隊アリ",
        "最大満腹度",
        "満腹度上限。外回り（パトロール）の持続時間に影響。",
        "sim/species/red_ant_soldier.json",
        "float",
        ("traits", "max_satiety"),
        min_val=30,
        max_val=300,
    ),
    FieldSpec(
        "soldier_metabolism",
        "兵隊アリ",
        "代謝率",
        "毎 tick の満腹度減少。",
        "sim/species/red_ant_soldier.json",
        "float",
        ("traits", "metabolism_rate"),
        min_val=0.01,
        max_val=0.2,
    ),
    FieldSpec(
        "soldier_hp_regen_mult",
        "兵隊アリ",
        "HP 回復倍率",
        "テリトリー・環境由来の HP 回復倍率（未設定時 1.0）。",
        "sim/species/red_ant_soldier.json",
        "float",
        ("traits", "hp_regen_mult"),
        min_val=0.0,
        max_val=2.0,
    ),
    FieldSpec(
        "soldier_starvation_hp_mult",
        "兵隊アリ",
        "飢餓 HP ダメージ倍率",
        "満腹0%以降の HP ダメージ倍率。未設定時はシミュ共通既定。",
        "sim/species/red_ant_soldier.json",
        "float",
        ("traits", "starvation_hp_mult"),
        min_val=0.0,
        max_val=2.0,
    ),
    FieldSpec(
        "soldier_patrol_radius",
        "兵隊アリ",
        "防衛巡回半径",
        "NestPatrolAction の patrol_radius。テリトリー内の巡回範囲。",
        "sim/species/red_ant_soldier.json",
        "float",
        action_name="NestPatrolAction",
        param_name="patrol_radius",
        min_val=40,
        max_val=300,
    ),
    FieldSpec(
        "soldier_combat_attack",
        "兵隊アリ",
        "対コロニー戦闘攻撃力",
        "CombatAction の attack_power。他勢力アリとの戦闘。",
        "sim/species/red_ant_soldier.json",
        "float",
        action_name="CombatAction",
        param_name="attack_power",
        min_val=0.5,
        max_val=5.0,
    ),
    FieldSpec(
        "soldier_combat_speed",
        "兵隊アリ",
        "対コロニー戦闘移動倍率",
        "CombatAction の speed_multiplier。",
        "sim/species/red_ant_soldier.json",
        "float",
        action_name="CombatAction",
        param_name="speed_multiplier",
        min_val=0.5,
        max_val=3.0,
    ),
    FieldSpec(
        "soldier_hunt_attack",
        "兵隊アリ",
        "対クモ攻撃力",
        "HuntAction の attack_power。クモ排除の火力。",
        "sim/species/red_ant_soldier.json",
        "float",
        action_name="HuntAction",
        param_name="attack_power",
        min_val=0.5,
        max_val=6.0,
    ),
    FieldSpec(
        "soldier_hunt_speed",
        "兵隊アリ",
        "対クモ追跡移動倍率",
        "HuntAction の speed_multiplier。",
        "sim/species/red_ant_soldier.json",
        "float",
        action_name="HuntAction",
        param_name="speed_multiplier",
        min_val=0.5,
        max_val=3.0,
    ),
    FieldSpec(
        "world_amoeba",
        "ワールド開始",
        "初期アメーバ数",
        "開始時にスポーンするアメーバの数。食料源として働きアリの狩り対象。",
        "sim/worlds/world.json",
        "int",
        ("initial_entities", "Amoeba"),
        min_val=0,
        max_val=100,
    ),
    FieldSpec(
        "world_queen",
        "ワールド開始",
        "初期女王数",
        "通常は 1。プレイヤーコロニーの女王数。",
        "sim/worlds/world.json",
        "int",
        ("initial_entities", "red_ant_queen"),
        min_val=0,
        max_val=3,
    ),
    FieldSpec(
        "world_workers",
        "ワールド開始",
        "初期働きアリ数",
        "ゲーム開始時から外に出ている働きアリの数。",
        "sim/worlds/world.json",
        "int",
        ("initial_entities", "red_ant"),
        min_val=0,
        max_val=20,
    ),
    FieldSpec(
        "world_pop_red_ant",
        "ワールド開始",
        "働きアリ個体上限",
        "ワールド全体で同時に存在できる red_ant の上限。",
        "sim/worlds/world.json",
        "int",
        ("population_limits", "red_ant"),
        min_val=1,
        max_val=100,
    ),
    FieldSpec(
        "world_pop_soldier",
        "ワールド開始",
        "兵隊アリ個体上限",
        "red_ant_soldier の同時存在上限。",
        "sim/worlds/world.json",
        "int",
        ("population_limits", "red_ant_soldier"),
        min_val=0,
        max_val=50,
    ),
    FieldSpec(
        "world_hole_cost",
        "ワールド開始",
        "巣穴設置コスト",
        "右クリックで巣穴を追加するときに消費する食料。",
        "sim/worlds/world.json",
        "float",
        ("colony", "hole_food_cost"),
        min_val=50,
        max_val=1000,
    ),
    FieldSpec(
        "world_territory_hp_regen",
        "ワールド開始",
        "テリトリー HP 回復",
        "自コロニーのテリトリー内にいる個体の毎 tick HP 回復量。"
        "飢餓ダメージ（代謝×飢餓倍率）と同程度だと HP が減らなくなります。",
        "sim/worlds/world.json",
        "float",
        ("colony", "territory_effects", "hp_regen_per_dt"),
        min_val=0.0,
        max_val=0.05,
    ),
    FieldSpec(
        "game_low_food",
        "ゲーム進行",
        "低備蓄アラート閾値",
        "巣の備蓄率がこの値を下回ると「食料不足」警告が出ます（0.10 = 10%）。",
        "game/player.json",
        "float",
        ("monitor", "low_food_ratio"),
        min_val=0.01,
        max_val=0.5,
    ),
    FieldSpec(
        "game_high_food",
        "ゲーム進行",
        "繁殖解禁閾値",
        "備蓄率がこの値に達すると女王の産卵が解禁されます（0.50 = 50%）。",
        "game/player.json",
        "float",
        ("monitor", "high_food_ratio"),
        min_val=0.1,
        max_val=1.0,
    ),
    FieldSpec(
        "game_milestone_workers",
        "ゲーム進行",
        "兵隊解禁の働きアリ数",
        "コロニーの働きアリがこの数に達すると兵隊アリ産卵が解禁されます。",
        "game/player.json",
        "int",
        ("monitor", "milestone_workers"),
        min_val=1,
        max_val=30,
    ),
    FieldSpec(
        "sim_starvation_hp_mult",
        "シミュ共通",
        "飢餓 HP ダメージ倍率（既定）",
        "種別に starvation_hp_mult が無いときの共通既定。"
        "満腹0%で代謝により満腹度がマイナスになった分×この値が HP ダメージ。",
        "sim/defaults.json",
        "float",
        ("starvation_hp_mult",),
        min_val=0.0,
        max_val=1.0,
    ),
    FieldSpec(
        "client_debug_hud",
        "表示・デバッグ",
        "デバッグ HUD",
        "ゲーム画面上部にデバッグ情報を表示します。",
        "client/display.json",
        "bool",
        ("debug_hud",),
    ),
    FieldSpec(
        "client_debug_messages",
        "表示・デバッグ",
        "ゲームメッセージをコンソール出力",
        "進行メッセージをターミナルにも print します。",
        "client/display.json",
        "bool",
        ("debug_game_messages",),
    ),
    FieldSpec(
        "client_fps",
        "表示・デバッグ",
        "FPS 上限",
        "ゲームループの最大フレームレート。",
        "client/display.json",
        "int",
        ("fps",),
        min_val=15,
        max_val=120,
    ),
]
