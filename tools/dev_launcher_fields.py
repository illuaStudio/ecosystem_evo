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
    """トップレベルタブ名（種・ワールド等）。"""
    return launcher_tabs()


def fields_for_category(category: str) -> list[FieldSpec]:
    """カテゴリ内の全項目（後方互換）。"""
    return [s for s in FIELD_SPECS if s.category == category]


_NESTED_AI_CATEGORIES: frozenset[str] = frozenset({"女王", "働きアリ", "兵隊アリ"})

_STATIC_TAB_ORDER: tuple[str, ...] = (
    "女王",
    "働きアリ",
    "兵隊アリ",
    "ワールド",
    "ゲーム進行",
    "シミュ共通",
    "表示・デバッグ",
)


def launcher_tabs() -> list[str]:
    tabs: list[str] = []
    for name in _STATIC_TAB_ORDER:
        if any(s.category == name for s in FIELD_SPECS):
            tabs.append(name)
    return tabs


def format_config_key(spec: FieldSpec) -> str:
    """JSON 上の英語キー表記（会話・デバッグ用）。"""
    if spec.handler == "inventory_slot_count":
        return "inventory.slot_count"
    if spec.handler == "inventory_uniform_slot_max_mass":
        return "inventory.slots[].max_mass"
    if spec.action_name and spec.param_name:
        if spec.profile_id:
            return (
                f'reproduction_profiles["{spec.profile_id}"]'
                f" → {spec.action_name}.params.{spec.param_name}"
            )
        return f"mind.actions → {spec.action_name}.params.{spec.param_name}"
    if spec.json_path:
        return ".".join(str(p) for p in spec.json_path)
    return spec.field_id


def format_field_reference(spec: FieldSpec) -> str:
    """説明欄末尾に付けるキー・ファイル参照。"""
    return (
        f"設定キー: {format_config_key(spec)}\n"
        f"ファイル: config/{spec.config_relpath}"
    )


def _spec_lookup_key(spec: FieldSpec) -> tuple:
    if spec.handler:
        return ("handler", spec.config_relpath, spec.handler)
    if spec.action_name and spec.param_name:
        return (
            "action",
            spec.config_relpath,
            spec.profile_id,
            spec.action_name,
            spec.param_name,
        )
    if spec.json_path:
        return ("path", spec.config_relpath, spec.json_path)
    return ("id", spec.field_id)


