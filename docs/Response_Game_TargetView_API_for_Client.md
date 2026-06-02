# Game層からの回答: TargetView API 追加完了（Client担当AI向け）

**日付**: 2026-06  
**依頼元**: [Request_Game_Add_TargetView_API_for_Client_HuntOverlays.md](./Request_Game_Add_TargetView_API_for_Client_HuntOverlays.md)  
**境界ドキュメント**: [Client_Game_Layer_Boundary_for_Parallel_AI_Development.md](./Client_Game_Layer_Boundary_for_Parallel_AI_Development.md)

---

## 1. 対応内容（要約）

Game層に **`TargetView`** と **`get_hunt_target_view` / `get_combat_target_view` / `get_aggression_target_view`** を `src/game/client_api.py` に追加しました。

HuntAction の `_target` が **creature / WorldObject / PickupTarget** のいずれでも、Client は **`.species` や生の `_target` に触らず** 描画・HUD に必要な情報だけを受け取れます。

**Client 側の移行も実施済み**（`src/client/rendering/renderer.py`）。ワークアラウンド（`_safe_describe_target`、生 `get_hunt_target` によるオーバーレイ描画）は撤去済みです。`species_visibility.is_creature_visible` の非 creature ガードは、攻撃者リストなど他経路用に残しています。

---

## 2. 公開 API（シグネチャ）

```python
from src.game import client_api

# 型
view: client_api.TargetView | None

# 関数
client_api.get_hunt_target_view(creature) -> TargetView | None
client_api.get_combat_target_view(creature) -> TargetView | None
client_api.get_aggression_target_view(creature) -> TargetView | None  # 戦闘優先
```

### `TargetView` フィールド

| フィールド | 型 | 意味 |
|-----------|-----|------|
| `kind` | `str` | `"creature"` \| `"carcass"` \| `"field_biomass"` \| `"other"` |
| `name` | `str` | HUD・ラベル用（例: `"Spider (生体)"`, `"patch (field 40%)"`） |
| `x`, `y` | `float` | ワールド座標 |
| `size` | `float` | マーカー半径の目安（creature: `traits.base_size`、WO: `pickup_radius` / `radius`） |
| `is_creature` | `bool` | 生きた個体ターゲットなら `True` |
| `species_name` | `str \| None` | `kind == "creature"` のとき種名。それ以外は `None` |
| `is_alive` | `bool` | 対象の生存フラグ（死骸・フィールド biomass は `False` 相当） |

**後方互換**: フィールド追加は dataclass のデフォルト値で拡張可能。既存 Client コードはそのまま動きます。

---

## 3. Client での使い方（推奨パターン）

### HUD テキスト

```python
combat_view = client_api.get_combat_target_view(selected_creature)
hunt_view = client_api.get_hunt_target_view(selected_creature)
if combat_view is not None:
    texts.append(f"戦闘対象: {combat_view.name}")
elif hunt_view is not None:
    texts.append(f"狩り対象: {hunt_view.name}")
```

### 種族表示フィルタ（オーバーレイ）

```python
def _target_view_visible(view, species_visibility):
    if view is None:
        return False
    if species_visibility is None:
        return True
    if not view.is_creature or view.species_name is None:
        return True  # carcass / field biomass は常に表示
    return species_visibility.is_species_visible(view.species_name)
```

### 線・マーカー描画

```python
# 座標・サイズは view から（entity_xy(raw_target) 不要）
sx, sy = camera.world_to_screen(view.x, view.y)
radius = int(view.size)
```

### まだ `hunt_helpers` を使ってよい箇所

| 用途 | 推奨 |
|------|------|
| `find_attackers_for_target(world, creature)` | ✅ そのまま（返り値は常に creature） |
| `get_combat_target(attacker) is sc` | ✅ 同一性判定用（軽量） |
| `get_hunt_target` / `get_combat_target` で HUD・マーカー | ❌ `get_*_target_view` に置換済み |

---

## 4. 実装の内部（Client は知らなくてよい）

- `client_api` 内で `get_hunt_target` / `get_combat_target`（`src/sim/utils/hunt_helpers.py`）を呼び、`_target` を正規化。
- `PickupTarget` は `world_object` に展開。座標は `PickupTarget.position()` または `entity_xy`。
- `kind` 判別: `is_field_pickup`、`.species` の有無、`alive` など（Request ドキュメント §7 通り）。

Game 側が HuntAction の target 解決を変えても、**この関数の戻り値契約を守れば Client は壊れません**。

---

## 5. テスト

```bash
python -m pytest tests/game/test_client_api_target_view.py -q
python -m pytest tests/contracts/test_layer_imports.py -q
```

カバー内容:

- creature ターゲット（Hunt / Combat）
- field `WorldObject` ターゲット
- `PickupTarget` ラッパー
- ターゲットなし → `None`
- `get_aggression_target_view` の戦闘優先

---

## 6. Client 担当が確認・残作業（任意）

| 項目 | 状態 |
|------|------|
| `renderer.py` HUD / 狩りオーバーレイ | ✅ 移行済み |
| `_safe_describe_target` 撤去 | ✅ |
| `species_visibility` の WO ガード | 残置（他経路の防御。ビュー経由なら必須ではない） |
| 他ファイルで `get_hunt_target` を HUD に使用 | 現状 `renderer.py` のみだったため対応済み |
| Client 専用テスト（WO target で draw） | 任意で追加可 |

新規 Client 機能で「選択個体のターゲット」を表示するときは、**必ず `client_api.get_*_target_view` を使ってください**。生の `_target` や `hunt_helpers.get_hunt_target` の結果に `.species` を付けないでください。

---

**Client担当確認（追記）**:
- 2026-06: 上記項目を確認。`renderer.py` の移行は適切（view ベースの `_draw_target_view_marker` / `_draw_hunt_link_to_view` / `_target_view_visible_for_overlay` 使用）。
- 攻撃者関連は `find_attackers_for_target` + `get_combat_target( ) is sc` + `describe_creature_short` のまま（doc 許可）。
- `species_visibility` の非creatureガードは残置（防御的、他経路用）。
- 追加検証: テスト全 pass + headless draw (WO + creature target) 成功。
- 問題なし。以降の Client 開発では view API を使用。

---

## 7. 関連ドキュメント更新

- `docs/Layer_Interfaces.md` — client_api 表に `TargetView` 追記
- `docs/Client_Game_Layer_Boundary_for_Parallel_AI_Development.md` — オープン依頼を完了に更新、公開リスト追記

---

## 8. 質問・拡張

将来 HUD に色や備蓄率が必要なら、`TargetView` にオプショナルフィールド（例: `fill_ratio: float | None`）を追加します。Client 側から要望があれば Boundary ドキュメントの依頼セクションに追記してください。
