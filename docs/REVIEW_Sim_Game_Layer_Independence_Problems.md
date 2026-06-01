# Sim層とGame層の境界独立性に関する現状問題点レビュー

**作成日**: 2026-06  
**作成者**: Grok (xAI) によるソース読み取り・分析  
**対象リポジトリ**: [illuaStudio/ecosystem_evo](https://github.com/illuaStudio/ecosystem_evo)  
**目的**: Cursor及び今後のリファクタリングのために、Sim層とGame層の境界問題を客観的・詳細に整理する。

---

## 1. 背景と理想像

公式ドキュメント `docs/Architecture_Sim_Game_Boundary.md` で、以下の原則が明確に定められています。

> **Sim層** は「ゲームに依存しない基盤」であること。
> ゲーム特有の概念（コロニー、勢力、繁殖進行、女王の役割など）は極力入れない。

> Game層がゲームを進行させる。Sim層からイベントを受け取り、Bridge経由で命令を発行する形にすべき。

同ドキュメントは、現在の「漏れ」を開発者自身が正直に認識し、今後の改善方針（Phase D以降）まで記述しています。

---

## 2. 評価サマリー

### 良い点

- **import方向の独立性は完全に守られている**
  - `src/sim/` から `src/game/` への import は全面無し。
- **優秀な分離機構が既に存在**
  - `SimBridge` + `game_hooks` 注入
  - `register_game_actions()` による Action レジストリ拡張
  - `colony_session.py` での `WeakKeyDictionary` + コールバックパターン
- **問題の自覚が高い**
  - 上記のアーキテクチャドキュメントが存在し、改善ロードマップが書かれている。

### 問題点（重大度順）

1. **Worldクラスへのゲームドメインの強い混入** (最大問題)
2. **WorldObjectSystem および関連Utilsへのゲームロジック漏れ**
3. **イベント定義への affiliation 概念の混入**
4. **ライフサイクルフックの過度利用とガッチリ結合**

---

## 3. 具体的な問題場所と証拠

### 3.1 Worldクラスへのゲーム概念の直接混入

**ファイル**: `src/sim/systems/world.py`

```python
self._affiliation_layout_raw = dict(layout.get("affiliation") or {})
self._affiliation_layout = AffiliationLayoutState.from_block(...)

# 以下のプロパティが公開されている
@property
def affiliation_profiles(self) -> dict: ...
@property
def defeated_affiliations(self) -> set[str]: ...
@property
def affiliation_species(self) -> dict: ...

self.on_sim_tick = None
self.on_creature_added = None
self.access_damage_handler = None
```

**update内での直接呼び出し**:
```python
tick_hook = getattr(self, "on_sim_tick", None)
if tick_hook is not None:
    tick_hook(dt)   # ここで ColonyOrchestrator.update が呼ばれる
```

**問題点**:
- Worldが「コロニー/勢力の状態を持つ容器」になっている
- Sim層の核心クラスがゲームルールの状態を知っている

### 3.2 WorldObjectSystemのゲーム特化

**ファイル**: `src/sim/systems/world_object_system.py` (約 30,000 lines)

- colony compound、storage、access point、備留管理などのゲーム特有ロジックが大量に存在
- ドキュメントでも「現在 WorldObjectSystem はすでにかなりゲーム寄り」と認識されている

### 3.3 イベントへのゲーム概念の混入

**ファイル**: `src/sim/events.py`

```python
@dataclass
class DeathEvent(SimEvent):
    affiliation_id: Optional[str] = None   # ゲーム概念

@dataclass
class AffiliationDefeatedEvent(SimEvent):   # このイベント自体がゲーム特有
    affiliation_id: str = ""
```

Sim層が「勢力の敗北」というゲーム的な事象を知っている状態。

### 3.4 コールバックによる強い結合

**`src/game/colony_session.py`**:

```python
def attach_colony_orchestrator(world: "World", orchestrator):
    register_game_actions()                    # Game層からSimのレジストリを変更
    world.on_creature_added = ...
    world.access_damage_handler = ...
    world.on_sim_tick = orchestrator.update   # 最も重要なドライブロジック
```

これ自体は「必要悪」ではないが、コロニー進行の大部分がこのフックに集中しており、Sim層の独立性を低下させている。

---

## 4. 影響

- **メンテナンス性の悪化**: Sim層のテストがゲームルールに依存しやすくなっている
- **拡張性の阻害**: 新しいゲームモード、別の勢力タイプ、マルチプレイヤー化などがしにくい
- **設計負荷の増大**: Worldが「すべてを知っている神」になっており、認知ロードが高い
- **今後のAIコーディング時の障害**: コンテキストが大きすぎて、変更時の予測難易度が低下

---

## 5. Cursor / AI レビューにお願いしたい観点

1. 上記の漏れが、実際の開発スピードと保守性にどれくらい影響しているかの量化
2. 現実的な改善戦略の提案
   - Big Bang リファクタリング vs 段階的アプローチ
   - 最小限の改善で最大効果が得られる順序
3. `World` からゲーム状態を分離する際の最適な抽象化レベル
4. 現在の `SimBridge` + フック機構を活かしたままでの改善可能性
5. テストスートの再構築が必要になる範囲

---

## 6. 推奨リファクタリング方針（個人的見解）

| 優先度 | 項目 | 内容 |
|--------|------|------|
| High   | World からの affiliation 状態の分離 | `_affiliation_layout` と関連プロパティを、Game層が持つ小さなコンテナへ移動 |
| High   | WorldObjectSystem の分割 | 薄い汎用部分とコロニー解釈レイヤーの分離を検討 |
| Medium | イベントの純化 | `AffiliationDefeatedEvent` を Game層でのみ取り扱う形に変更、Simイベントは更に事実のみに |
| Medium | on_sim_tick の使い方の制限 | コロニー進行の大部分を、イベントドリブンへの移行を検討 |
| Low    | 新しいヘルパーレイヤーの作成 | `GameWorldInterpreter` または `ColonySiteSystem` (ゲーム層) の新設 |

---

## 7. 参考ドキュメント

- `docs/Architecture_Sim_Game_Boundary.md` (最重要)
- `docs/SimBridge.md`
- `docs/Simulation_Events.md`
- `src/game/colony_session.py` (分離機構の最も良い例)
- `src/sim/systems/world.py`
- `src/sim/systems/world_object_system.py`

---

**注**: このドキュメントは、問題点を強調するために書かれましたが、プロジェクト全体の品質は非常に高いです。特にテスト量とドキュメント質は、同規模のプロジェクトとして優秀です。
