# Game層への依頼: Client 向け「選択個体の Hunt/Combat ターゲット」安全ビュー API の追加

> **このドキュメントの目的**: Client担当が Game担当（CursorAIなど）に具体的な変更を依頼するための詳細仕様書です。
> Game担当はまずこのファイルを読んで実装してください。
> 並行開発のルールや文脈は [Client_Game_Layer_Boundary_for_Parallel_AI_Development.md](./Client_Game_Layer_Boundary_for_Parallel_AI_Development.md) の「現在オープンな Client からの Game層への依頼」セクションも参照。

**対象**: CursorAI / Game担当AI の方へ（Client担当が作成）

**ステータス**: ✅ **完了**（2026-06）— Game 実装・Client 移行済み。回答: [Response_Game_TargetView_API_for_Client.md](./Response_Game_TargetView_API_for_Client.md)

**目的**: 設計上きれいに分離するため、Game層に `client_api` 経由のビューを追加してほしい。Client側で現在 ad-hoc な防御コードを入れているが、これは一時的なワークアラウンド。

## 1. 何が起きたか（再現したエラー）
- 選択クリーチャー（`selected_creature`）の右クリック選択時、`_draw_hunt_overlays` や HUD「狩り対象」表示でクラッシュ。
- エラー: `AttributeError: 'WorldObject' object has no attribute 'species'`
- 発生場所例:
  - `src/client/species_visibility.py:65` → `creature.species.name`
  - `renderer.py` の `is_creature_visible` 呼び出し、`prey.traits.get`、`describe_creature_short`
- トリガー: `get_hunt_target(sc)` / `get_combat_target(sc)` が返す値が `creature` ではなく `WorldObject`（field carcass / biomass pickup）だった。

## 2. なぜこうなるのか（設計の意図）
- `src/game/ai/hunt_actions.py` の `HuntAction` は**意図的に**両方をターゲットにする:
  - 生きた獲物（`find_nearest_prey_creature`）
  - 死骸 / フィールドバイオマス（`find_nearest_forage_among` + `is_field_pickup` / `PickupTarget` 系）
  - params で `carcass_only_species`, `living_only`, `pickup_on_kill` などを制御。
  - `_target` に creature または WorldObject を直接セット（`_resolve_target` など）。
- `src/sim/utils/hunt_helpers.py` の `get_hunt_target` / `get_combat_target` / `describe_creature_short` はこれをそのまま Any で返す（Sim の中立ヘルパー）。
- Client の描画（`renderer.py` の `_draw_hunt_overlays`, `_draw_prey_marker`, 選択個体HUDテキスト）や `species_visibility` は「対象は常に creature で .species を持つ」と仮定していた。
- CombatAction は主に creature だが、HuntAction は明確に混在をサポート。

これは **Game のドメイン知識**（いつ carcass を狙うか、いつ creature か）。

## 3. 現在の Client 側の対応（ワークアラウンド）
Client層だけで以下を追加してクラッシュを回避した（`src/client/` のみ編集）:
- `species_visibility.py`: `is_creature_visible` に `hasattr(species)` ガード。非 creature（WorldObject など）は `True`（選択オーバーレイは常に描きたいため）。
- `renderer.py`:
  - `_creature_visible_for_overlay` のコメント強化。
  - `_draw_prey_marker` で size を `traits` → `radius` / `pickup_radius` フォールバック。
  - 新規 `_safe_describe_target`（species がある時だけ `describe_creature_short` を呼び、なければ label/type_ref + 「死骸/対象」フォールバック）。
  - HUDテキスト構築と attackers 表示で `_safe_describe_target` を使うよう変更。
- これで WO target でも draw 成功し、サイズ・名前がそれなりに出る。
- テスト: headless GameApp + 明示的に WO を _target にセットしたモックで確認済み。contracts / client テストも pass。

**これは「きれいではない」**。Client が Game の Action 内部型（WorldObject vs creature）の区別を一部知ってしまっている。