# (日本語ラベル, 説明, 型, min, max)
_PARAM_META: dict[str, tuple[str, str, ValueType, float | None, float | None]] = {
    "angle_range": ("旋回角度", "徘徊・巡回時の方向変更幅（度）。", "float", 5, 180),
    "approach_speed_multiplier": ("接近移動倍率", "巣や獲物へ近づくときの速度倍率。", "float", 0.3, 3.0),
    "approach_when_hungry": ("飢餓時も空巣へ接近", "備蓄が無くても飢餓なら巣へ向かう。", "bool", None, None),
    "attack_power": ("攻撃力", "1 回の攻撃で与えるダメージ。", "float", 0.5, 10.0),
    "base_max_carry": ("運搬上限（Action）", "ReturnToNestAction が参照する運搬量上限。", "float", 10, 300),
    "base_size": ("基本サイズ", "個体の表示・接触判定の基準サイズ。", "float", 3, 40),
    "base_speed": ("基本移動速度", "荷物なしの移動速度。", "float", 0.05, 3.0),
    "base_vision": ("視界", "認識できる距離（px）。", "float", 40, 600),
    "bite_gain": ("満腹変換倍率", "食料1単位あたり加算される満腹度。", "float", 0.5, 5.0),
    "camera_height": ("カメラ高さ", "ゲーム画面の描画高さ（px）。", "int", 400, 1600),
    "camera_pan_extra": ("カメラ余白", "ワールド端から見える余白（px）。", "int", 0, 800),
    "camera_width": ("カメラ幅", "ゲーム画面の描画幅（px）。", "int", 600, 2400),
    "carcass_utility_mult": ("死骸優先倍率", "死骸を選ぶときの utility 倍率。", "float", 0.5, 3.0),
    "colony_hoard_strength": ("巣へ貯蔵優先度", "満腹時に巣へ運ぶ行動の強さ。", "float", 0, 2.0),
    "contact_padding": ("接触余白", "攻撃・接触判定の追加距離（px）。", "float", 0, 30),
    "corpse_decompose_rate": ("死骸分解率", "死骸が自然分解する速さ。", "float", 0, 0.1),
    "debug_events": ("シミュイベントログ", "シミュ内部イベントをログ出力。", "bool", None, None),
    "debug_sim_events": ("シミュイベント HUD", "画面上にシミュイベントを表示。", "bool", None, None),
    "defense_hunt": ("防衛狩り", "テリトリー防衛目的の狩りモード。", "bool", None, None),
    "density_initial_max": ("マナ初期密度（最大）", "開始時マナ密度の上限。", "float", 0, 500),
    "density_initial_min": ("マナ初期密度（最小）", "開始時マナ密度の下限。", "float", 0, 500),
    "density_max": ("マナ密度上限", "タイルあたりのマナ密度上限。", "float", 100, 20000),
    "deposit_radius": ("巣への搬入半径", "巣備蓄に入れる判定距離（px）。", "float", 5, 100),
    "feed_per_tick": ("1ティックの食料消費", "1ティックで巣備蓄から取る食料量。", "float", 0.01, 50),
    "feed_radius": ("巣食事半径", "巣で食事できる距離（px）。", "float", 10, 80),
    "food_cost": ("産卵食料コスト", "1 匹産むごとに消費する食料。", "float", 5, 300),
    "food_leak_rate": ("食料漏洩率", "備蓄が一定以上あるときマナへ漏れる割合。", "float", 0, 0.01),
    "food_leak_reserve_ratio": ("漏洩開始備蓄率", "この割合以上の備蓄から漏洩が始まる。", "float", 0, 0.5),
    "food_to_mana_ratio": ("食料→マナ変換率", "漏洩・分解でマナに変わる割合。", "float", 0, 1.0),
    "fullscreen": ("フルスクリーン", "フルスクリーン表示。", "bool", None, None),
    "guard_mode": ("防衛巡回モード", "テリトリー防衛向けの巡回。", "bool", None, None),
    "hide_radius": ("巣穴に隠れる半径", "この距離内で避難完了。", "float", 10, 80),
    "high_food_ratio": ("産卵解禁閾値", "巣備蓄率がこの値以上で産卵解禁。", "float", 0.05, 1.0),
    "hole_damage_mana_cost": ("巣穴攻撃マナ消費", "巣穴1回攻撃のマナコスト。", "float", 0, 2.0),
    "hole_destroy_mana_return_ratio": ("巣穴破壊マナ返却", "巣穴破壊時に返るマナの割合。", "float", 0, 1.0),
    "hole_food_cost": ("巣穴設置コスト", "巣穴追加に必要な食料。", "float", 10, 2000),
    "hole_max_hp": ("巣穴 HP", "追加巣穴の耐久力。", "float", 10, 500),
    "hp_drain_per_dt": ("毒霧 HP 減少", "毒エリア内の1ティック HP 減少量。", "float", 0, 0.5),
    "hp_regen_mult": ("HP 回復倍率", "環境 HP 回復に掛ける倍率。", "float", 0, 3.0),
    "hp_regen_per_dt": ("テリトリー HP 回復", "自テリトリー内の1ティック HP 回復量。", "float", 0, 0.1),
    "initial_stored_food": ("初期備蓄", "開始時の巣食料。", "float", 0, 10000),
    "living_only": ("生きた個体のみ", "死骸ではなく生きた獲物のみ対象。", "bool", None, None),
    "low_food_ratio": ("低備蓄アラート", "この備蓄率未満で警告。", "float", 0.01, 0.5),
    "max_colony_members": ("コロニー個体上限", "この数以上で産卵停止。", "int", 1, 100),
    "max_food": ("巣食料上限", "巣に貯められる食料の最大量。", "float", 100, 50000),
    "max_holes": ("巣穴数上限", "コロニーが持てる巣穴の最大数。", "int", 1, 20),
    "max_hp": ("最大 HP", "体力上限。", "float", 10, 3000),
    "max_satiety": ("最大満腹度", "満腹度の上限。", "float", 10, 1000),
    "metabolism_rate": ("代謝率", "1ティックあたり減る満腹度。", "float", 0.001, 1.0),
    "milestone_workers": ("兵隊解禁働きアリ数", "働きアリがこの数以上で兵隊解禁。", "int", 1, 50),
    "min_food_reserve": ("最低食料備蓄", "操作後も残す食料の下限。", "float", 0, 1000),
    "min_hole_spacing": ("巣穴最小間隔", "巣穴同士の最小距離（px）。", "float", 20, 400),
    "min_usable_food_ratio": ("巣食事可能備蓄率", "巣食事 utility 判定用（互換）。", "float", 0, 0.5),
    "min_usable_satiety_gain": ("巣食事最小回復", "巣食事 utility 判定用（互換）。", "float", 0, 10),
    "nest_leash_radius": ("巣からの最大距離", "この距離を超えると行動を止める。0=無制限。", "float", 0, 400),
    "nest_pull_strength": ("巣への引き戻し", "巡回中に巣方向へ引く強さ。", "float", 0, 2.0),
    "nest_x": ("巣 X 座標", "コロニー巣の X 位置。", "float", 0, 5000),
    "nest_y": ("巣 Y 座標", "コロニー巣の Y 位置。", "float", 0, 5000),
    "patrol_radius": ("巡回半径", "巣周辺を動く半径（px）。", "float", 20, 400),
    "pickup_on_kill": ("倒したら即拾う", "捕食成功時に死骸を拾う。", "bool", None, None),
    "radius": ("効果半径", "フィールド効果の半径（px）。", "float", 10, 300),
    "regen_rate": ("マナ再生率", "マナレイヤーの再生速度。", "float", 0, 5000),
    "return_speed_multiplier": ("巣復帰速度倍率", "巡回中に巣へ戻る速度倍率。", "float", 0.3, 3.0),
    "satiety_full_above": ("十分満腹とみなす率", "この満腹率以上で食事不要。", "float", 0.3, 1.0),
    "satiety_hungry_below": ("飢餓とみなす率", "この満腹率以下で飢餓。", "float", 0.01, 0.5),
    "scavenge_contact_padding": ("途中食事接触余白", "巣へ向かう途中の死骸接触距離。", "float", 0, 30),
    "sim_ticks_per_step": ("1ステップの tick 数", "描画1回あたりのシミュ tick。", "int", 1, 100),
    "simulation_speed": ("シミュ速度倍率", "シミュレーション全体の速度。", "float", 0.1, 10),
    "spawn_cooldown": ("産卵クールダウン", "次の産卵までの tick 数。", "int", 0, 10000),
    "spawn_radius": ("産卵スポーン半径", "子個体の出現距離（px）。", "float", 5, 200),
    "spawn_spread": ("スポーン散らばり", "巣付近スポーンの散らばり（px）。", "float", 0, 100),
    "speed_multiplier": ("移動倍率", "行動中の移動速度倍率。", "float", 0.2, 4.0),
    "starvation_hp_mult": ("飢餓 HP ダメージ倍率", "満腹0%以下の HP ダメージ倍率。", "float", 0, 2.0),
    "territory_approach_margin": ("テリトリー接近余白", "防衛狩りのテリトリー判定余白。", "float", 0, 200),
    "territory_only": ("テリトリー内のみ", "テリトリー外では行動しない。", "bool", None, None),
    "territory_radius": ("テリトリー半径", "勢力圏の半径（px）。", "float", 30, 500),
    "territory_threat": ("テリトリー脅威優先", "テリトリー接近脅威を優先。", "bool", None, None),
    "territory_threat_score_mult": ("テリトリー脅威倍率", "脅威時 utility の倍率。", "float", 0.5, 3.0),
    "ui_font_size": ("UI フォントサイズ", "画面上 UI のフォントサイズ。", "int", 10, 48),
    "world_height": ("ワールド高さ", "マップの高さ（px）。", "int", 500, 5000),
    "world_width": ("ワールド幅", "マップの幅（px）。", "int", 500, 5000),
}

