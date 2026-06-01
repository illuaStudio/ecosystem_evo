# Game → Sim 命令 API（SimBridge）

ゲーム層がシミュレーション層へ状態変更を指示する唯一の窓口。

## 原則

- **Sim → Game**: `World.events`（EventBus）で事実を通知
- **Game → Sim**: `SimBridge.execute(SimCommand)` のみ
- Client / デバッグキーも GameController 経由で Bridge を呼ぶ

## 命令一覧

| 命令 | 用途 |
|------|------|
| `SpawnCreature` | 指定種をスポーン。`x`/`y` 省略時はランダム座標 |
| `SetCreatureMind` | 個体の AI actions を replace / merge / reset |
| `SetSpeciesMind` | 種名一致の全個体に AI 適用（`colony_id` で絞り可） |
| `SetAffiliationCasteMind` | **同一コロニー内の種別**全個体に AI 適用 |
| `EnterCreatureShelter` | 個体を巣穴 shelter へ |

### SetAffiliationCasteMind.caste

| 値 | 対象 |
|----|------|
| `worker` | 働きアリ（`_soldier` / `_vanguard` / `_queen` 以外） |
| `soldier` | 種名が `_soldier` で終わる個体 |
| `vanguard` | 種名が `_vanguard` で終わる個体 |
| `combat` | 兵隊 + 先兵（`_soldier` / `_vanguard`） |
| `queen` | 種名が `_queen` で終わる個体 |
| `member` | コロニー所属の全個体 |

複数形エイリアス（`workers`, `soldiers` 等）も受け付ける。

### SpawnCreature.source

| 値 | 意味 |
|----|------|
| `game` | ゲーム進行・脚本からのスポーン |
| `debug` | Client デバッグキー |

`SpawnEvent.source` に反映される。

### SetCreatureMind / SetSpeciesMind.mode

| 値 | 意味 |
|----|------|
| `replace` | actions を丸ごと差し替え |
| `merge` | 既存に不足 action 名だけ追加 |
| `reset` | 種 JSON の既定 actions に戻す |

## 使用例

```python
from src.sim.bridge import SimBridge
from src.sim.commands import SpawnCreature, SetSpeciesMind

bridge = SimBridge(world)

# 指定座標
bridge.execute(SpawnCreature(species="Spider", x=400, y=300, source="game"))

# ランダム座標
bridge.execute(SpawnCreature(species="Spider", source="game"))

# 種族全体に AI 付帯
bridge.execute(SetSpeciesMind(
    species_name="red_ant_queen",
    actions=profile_actions,
    affiliation_id="red_ant",
    mode="replace",
))

# 同一コロニーの働きアリ全員
bridge.execute(SetAffiliationCasteMind(
    affiliation_id="red_ant",
    caste="worker",
    actions=profile_actions,
    mode="merge",
))

# 兵隊 + 先兵
bridge.execute(SetAffiliationCasteMind(
    affiliation_id="red_ant",
    caste="combat",
    actions=profile_actions,
    mode="replace",
))
```

## ゲーム進行（progression.json）

`GameDirector.evaluate_unlocks()` が tick 末尾で `progression.json` を評価する。

| unlock id | 条件 | 効果 |
|-----------|------|------|
| `queen_worker_reproduction` | `high_food_reached` | 女王 AI → 食事+働きアリ繁殖 |
| `queen_soldier_reproduction` | `workers_milestone` + 上記解禁済 | 女王 AI → 兵隊繁殖追加 |

状態は `GameState.applied_unlocks` に記録（一度きり）。

`src/game/command_builder.py` が JSON プロファイルを命令に変換する:

- `spawn_creature(bridge, species, x=..., y=...)`
- `apply_mind_profile(bridge, creature, profile_id)`
- `apply_mind_profile_to_species(bridge, species, profile_id, affiliation_id=...)`
- `apply_mind_profile_to_affiliation_caste(bridge, affiliation_id, caste, profile_id)`
- `apply_spawn_profile(bridge, creature)` — `spawn_profiles.json` 適用

`GameController` は上記をラップ:

```python
ctrl.spawn_creature("Spider", x=100, y=200)
ctrl.apply_mind_profile(queen, "workers_and_soldiers")
ctrl.apply_mind_profile_to_species("red_ant_queen", "workers_only", affiliation_id="red_ant")
ctrl.apply_mind_profile_to_affiliation_caste("red_ant", "worker", "some_profile")
ctrl.apply_mind_profile_to_affiliation_caste("red_ant", "combat", "patrol_profile")
```
