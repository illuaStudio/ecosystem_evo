# Sim 層アーキテクチャ

## 三層分離

| 層 | 正 | 例 |
|----|-----|-----|
| **生物** | `Creature` + コンポーネント | HP, Mind, Inventory, PostLife |
| **配置物** | `WorldObject`（`WorldObjectSystem`） | zone, obstacle, spawn, field, compound |
| **バイオーム** | `WorldBiome`（手続きノイズ） | rich/poor, spawn_rate_multiplier |

## マップ配置の流れ

1. **ランタイム**: `canonicalize_runtime_layout(world_data)` — instances 展開 + affiliation プロファイル同期（legacy sections へのミラーはしない）
2. **エディタ/テスト**: `normalize_world_layout()` — instances ↔ 旧 sections の双方向ミラー
3. `WorldObjectSystem.init_from_layout` — 唯一の配置ソース
4. 派生キャッシュ（読み取り専用）:
   - `ZoneSystem.rebuild_from_world_objects()`
   - `ObstacleSystem.rebuild_from_world_objects()`
   - `SpawnSystem.rebuild_from_world_objects()`

巣クリアリングは `{affiliation_id}_clearing` の **zone WorldObject**。`ZoneSystem` は WO をミラーするだけ。

## 環境フィールド

`environment/field_sources.py` — `BiomeFieldSource` + `TerritoryFieldSource` + `ZoneFieldSource` → `compose_field_sample()`。

## 死後

- sim の `death_policy` は **step 列のみ**（エイリアスなし）
- 種 JSON の文字列エイリアスは `species.expand_death_policy_content()` で展開
- パーツ: `spawn_drop`, `remove`, `warp_to`, …

## 採餌

- `combat/pickup_target.py` — field WorldObject の統合探索・移動・消費
- `utils/forage_helpers.py` — 中立名 API（field 専用の拾得は `loot_helpers`）

## Compound / 勢力拠点

- `CompoundSystem` — 汎用 storage + access（sim）
- **ゲーム層** `game/colony_compound.py` — 勢力拠点への預け入れ・給餌
- **sim** `affiliation_layout.py` — ワールド JSON affiliation ブロックの中立データ（`World._affiliation_layout`）
- **ゲーム層** `game/colony_config.py` — 上記レイアウトへの参照ヘルパ（`ColonyConfig` は型エイリアス）
- **ゲーム層** `game/affiliation_feed.py` — 拠点給餌判定（種 JSON の `affiliation_feed`）
- `utils/affiliation_site_helpers.py` — 拠点への距離・座標（ゲーム意味なし）
- **ゲーム層** `game/colony_orchestrator.py` — コロニー進行（敗北・接続点・備蓄漏れ・所属付与）
- **ゲーム層** `game/colony_runtime.py` + `colony_session.py` — 敗北集合・ゲームイベント（`AffiliationDefeatedEvent`）
- **Sim** `World.defeated_affiliation_checker` — Game が attach 時に注入する敗北判定（Sim は Game を import しない）
- **ゲーム層** `game/ai/` — 意味のある行動すべて（狩り・戦闘・逃走・捕食・コロニー・避難等）。`register_game_actions()` でレジストリ登録
- **シミュ層** `sim/ai/actions/` — `Action` 基底・`IdleLocomotionAction`（フォールバック専用）・レジストリ・`UtilityMind`