_ACTION_LABELS: dict[str, str] = {
    "ColonyReproduceAction": "産卵",
    "CombatAction": "戦闘",
    "FeedAtNestAction": "巣食事",
    "HuntAction": "狩り",
    "NestPatrolAction": "巡回",
    "ReturnToNestAction": "帰巣",
    "ScavengeCarriedAction": "運搬中食事",
    "SeekShelterAction": "避難",
    "WanderAction": "徘徊",
}

_PROFILE_LABELS: dict[str, str] = {
    "queen_feed_and_soldiers": "兵隊含む",
    "queen_feed_and_workers": "働きアリ産卵",
    "survival_feed_only": "解禁前",
    "workers_and_soldiers": "働きアリ+兵隊",
    "workers_only": "働きアリのみ",
}

_SKIP_JSON_PATHS: set[tuple[str, ...]] = {
    ("colony", "enabled"),
    ("inventory", "slot_count"),
    ("life_cycle", "death"),
    ("colony", "territory_effects", "requires_colony_match"),
}

_SKIP_ACTION_PARAMS: set[tuple[str, str]] = {
    ("FeedAtNestAction", "scavenge_species"),
    ("HuntAction", "carcass_only_species"),
    ("HuntAction", "nest_leash_radius"),
}


def is_action_field(spec: FieldSpec) -> bool:
    return bool(spec.action_name and spec.param_name)


