# Simulation Events（Sim 層事実イベント）

生態系シミュレーション層が発行する**離散イベント**の契約。ゲーム層は `World.events` を購読または `drain()` で取り出して解釈する。

## 設計方針

- シミュレーション層は「事実の発生」を等しく通知するだけ
- 数値の推移（備蓄率・個体数など）はイベント化しない（ゲーム層が監視）
- イベントは `World.events`（`EventBus`）に `emit` される

## イベント一覧

| イベント | 発火タイミング | 主なフィールド |
|---------|---------------|---------------|
| `DeathEvent` | 個体が死骸化したとき | `creature`, `species_name`, `cause` |
| `SpawnEvent` | 個体がワールドに追加されたとき | `creature`, `species_name`, `source`, `parent` |
| `ItemFoundEvent` | 死骸/アイテムを拾ったとき | `carrier`, `species_name`, `item_kind`, `amount` |
| `CombatStartedEvent` | 個体同士またはアクセスポイントへの初回攻撃 | `attacker`, `attacker_species`, `target_kind`, `target_creature` / `target_object_id` |
| `AffiliationAllAccessRemovedEvent` | ある affiliation の全アクセスポイント（接続点）が破壊されたとき | `affiliation_id` |

**注**: `AffiliationDefeatedEvent`（`affiliation_id`, `message`）は **Game 層** (`src/game/events.py`) のイベント。Sim 層の `AffiliationAllAccessRemovedEvent`（事実）に対する game 側の反応として生成される。

### DeathEvent.cause

| 値 | 意味 |
|----|------|
| `hp` | HP が尽きた |
| `lifespan` | 寿命到達 |
| `metabolism` | 飢餓・代謝 |
| `defeat` | コロニー敗北時（巣穴内の個体） |
| `unknown` | その他 |

### SpawnEvent.source

| 値 | 意味 |
|----|------|
| `initial` | ワールド初期配置 |
| `reproduction` | 繁殖行動による追加 |
| `spawn` | その他（既定） |
| `game` | ゲーム進行・脚本からのスポーン |
| `debug` | デバッグ操作からのスポーン |

`source` は `SpawnCreature` コマンドの source や world.add_creature から引き継がれる。

## API

```python
from src.sim import EventBus, DeathEvent, SpawnEvent

world.events.emit(event)          # キューに積み、購読者へ即通知
world.events.subscribe(handler)   # handler(event) を登録
events = world.events.drain()     # キューを取り出してクリア
```

## 発火箇所（コード）

イベントの発火は `src/sim/emitters.py` に集約されている（直接 emit せずヘルパー経由が推奨）。

| イベント | 呼び出し元ファイル |
|---------|---------|
| Death | `src/sim/components/death.py` (`emit_death`) |
| Spawn | `src/sim/systems/world.py` (`add_creature` → `emit_spawn`) |
| ItemFound | `src/sim/utils/loot_helpers.py` (`emit_item_found`) |
| CombatStarted | `src/sim/utils/combat_helpers.py`, `src/sim/combat/target_damage.py` (`emit_*` / `maybe_emit_combat_from_damage`) |
| AffiliationAllAccessRemoved | `src/sim/systems/compound_system.py` (`emit_affiliation_all_access_removed`) |

## ゲーム層での利用（例）

Sim イベントは事実のみ。Game 層（`GameDirector`）が受け取り、**creature / world_object から affiliation を解決**し、必要に応じて game イベントを生成する。

接続点（`world_object`）への攻撃では `target_object_id` → access の `parent_id` で所属勢力を判定する。

```python
# GameController / Director 側での典型処理
for event in world.events.drain():  # Sim 事実イベント
    if isinstance(event, SpawnEvent):
        # event-driven: 所属付与など game 反応
        ...
    if isinstance(event, AffiliationAllAccessRemovedEvent):
        # → defeat 処理 → AffiliationDefeatedEvent (game event) 発火
        ...

# 別途 game イベント
game_events = drain_game_events(world)
for ev in game_events:
    if isinstance(ev, AffiliationDefeatedEvent):
        ui.show_message(ev.message)
```

`GameDirector.on_sim_events(events, world)` と `on_game_events(...)` がこれらを一元的にハンドルする。

## 戦闘開始の重複抑制

同一 tick 内で同じ `(攻撃者, 対象)` ペアからは `CombatStartedEvent` を1回だけ発火する（`World._combat_pairs_this_tick`）。
