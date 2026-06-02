# 層間インターフェース契約（Client / Game / Sim）

**目的**: 2 つの AI（または 2 人）が **Client・Game・Sim を別々に修正**しても、契約を守れば結合テストで破綻を検知できる状態にする。

**原則**: 層の「内部実装」は自由に変えてよい。**契約に書かれた型・関数・イベントだけ**を隣の層から使う。

---

## 依存方向（厳守）

```
Client  →  Game  →  Sim
          ↘      ↗
           (Game は Sim の公開 API のみ)
Sim は Game / Client を import しない
Game は Client を import しない
```

| 境界 | 許可される向き | 禁止 |
|------|----------------|------|
| Sim ↔ Game | Game → Sim の公開 API | Sim → Game |
| Game ↔ Client | Client → Game の公開 API | Game → Client |
| Client → Sim | 読み取り専用の公開型（`World`, 描画用 DTO） | Client が Sim の game 専用 utils に依存 |

`tests/contracts/test_layer_imports.py` が import 方向を自動検査する。

---

## Sim 層 — 公開面（Game / テストが使ってよいもの）

### コア型

| シンボル | モジュール | 用途 |
|----------|------------|------|
| `World` | `src.sim.systems.world` | シミュレーション世界 |
| `SimBridge` | `src.sim.bridge` | Game → Sim 命令の唯一の実行窓口 |
| `SimCommand` 各種 | `src.sim.commands` | 命令データ（`SpawnCreature`, `SetCreatureMind`, …） |
| `SimEvent` 各種 | `src.sim.events` | 事実イベント（下表） |
| `EventBus` | `src.sim.event_bus` | `emit` / `drain` / `subscribe` |

### Sim イベント（事実のみ）

| イベント | 意味 |
|----------|------|
| `SpawnEvent` | 個体がワールドに追加された |
| `DeathEvent` | 死骸化 |
| `ItemFoundEvent` | 拾得 |
| `CombatStartedEvent` | 戦闘開始 |
| `AffiliationAllAccessRemovedEvent` | ある affiliation の接続点がすべてなくなった |

**Game 専用の意味**（プレイヤー敗北メッセージ等）は Sim に置かない。`AffiliationDefeatedEvent` は **Game 層**（`src.game.events`）。

### World 上の「中立データ」（Game が書き、Sim が読む）

| API | 説明 |
|-----|------|
| `world.mark_affiliation_defeated(id)` | 敗北フラグ（Game が設定） |
| `world.is_affiliation_defeated(id)` | 敗北判定（Sim AI・戦闘が参照） |
| `world.events` | イベントバス |
| `world.shelter_allowed_action_names` | 避難所で許可する action 名集合（Game が `attach_colony_config` で設定） |

**禁止（Sim 内部に閉じる）**: `ColonyOrchestrator`, `register_game_actions`, `colony_session` への参照。

### Game → Sim の書き込み

**`SimBridge.execute(SimCommand)` のみ。** 詳細は `docs/SimBridge.md`。

---

## Game 層 — 公開面（Client / ツールが使ってよいもの）

### Client のメイン窓口

| シンボル | モジュール | 用途 |
|----------|------------|------|
| `GameController` | `src.game.game_controller` | tick・メッセージ・Bridge 経由スポーン |
| `GameState` | `src.game.game_state` | プレイヤー勢力 ID・フラグ・危険度等 |
| `GameMessage` | `src.game.game_message` | UI メッセージ |
| `SimRunner` | `src.game.sim_runner` | `world.update` 前の maintenance 配線 |
| **`client_api`** | `src.game.client_api` | **Client 専用の読み取り API（推奨）** |

### Client が Game 経由で読むべきデータ

`src.game.client_api` を使う（`colony_session` / `colony_orchestrator` の直接 import は Client では非推奨）。

| 関数 | 用途 |
|------|------|
| `get_defeated_affiliation_ids(world)` | 描画（敗北勢力の薄表示） |
| `try_get_affiliation_fill_ratio(world, id)` | HUD（備蓄率） |
| `try_get_colony_orchestrator(world)` | デバッグ・穴配置等（既存互換） |

### Game の内部（Client が触らない）

- `colony_orchestrator`, `colony_compound`, `game_director` のロジック詳細
- `src.game.ai.*` の Action 実装（Client は action 名のラベル程度まで）

### Game が Sim を触る経路

1. **命令**: `SimBridge.execute`
2. **イベント処理**: `world.events.drain()` → `GameDirector.on_sim_events`
3. **tick 補完**: `ensure_creature_affiliations`, `SimRunner._run_game_maintenance`
4. **敗北**: `AffiliationAllAccessRemovedEvent` → `defeat_affiliation` → `AffiliationDefeatedEvent`

---

## Client 層 — 責務と制約

### やること

- pygame 描画・入力
- `SimRunner.tick(world)` → `GameController.on_tick(world)` の順序維持
- `GameController` / `client_api` / `GameState` 経由のゲーム情報表示

### 避けること（別 AI が Sim を壊さないため）

| 非推奨 | 代わり |
|--------|--------|
| `from src.game.colony_session import …` | `from src.game import client_api` |
| `from src.game.ai.reproduction_actions import …` | HUD は action 名文字列のみ |
| `from src.sim.utils.*` の乱用 | 描画に必要な最小限、または `client_api` へ要望を足す |

**許容（現状）**: `World` 参照、`entity_xy`, `is_creature_sheltered` 等の**安定した描画ヘルパ**。新規依存は `client_api` 拡張を優先。

### Client が持つ結合点（変更時は両方確認）

```text
GameApp.reset_simulation:
  World() → make_sim_bridge → GameController.reset_for_world

GameApp.update (毎 sim tick):
  SimRunner.tick(world)   # maintenance + world.update
  GameController.on_tick(world)
```

---

## 2 AI で並行開発するときの手順

### AI-A: Sim だけ触る

1. `tests/contracts/test_layer_imports.py` が通ることを確認
2. `tests/sim/` のうち `@pytest.mark.no_colony` テストを優先
3. イベント・`World` API 変更時は `docs/Simulation_Events.md` と本書の Sim 表を更新
4. Game 側が必要なら **新しい SimEvent または World の中立フィールド**を追加（Game は別 PR）

### AI-B: Game だけ触る

1. `tests/game/` を実行
2. Sim への変更は `SimBridge` / イベント購読 / `mark_affiliation_defeated` に限定
3. Client 向けの新データは `client_api.py` に追加

### AI-C: Client だけ触る

1. `tests/client/` を実行
2. Game/Sim の内部モジュールを import しない方針
3. ゲーム状態が要れば `GameController.state` または `client_api`

### 結合確認（どちらかがマージ前に）

```bash
python -m pytest tests/contracts tests/game tests/sim tests/client -q
```

---

## ロードマップ（契約の強化）

| 優先度 | 項目 | 効果 |
|--------|------|------|
| 高 | import 契約テスト（実施済み） | 層違反を即検知 |
| 高 | `client_api` への Client 依存集約 | Client AI が Sim を触らない |
| 中 | `Simulation_Events.md` と本書の同期 | ドキュメント単一真実源 |
| 中 | Sim 公開面の `src/sim/public.py` 再エクスポート | import 先を 1 モジュールに |
| 低 | `WorldView` DTO（Client 専用スナップショット） | Renderer の Sim 依存ゼロ |

---

## 関連ドキュメント

- `docs/Architecture_Sim_Game_Boundary.md` — 設計思想
- `docs/SimBridge.md` — Game → Sim 命令
- `docs/Simulation_Events.md` — イベント詳細（要: Game イベントとの区分を追記）