def has_nested_ai_tabs(category: str) -> bool:
    return category in _NESTED_AI_CATEGORIES


def fields_for_category_main(category: str) -> list[FieldSpec]:
    specs = [
        s for s in FIELD_SPECS if s.category == category and not is_action_field(s)
    ]
    return sorted(specs, key=lambda s: s.field_id)


def ai_subtab_key(spec: FieldSpec) -> str | None:
    if not is_action_field(spec):
        return None
    action_label = _ACTION_LABELS.get(spec.action_name, spec.action_name)
    if spec.profile_id:
        profile_tag = _PROFILE_LABELS.get(spec.profile_id, spec.profile_id)
        return f"{action_label} [{profile_tag}]"
    return action_label


def _ai_subtab_sort_key(name: str) -> tuple:
    if "[" in name:
        action, _, rest = name.partition(" [")
        return (1, rest.rstrip("]"), action)
    return (0, "", name)


def ai_subtabs_for_category(category: str) -> list[str]:
    seen: list[str] = []
    for spec in FIELD_SPECS:
        if spec.category != category:
            continue
        key = ai_subtab_key(spec)
        if key and key not in seen:
            seen.append(key)
    return sorted(seen, key=_ai_subtab_sort_key)


def fields_for_ai_subtab(category: str, subtab: str) -> list[FieldSpec]:
    specs = [
        s
        for s in FIELD_SPECS
        if s.category == category and ai_subtab_key(s) == subtab
    ]
    return sorted(specs, key=lambda s: (s.param_name or ""))


def _meta_for_param(param_name: str) -> tuple[str, str, ValueType, float | None, float | None]:
    if param_name in _PARAM_META:
        return _PARAM_META[param_name]
    return (
        param_name,
        f"パラメータ {param_name}。",
        "float",
        None,
        None,
    )


def _meta_for_path(path: tuple[PathKey, ...]) -> tuple[str, str, ValueType, float | None, float | None]:
    key = str(path[-1])
    if key in _PARAM_META:
        return _PARAM_META[key]
    joined = ".".join(str(p) for p in path)
    return (joined, f"設定 {joined}。", "float", None, None)


def _make_field_id(prefix: str, *parts: str) -> str:
    raw = "_".join([prefix, *parts])
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in raw).lower()