## 4. 設計上なぜ Game / client_api に置くのがきれいか（並行開発の観点）
- **情報隠蔽と境界**: Client は「この選択個体は今何を狙っていて、描画するにはどんな情報が必要か」だけ知ればよい。Game の HuntAction / CombatAction / forage ロジックの詳細（carcass 判定、field pickup、_target の生の型）を知る必要はない。
- **並行開発の頑健性**: Game側が target 解決ロジック（優先順位、carcass_utility、PickupTarget ラッパーの進化、Combat の拡張など）を変えても、client_api のシグネチャと `TargetView` の内容を維持すれば Client は壊れない。現在のような「Client が突然クラッシュして Game の変更に気づく」事態を防げる。
- **既存パターンとの整合**: すでに `find_queen_reproduction_action` / `get_queen_reproduction_readiness` で、Game の reproduction Action 詳細を client_api 内に閉じ込めている。queen_status.py は直接 `src.game.ai.reproduction_actions` を import しなくなった。これと全く同じ。
- **Client の責務分離**: Client の `SpeciesVisibilityManager` は「生態グループ（red_ant, spider など creature 種）」の ON/OFF。WorldObject target は種族フィルタの対象外（常に表示）という判断は、Game がビューで `is_creature` や `species_name` を教えてくれれば Client がシンプルに書ける。
- **Layer_Interfaces / Boundary ドキュメントの精神**:
  - Client → Game は `client_api` 経由が推奨。
  - `from src.sim.utils.hunt_helpers` の直接利用（描画ヘルパーとして許容されていた範囲）を、target 表示については client_api に移行したい。
  - 「新しい Game データが必要になったら client_api に追加を検討（またはこのようなドキュメントで依頼）」と明記されている。
- 長期メンテ: 将来 target が増えても（例: 他の WorldObject 種別、構造物など）、ビューを拡張するだけで Client 側の if が増えなくて済む。

**結論**: 設計上きれいなので、Game層で追加をお願いします。Client側は API 追加後にワークアラウンドを撤去してビューを使う形にリファクタします。

## 5. 提案する API（client_api.py への追加イメージ）
```python
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.sim.systems.world import World
    # ...

@dataclass(frozen=True)
class TargetView:
    """選択個体が現在 HuntAction / CombatAction で狙っている対象の、Client描画・HUD用ビュー。
    Game層が Action._target を解決して構築。Client は creature / WorldObject / 将来の型の違いを知らなくてよい。
    """
    kind: str                  # "creature" | "carcass" | "field_biomass" | "other"
    name: str                  # HUD/ラベル用表示名（例: "springtail (死骸)", "biomass (field 80%)"）
    x: float
    y: float
    size: float                # 描画半径の目安（creature の base_size 系 or WorldObject の pickup_radius / radius）
    is_creature: bool
    species_name: Optional[str] = None   # kind == "creature" の場合のみ有効
    is_alive: bool = True
    # 将来必要なら: color_hint: tuple, fill_ratio: float などを追加（後方互換で拡張可）
```

```python
def get_hunt_target_view(creature) -> Optional[TargetView]:
    """creature の現在の HuntAction ターゲットのビューを返す。
    対象なし / Action なし なら None。
    Game 内部で get_hunt_target + is_field_pickup などで判別して構築。
    """

def get_combat_target_view(creature) -> Optional[TargetView]:
    """同様に CombatAction のターゲットビュー。"""
```

（任意）`get_aggression_target_view(creature)` で両方をまとめて返すラッパーも便利かも。

## 6. Client側での使用イメージ（追加後に置き換え予定）
```python
# renderer.py など
from src.game import client_api

# ...
hunt_view = client_api.get_hunt_target_view(sc)
if hunt_view and (not hunt_view.is_creature or
                  species_visibility.is_species_visible(hunt_view.species_name)):
    # 位置は view から
    sx, sy = camera.world_to_screen(hunt_view.x, hunt_view.y)
    self._draw_hunt_link(...)  # 必要なら view 対応に
    # marker も size = hunt_view.size を使って描画
    ...

# HUD テキスト
if hunt_view:
    texts.append(f"狩り対象: {hunt_view.name}")
elif ... :
    ...
```

- `species_visibility.is_creature_visible` の呼び出しは creature のみ（view.is_creature チェック後）。
- 現在の `_safe_describe_target`, 直接 `get_hunt_target` + `describe_creature_short` 呼び出しを撤去可能。
- `_draw_prey_marker` なども view ベースにすれば raw target をほとんど触らなくて済む。
- `find_attackers_for_target`（返り値が creature list）や attackers 側の処理は現状のままでも OK（攻撃者は常に creature）。

## 7. Game側実装のヒント
- client_api.py 内に閉じて実装（内部で `from src.sim.utils.hunt_helpers import get_hunt_target, get_combat_target` などは許可）。
- `from src.sim.utils.field_pickup_helpers import is_field_pickup, pickup_radius`
- WorldObject かどうかの判別: `is_field_pickup(target) or (target is not None and not getattr(target, "alive", True))`
- name の構築: creature の場合は既存の `describe_creature_short` 相当を使い、WO の場合は `target.label or "carcass" or f"biomass ({target.fill_ratio*100:.0f}%)"` など適切なもの。
- size: creature → `base_size` 系、WO → `pickup_radius(target)` や `target.radius`
- 位置: `entity_xy` 相当で x, y を取る（WO も対応済み）。
- 既存の `hunt_helpers.py` や `describe_creature_short` は**そのまま残して構わない**（Game内部、テスト、Sim 側でまだ使われているため）。
- 可能なら `GameController` の on_tick などで軽く事前解決せず、Client から呼ばれたときに resolve（または state に軽く持つ）。
- 後方互換: 最初はシンプルなフィールドだけ。必要に応じて拡張。

