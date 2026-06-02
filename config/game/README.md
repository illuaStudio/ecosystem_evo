# ゲーム層設定（`config/game/`）

シミュレーションエンジン（`src/sim/`）が読み込む**コンテンツ**。数値の意味づけ（勢力拠点・給餌・コロニー AI など）は **game 層コード**（`src/game/`）が解釈する。sim は `src/game` を import しない。

## sim / game の役割

| 層 | 担当 |
|----|------|
| **sim** | 個体・物理・`wander_step` 等の移動プリミティブ、`WorldObject`、affiliation レイアウトの**中立データ**（`AffiliationLayoutState`） |
| **game** | コロニー進行（`ColonyOrchestrator`）、すべての「意味ある」AI（`HuntAction`, `CombatAction`, `ChaseAction` 等）、拠点給餌判定（`affiliation_feed`） |

種 JSON の `mind.actions` に書く行動名のうち、コロニー向けは `src/game/ai/` に実装され、`register_game_actions()` でレジストリに載る。本番は `GameController.reset_for_world`、テストは `tests/sim/colony_binding.bind_colony` または `load_test_world()` がこれを行う。

## ディレクトリ

| パス | 内容 |
|------|------|
| `species/` | 種定義（traits, mind, death_policy, affiliation_feed 等） |
| `worlds/` | ワールド JSON（`affiliation` ブロック含む） |
| `reproduction_profiles/` | コロニー産卵プロファイル（game 層が参照） |

## affiliation（ワールド JSON）

`worlds/*.json` の `affiliation` は sim が `World._affiliation_layout` に解析する。プロファイル（`nest_x`, `max_mass` 等）・勢力スタイル・種族マップはここに置く。敗北状態も同オブジェクト上で更新される。

ゲーム層は `ColonyOrchestrator` 経由で拠点オブジェクトの生成・給餌・接続点などを扱う。

## 種 JSON: `affiliation_feed`

コロニー種が拠点 storage から食べるルール。game の `affiliation_feed.py` が解釈する（旧 `nest_feed` キーも受理）。

## 死後処理（`death_policy`）

sim は **PostLife のパーツ列**だけ実行する。種 JSON に `death_policy` が無い／空なら **何もしない**。

| 値 | 意味 |
|----|------|
| `"field_drop"` | 地面に `field_bulk` を出して個体を `remove`（本ゲームの通常死後ルート） |
| `"immediate_remove"` / `"remove"` | 即ワールドから削除 |
| `{ "steps": [ ... ] }` | パーツを直列指定（`spawn_drop`, `warp_to` 等） |

地面ドロップの型:

| 型 | 用途 |
|----|------|
| `field_bulk` | バイオマス（連続量・死後ドロップ） |
| `field_item` / `field_gold` | `StackItem`（剣・金貨など個数物） |

ゾーン（毒霧など）は `instances` の `layer: "zone"` のみ。

例（`species/spider.json`）:

```json
"death_policy": "field_drop"
```

## 主な Action 名（種 JSON）

**sim:** `IdleLocomotionAction` のみ（utility 全滅時のフォールバック。ゲームルールなし）

**mind オプション:** `fallback_action`（既定 `IdleLocomotionAction`）、`fallback_params`（未指定時は同名の `actions` エントリの params を流用）

**game:** `WanderAction`, `ChaseAction`, `CombatAction`, `FleeAction`, `HuntAction`, `ReturnToNestAction`（→ `ReturnToAffiliationDepositAction`）, `FeedAtNestAction`, `NestPatrolAction`, `AffiliationReproduceAction`, `SeekShelterAction`, `AttackHoleAction`, `ScavengeCarriedAction`, `ReproductionAction`（基底）

`HuntAction` の params は種 JSON に列挙したキーのみ必須（`require_action_params`）。オプション例: `nest_leash_radius`, `nest_hunt_dampen_radius`（未指定時は game 側デフォルト）。

## テスト

- `tests/sim/world_fixtures.load_test_world()` — affiliation 付きワールド＋`bind_colony`
- `tests/sim/conftest.py` / `tests/game/conftest.py` — テスト用 World 生成時に monkeypatch で bind_colony を自動適用（`@pytest.mark.no_colony` で opt-out）。ルート `tests/conftest.py` は action レジストリ登録のみ。