def _discover_action_specs(
    *,
    category: str,
    relpath: str,
    seen: set[tuple],
    profile_id: str = "",
) -> list[FieldSpec]:
    data = load_json(relpath)
    if profile_id:
        actions = data.get(profile_id, {}).get("actions") or []
    else:
        actions = data.get("mind", {}).get("actions") or []

    specs: list[FieldSpec] = []
    for action in actions:
        action_name = str(action.get("name", ""))
        if not action_name:
            continue
        for param_name, value in (action.get("params") or {}).items():
            if (action_name, param_name) in _SKIP_ACTION_PARAMS:
                continue
            if value is None:
                continue
            if not isinstance(value, (int, float, bool)):
                continue
            key = ("action", relpath, profile_id, action_name, param_name)
            if key in seen:
                continue
            label, help_text, vtype, min_v, max_v = _meta_for_param(param_name)
            if profile_id:
                help_text = (
                    f"繁殖プロファイル {profile_id} の {action_name}。{help_text}"
                )
            else:
                help_text = f"{action_name} の {help_text}"
            field_id = _make_field_id(
                category,
                profile_id or "species",
                action_name,
                param_name,
            )
            specs.append(
                FieldSpec(
                    field_id,
                    category,
                    label,
                    help_text,
                    relpath,
                    vtype,
                    action_name=action_name,
                    param_name=param_name,
                    profile_id=profile_id,
                    min_val=min_v,
                    max_val=max_v,
                )
            )
            seen.add(key)
    return specs


def _discover_path_specs(
    *,
    category: str,
    relpath: str,
    paths: list[tuple[PathKey, ...]],
    seen: set[tuple],
) -> list[FieldSpec]:
    data = load_json(relpath)
    specs: list[FieldSpec] = []
    for path in paths:
        if path in _SKIP_JSON_PATHS:
            continue
        key = ("path", relpath, path)
        if key in seen:
            continue
        value = _get_nested(data, path)
        if value is None:
            continue
        if not isinstance(value, (int, float, bool)):
            continue
        label, help_text, vtype, min_v, max_v = _meta_for_path(path)
        field_id = _make_field_id(category, relpath.replace("/", "_"), *map(str, path))
        specs.append(
            FieldSpec(
                field_id,
                category,
                label,
                help_text,
                relpath,
                vtype,
                json_path=path,
                min_val=min_v,
                max_val=max_v,
            )
        )
        seen.add(key)
    return specs


def _discover_trait_specs(
    *,
    category: str,
    relpath: str,
    seen: set[tuple],
) -> list[FieldSpec]:
    data = load_json(relpath)
    paths: list[tuple[PathKey, ...]] = []
    traits = data.get("traits") or {}
    for key in traits:
        if isinstance(traits[key], (int, float, bool)):
            paths.append(("traits", key))
    colony = data.get("colony") or {}
    for key, value in colony.items():
        if key in ("colony_id", "join_species"):
            continue
        if isinstance(value, (int, float, bool)):
            paths.append(("colony", key))
    return _discover_path_specs(
        category=category, relpath=relpath, paths=paths, seen=seen
    )