CombatAction は現在 creature 中心だが、同じビュー型で統一すると Client コードがきれい。

## 8. 影響範囲と移行ステップ
- **主な Client 変更箇所**（API 追加後に私が担当）:
  - `src/client/rendering/renderer.py` の `_draw_hunt_overlays`, `_draw_prey_marker`, `draw` 内の HUD テキスト構築。
  - 必要なら `species_visibility` の呼び出しガードをビュー判断に置き換え。
- **テスト**:
  - 既存 client テスト + contracts。
  - 追加で「creature target の場合」と「WorldObject target の場合」の両方で draw できるモックテストを Client 側に足せると良い。
- **ドキュメント更新**（Game側で API 追加時に一緒に）:
  - `docs/Layer_Interfaces.md` の client_api テーブルに `TargetView` / `get_hunt_target_view` などを追記。
  - このドキュメント or `docs/Client_Game_Layer_Boundary_for_Parallel_AI_Development.md` の変更履歴に追記。
- **Client 側の後始末**: ワークアラウンド（_safe_describe など）をビュー使用に置き換え後、不要になれば簡素化。直接 hunt_helpers 依存を減らせる。
- 影響する可能性のある他の場所: デバッグログ、メッセージフィードなどで target を文字列化している箇所（あれば同様にビュー推奨）。

## 9. 関連ファイル（参考）
- Client 現在のワークアラウンド: `src/client/rendering/renderer.py`, `src/client/species_visibility.py`
- Game の target 設定: `src/game/ai/hunt_actions.py`（_find_prey, execute, _is_field_carcass_prey など）、`src/game/ai/combat_actions.py`
- ヘルパー: `src/sim/utils/hunt_helpers.py`, `src/sim/utils/field_pickup_helpers.py`, `src/sim/combat/pickup_target.py`
- 既存 client_api パターン: `find_queen_reproduction_action`, `get_queen_reproduction_readiness`, `GamePhaseView`
- 境界ドキュメント: `docs/Client_Game_Layer_Boundary_for_Parallel_AI_Development.md`, `docs/Layer_Interfaces.md`

## 10. まとめ・お願い
設計上、Client が生の target を直接触って creature か WorldObject かを推測するより、**Game が「Client が描画に必要な情報だけをまとめたビュー」として提供する**方がきれいです。queen reproduction の隠蔽と同じ方向性で、並行開発が今後も安全に続けられます。

---

## 11. 完了確認（Client担当）
- Game 実装確認: `client_api.py` に `TargetView` + 3 view 関数追加済み。
- Client 移行確認: `renderer.py` の HUD/オーバーレイが view ベースに完全移行。`_safe_describe_target` など撤去。
- テスト: `tests/game/test_client_api_target_view.py` 全 pass、contracts pass、client/ pass。
- 統合検証: headless GameApp + WO target / creature target 両方で `draw()` 成功確認。
- ドキュメント: Boundary で「完了」リスト化、Layer_Interfaces 更新、Response ドキュメント参照。
- 残: `species_visibility.is_creature_visible` の防御ガードは攻撃者など他経路用に残置（ビュー経由のターゲット処理では不要）。
- 推奨: 今後「選択個体のターゲット」関連の Client コードは必ず `client_api.get_*_target_view` を使用。

**ステータス**: ✅ すべて完了。Client 側確認済み（2026-06）。

可能であればこの API を追加していただけると助かります。追加されたらシグネチャ・戻り値の例を共有いただければ、すぐに Client 側をそれに合わせて更新します。

質問や「もっとシンプルに（例: タプルで返す、または name + pos だけ）」などの代替案があれば、遠慮なく提案してください。Game の意図を最もきれいに表現できる形にしたいです。

---
**共有用文言ここまで**

このファイル全体を CursorAI / Game担当に渡すか、主要セクション（特に 4. 設計理由 + 5. 提案API + 6. 使用イメージ + 7. 実装ヒント）をコピーして伝えてください。
追加で「先日 Client で zoom + 選択リング修正した直後にこのエラーが出た。Client は現在 defensive fix で動くようにはしてあるが、根本は Game 側で抽象化してほしい」と文脈を添えると良いです。

Client担当として、API が入ったら速やかに移行して、直接的な hunt_helpers 依存をこの部分から減らします。
