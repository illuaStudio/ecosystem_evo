# Simulation Events（Phase 1）

生態系シミュレーション層が発行する**離散イベント**の契約。ゲーム層は `World.events` を購読または `drain()` で取り出して解釈する。

## 設計方針

- シミュレーション層は「事実の発生」を等しく通知するだけ
- 数値の推移（備蓄率・個体数など）はイベント化しない（ゲーム層が監視）
- イベントは `World.events`（`EventBus`）に `emit` される

## イベント一覧

| イベント | 発火タイミング | 主なフィールド |
|---------|---------------|---------------|
| `DeathEvent` | 個体が死骸化したとき | `creature`, `species_name`, `colony_id`, `cause` |
| `SpawnEvent` | 個体がワールドに追加されたとき | `creature`, `source`, `parent` |
| `ItemFoundEvent` | 死骸からバイオマスを拾ったとき | `carrier`, `item_kind`, `amount` |
| `CombatStartedEvent` | 個体同士／巣穴への初回攻撃 | `attacker`, `target_kind`, `target_creature` 等 |
| `ColonyDefeatedEvent` | 勢力の全巣穴が破壊されたとき | `colony_id`, `message` |

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
| `reproduction` | `ColonyReproduceAction`（女王など） |
| `split` | `SplitAction`（無性分裂） |
| `spawn` | その他（既定） |

## API

```python
from src.sim import EventBus, DeathEvent, SpawnEvent

world.events.emit(event)          # キューに積み、購読者へ即通知
world.events.subscribe(handler)   # handler(event) を登録
events = world.events.drain()     # キューを取り出してクリア
```

## 発火箇所（コード）

| イベント | ファイル |
|---------|---------|
| Death | `src/components/corpse.py` |
| Spawn | `src/systems/world.py` (`add_creature`) |
| ItemFound | `src/utils/inventory_helpers.py` |
| CombatStarted | `src/utils/combat_helpers.py`, `src/combat/target_damage.py` |
| ColonyDefeated | `src/systems/nest_system.py` |

## ゲーム層での利用（例）

```python
for event in world.events.drain():
    if isinstance(event, SpawnEvent) and event.source == "reproduction":
        ...
    if isinstance(event, ColonyDefeatedEvent):
        ui.show_message(event.message)
```

`GameApp` は `ColonyDefeatedEvent` を `drain()` して UI メッセージを表示する（Phase 1）。

## 戦闘開始の重複抑制

同一 tick 内で同じ `(攻撃者, 対象)` ペアからは `CombatStartedEvent` を1回だけ発火する（`World._combat_pairs_this_tick`）。