def _finalize_field_specs(base: list[FieldSpec]) -> list[FieldSpec]:
    seen = {_spec_lookup_key(s) for s in base}
    extras: list[FieldSpec] = []

    species_scans = [
        ("女王", "sim/species/red_ant_queen.json"),
        ("働きアリ", "sim/species/red_ant.json"),
        ("兵隊アリ", "sim/species/red_ant_soldier.json"),
    ]
    for category, relpath in species_scans:
        extras.extend(_discover_trait_specs(category=category, relpath=relpath, seen=seen))
        extras.extend(
            _discover_action_specs(category=category, relpath=relpath, seen=seen)
        )

    repro_path = "game/reproduction_profiles.json"
    repro_data = load_json(repro_path)
    for profile_id in repro_data:
        extras.extend(
            _discover_action_specs(
                category="女王",
                relpath=repro_path,
                seen=seen,
                profile_id=profile_id,
            )
        )

    world_paths: list[tuple[PathKey, ...]] = [
        ("world_width",),
        ("world_height",),
        ("mana", "regen_rate"),
        ("mana", "density_max"),
        ("mana", "density_initial_min"),
        ("mana", "density_initial_max"),
        ("colony", "hole_food_cost"),
        ("colony", "max_holes"),
        ("colony", "min_hole_spacing"),
        ("colony", "min_food_reserve"),
        ("colony", "hole_max_hp"),
        ("colony", "hole_damage_mana_cost"),
        ("colony", "hole_destroy_mana_return_ratio"),
        ("colony", "territory_effects", "hp_regen_per_dt"),
        ("colony", "profiles", "red_ant", "nest_x"),
        ("colony", "profiles", "red_ant", "nest_y"),
        ("colony", "profiles", "red_ant", "territory_radius"),
        ("colony", "profiles", "red_ant", "max_food"),
        ("colony", "profiles", "red_ant", "initial_stored_food"),
        ("colony", "profiles", "red_ant", "food_leak_rate"),
        ("colony", "profiles", "red_ant", "food_to_mana_ratio"),
        ("colony", "profiles", "red_ant", "food_leak_reserve_ratio"),
        ("colony", "profiles", "red_ant", "spawn_spread"),
        ("field_emitters", "defaults", "radius"),
        ("field_emitters", "defaults", "hp_drain_per_dt"),
    ]
    for species in (
        "Amoeba",
        "Spider",
        "red_ant",
        "red_ant_queen",
        "red_ant_soldier",
        "red_ant_vanguard",
    ):
        world_paths.append(("initial_entities", species))
        world_paths.append(("population_limits", species))

    extras.extend(
        _discover_path_specs(
            category="ワールド",
            relpath="sim/worlds/world.json",
            paths=world_paths,
            seen=seen,
        )
    )

    for relpath, category, paths in (
        ("game/player.json", "ゲーム進行", (("monitor", "low_food_ratio"), ("monitor", "high_food_ratio"), ("monitor", "milestone_workers"))),
        ("sim/defaults.json", "シミュ共通", (("sim_ticks_per_step",), ("simulation_speed",), ("debug_events",), ("starvation_hp_mult",))),
        ("client/display.json", "表示・デバッグ", (("fps",), ("camera_width",), ("camera_height",), ("camera_pan_extra",), ("ui_font_size",), ("fullscreen",), ("debug_hud",), ("debug_sim_events",), ("debug_game_messages",))),
    ):
        extras.extend(
            _discover_path_specs(
                category=category, relpath=relpath, paths=list(paths), seen=seen
            )
        )

    return base + extras


_BASE_FIELD_SPECS: list[FieldSpec] = [
    # --- 女王 ---
    FieldSpec(
        "queen_max_hp",
        "女王",
        "最大 HP",
        "女王の体力上限。0 になると死亡します。",
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
        "満腹度の上限値。巣の備蓄を食べてこの値まで回復します。",
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
        "1 ティックあたり減る満腹度。高いほど巣の食料を早く消費します。"
        "満腹 0% 以下では代謝分に starvation_hp_mult を掛けた HP ダメージも入ります。",
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
        "テリトリーなど環境由来の HP 回復に掛ける倍率。0 なら環境回復なし。",
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
        "満腹 0% を下回ったあと、マイナスになった満腹度×この値が HP ダメージ。"
        "種 JSON に無い場合は sim/defaults.json の共通値を使います。",
        "sim/species/red_ant_queen.json",
        "float",
        ("traits", "starvation_hp_mult"),
        min_val=0.0,
        max_val=2.0,
    ),
    FieldSpec(
        "queen_hungry_below",
        "女王",
        "飢餓とみなす満腹率",
        "満腹度÷最大満腹度がこの値以下になると「飢餓」状態になり、巣食事が優先されやすくなります。",
        "sim/species/red_ant_queen.json",
        "float",
        ("traits", "satiety_hungry_below"),
        min_val=0.05,
        max_val=0.5,
    ),
    FieldSpec(
        "queen_full_above",
        "女王",
        "十分満腹とみなす満腹率",
        "満腹度÷最大満腹度がこの値以上で「食事不要」と判断。産卵など他行動が選ばれやすくなります。",
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
        "ゲーム開始時、赤コロニー巣に入っている食料量。",
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
        "巣に貯められる食料の最大量。働きアリの搬入上限にもなります。",
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
        "一定量以上の備蓄があるとき、毎ティック マナへ漏れる割合。高いほど余剰食料が減ります。",
        "sim/worlds/world.json",
        "float",
        ("colony", "profiles", "red_ant", "food_leak_rate"),
        min_val=0.0,
        max_val=0.01,
    ),
    FieldSpec(
        "queen_init_feed_bite",
        "女王",
        "初期・満腹変換倍率（解禁前）",
        "解禁前プロファイル（survival_feed_only）の巣食事効率。"
        "1 ティックの満腹回復 ≈ feed_per_tick × bite_gain。",
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
        "赤コロニーの勢力圏半径（px）。自勢力エリアの広さと HP 回復範囲に関係します。",
        "sim/worlds/world.json",
        "float",
        ("colony", "profiles", "red_ant", "territory_radius"),
        min_val=50,
        max_val=400,
    ),
    FieldSpec(
        "queen_feed_bite",
        "女王",
        "満腹変換倍率（産卵解禁後）",
        "産卵解禁後プロファイル（queen_feed_and_workers）の巣食事効率。"
        "消費食料 1 単位あたり加算される満腹度。",
        "game/reproduction_profiles.json",
        "float",
        action_name="FeedAtNestAction",
        param_name="bite_gain",
        profile_id="queen_feed_and_workers",
        min_val=0.5,
        max_val=5.0,
    ),
    FieldSpec(
        "queen_feed_per_tick",
        "女王",
        "1 ティックの食料消費（産卵解禁後）",
        "産卵解禁後、FeedAtNestAction が 1 ティックで巣備蓄から取る食料量。"
        "満腹回復 ≈ feed_per_tick × bite_gain（最大満腹度で切り捨て）。",
        "game/reproduction_profiles.json",
        "float",
        action_name="FeedAtNestAction",
        param_name="feed_per_tick",
        profile_id="queen_feed_and_workers",
        min_val=0.01,
        max_val=50.0,
    ),
    FieldSpec(
        "queen_repro_food_cost",
        "女王",
        "産卵の食料コスト",
        "働きアリ 1 匹を産むたびに巣備蓄から差し引く食料量。",
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
        "巣穴の新設や産卵のあとも、巣に残しておく必要がある食料量の下限。",
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
        "member_species に数えた個体がこの数以上だと、女王は産卵しません。",
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
        "産卵クールダウン",
        "1 匹産んだあと、次の産卵まで待つティック数。小さいほど増殖が速い。",
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
        "産卵スポーン半径",
        "巣の中心から、産まれた子個体が出現する距離（px）。",
        "game/reproduction_profiles.json",
        "float",
        action_name="ColonyReproduceAction",
        param_name="spawn_radius",
        profile_id="queen_feed_and_workers",
        min_val=10,
        max_val=120,
    ),
    # --- 働きアリ ---
    FieldSpec(
        "worker_speed",
        "働きアリ",
        "基本移動速度",
        "荷物なしの移動速度。運搬中は inventory.carry_speed_reference_weight により減速します。",
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
        "速度倍率 ≈ 1 / (1 + 総重量 / 参照重量)。大きいほど同じ荷重でも速い。",
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
        "運搬量 1 あたりの重量。大きいほど同量の餌でより遅くなります。",
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
        "同時に運べるバイオマススロット数。",
        "sim/species/red_ant.json",
        "int",
        handler="inventory_slot_count",
        min_val=1,
        max_val=6,
    ),
    FieldSpec(
        "worker_inv_slot_max_mass",
        "働きアリ",
        "スロット容量（各枠）",
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
        "獲物・死骸・巣を認識できる距離（px）。",
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
        "働きアリの体力上限。",
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
        "満腹度の上限。高いほど外回りが長く続きます。",
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
        "1 ティックあたり減る満腹度。",
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
        "テリトリーなど環境由来の HP 回復に掛ける倍率。",
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
        "満腹 0% 以下で入る HP ダメージの倍率。未設定時は sim/defaults.json を参照。",
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
        "HuntAction で獲物に与えるダメージ。高いほど早く倒せます。",
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
        "HuntAction 実行中の移動速度倍率。",
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
        "狩り時の満腹変換倍率",
        "狩り中にその場で食べたときの bite_gain。獲物バイオマス→満腹度の変換効率。",
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
        "ReturnToNestAction で、巣の備蓄に入れる判定距離（px）。",
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
        "NestPatrolAction で巣から離れすぎないよう引き戻す半径（px）。",
        "sim/species/red_ant.json",
        "float",
        action_name="NestPatrolAction",
        param_name="patrol_radius",
        min_val=40,
        max_val=300,
    ),
    # --- 兵隊アリ ---
    FieldSpec(
        "soldier_speed",
        "兵隊アリ",
        "基本移動速度",
        "兵隊アリの基本移動速度。各 Action の speed_multiplier と組み合わさります。",
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
        "侵入者・クモを検知できる距離（px）。",
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
        "兵隊アリの体力上限。防衛戦の耐久力に直結します。",
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
        "満腹度の上限。パトロール可能時間に影響します。",
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
        "1 ティックあたり減る満腹度。",
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
        "テリトリーなど環境由来の HP 回復に掛ける倍率。",
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
        "満腹 0% 以下で入る HP ダメージの倍率。未設定時は sim/defaults.json を参照。",
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
        "NestPatrolAction（guard_mode）でテリトリー内を巡回する半径（px）。",
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
        "対アリ戦闘攻撃力",
        "CombatAction で他勢力アリに与えるダメージ。",
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
        "対アリ戦闘移動倍率",
        "CombatAction 実行中の移動速度倍率。",
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
        "HuntAction（Spider 向け）で与えるダメージ。",
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
        "HuntAction（Spider 向け）実行中の移動速度倍率。",
        "sim/species/red_ant_soldier.json",
        "float",
        action_name="HuntAction",
        param_name="speed_multiplier",
        min_val=0.5,
        max_val=3.0,
    ),
    # --- ワールド開始 ---
    FieldSpec(
        "world_amoeba",
        "ワールド開始",
        "初期アメーバ数",
        "ゲーム開始時にスポーンする Amoeba の数。働きアリの主な狩り対象。",
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
        "ゲーム開始時の red_ant_queen 数。通常は 1。",
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
        "ゲーム開始時にフィールド上にいる red_ant の数。",
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
        "ワールド全体で同時に存在できる red_ant_soldier の上限。",
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
        "プレイヤーが巣穴を追加するときに消費する食料量。",
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
        "自コロニーのテリトリー内にいる個体の、1 ティックあたり HP 回復量。",
        "sim/worlds/world.json",
        "float",
        ("colony", "territory_effects", "hp_regen_per_dt"),
        min_val=0.0,
        max_val=0.05,
    ),
    # --- ゲーム進行 ---
    FieldSpec(
        "game_low_food",
        "ゲーム進行",
        "低備蓄アラート閾値",
        "巣備蓄率（stored_food / max_food）がこの値未満で「食料不足」警告。0.10 = 10%。",
        "game/player.json",
        "float",
        ("monitor", "low_food_ratio"),
        min_val=0.01,
        max_val=0.5,
    ),
    FieldSpec(
        "game_high_food",
        "ゲーム進行",
        "産卵解禁閾値",
        "巣備蓄率がこの値以上で女王の産卵が解禁。0.50 = 50%。",
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
        "コロニーの red_ant 数がこの値以上で兵隊アリ産卵が解禁。",
        "game/player.json",
        "int",
        ("monitor", "milestone_workers"),
        min_val=1,
        max_val=30,
    ),
    # --- シミュ共通 ---
    FieldSpec(
        "sim_starvation_hp_mult",
        "シミュ共通",
        "飢餓 HP ダメージ倍率（共通）",
        "種 JSON に starvation_hp_mult が無い個体が使う共通倍率。",
        "sim/defaults.json",
        "float",
        ("starvation_hp_mult",),
        min_val=0.0,
        max_val=1.0,
    ),
    # --- 表示・デバッグ ---
    FieldSpec(
        "client_debug_hud",
        "表示・デバッグ",
        "デバッグ HUD 表示",
        "ゲーム画面上部にデバッグ情報を重ねて表示します。",
        "client/display.json",
        "bool",
        ("debug_hud",),
    ),
    FieldSpec(
        "client_debug_messages",
        "表示・デバッグ",
        "進行メッセージをコンソール出力",
        "ゲーム進行メッセージをターミナルにも print します。",
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

FIELD_SPECS: list[FieldSpec] = _finalize_field_specs(_BASE_FIELD_SPECS)
