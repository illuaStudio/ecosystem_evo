# object_types スキーマ（Phase 0）

`config/sim/object_types/*.json` はマップ上に置けるオブジェクト**型**のカタログ。
各型は **capabilities**（能力の組み合わせ）で定義する。

## トップレベル

| キー | 必須 | 説明 |
|------|------|------|
| `id` | ✓ | 型 ID（ファイル名と一致推奨） |
| `label` | | エディタ表示名 |
| `category` | | エディタ分類ヒント（`obstacle` / `zone` / `colony`）。実行時は capabilities が優先 |
| `capabilities` | ✓ | 能力ブロック（下記） |

レガシー flat フィールド（`shape`, `hp_drain_per_dt` 等）も読み込めるが、新規型は `capabilities` を使う。

## capabilities ブロック

| 能力 | 用途 | 主なフィールド |
|------|------|----------------|
| `collision` | 当たり判定 | `shape` (`circle`/`rect`), `radius`, `width`, `height` |
| `zone` | エリア効果 | 上記形状 + `hp_regen_per_dt`, `hp_drain_per_dt`, `field_tags`, `spawn_rate_multiplier` |
| `storage` | 貯蔵（ItemStack） | `max_food`, `initial_stored_food`, `slot_count`, `slots[]` |
| `access` | 接続点（隠れ・預け入れ・取出） | `role`, `shelter`, `deposit` / `deposit_access`, `withdraw` / `withdraw_access` |
| `combat` | 破壊可能 | `max_hp`, `hp` |
| `compound` | 親子 compound | `role`, `profile` (`colony`/`generic`), `default_access_type`, `visible` |
| `render` | 見た目（将来拡張） | `color`, `sprite` |

1つの型が複数能力を持てる（例: 当たり判定 + 回復エリア + 描画色）。

## 例

### 岩（当たりのみ）

```json
{
  "id": "rock",
  "label": "岩",
  "category": "obstacle",
  "capabilities": {
    "collision": { "shape": "circle", "radius": 22 },
    "render": { "color": [118, 112, 102] }
  }
}
```

### 毒霧（エリアのみ）

```json
{
  "id": "poison_fog",
  "label": "毒霧",
  "category": "zone",
  "capabilities": {
    "zone": {
      "shape": "circle",
      "radius": 95,
      "hp_drain_per_dt": 0.07,
      "field_tags": ["poison"]
    }
  }
}
```

### コロニー親（貯蔵）

```json
{
  "id": "affiliation_site",
  "capabilities": {
    "storage": { "max_food": 5000, "initial_stored_food": 80 },
    "compound": { "role": "root" }
  }
}
```

### 接続点（隠れ + 預け入れ + 戦闘）

```json
{
  "id": "affiliation_access",
  "capabilities": {
    "access": { "role": "access", "shelter": true, "deposit": true },
    "combat": { "max_hp": 120 }
  }
}
```

## マップ配置（instances）

`world.json` の `instances[]` で型を参照し、インスタンス単位で上書きできる。

```json
{
  "layer": "zone",
  "type": "poison_belt",
  "x": 520,
  "y": 620,
  "capabilities": {
    "zone": { "width": 240 }
  }
}
```

フラット上書き（`radius`, `hp_drain_per_dt` 等）も引き続き有効。

## 正規化 API

`src/sim/utils/object_capabilities.py`

- `normalize_capabilities(raw)` — レガシー → capabilities 統合
- `merge_type_with_instance(type_def, instance)` — 型 + 配置のマージ
- `zone_effects_from_data(merged)` — ZoneEffects 構築
- `resolve_geometry(merged, capability="zone"|"collision", ...)` — 形状解決

## Phase 2: compound 親子（共有 storage）

| 配置 layer | 役割 | legacy エイリアス |
|------------|------|-------------------|
| `compound_root` | storage 親 | `colony_site`, `nest` |
| `compound_access` | 接続点 | `colony_access` |

ランタイム API: `world.compound_system`（`get_root`, `add_access_point`, `find_nearest_access`, `damage_access` 等）。

リンク宝箱例:

```json
{ "id": "dungeon_loot", "layer": "compound_root", "type": "storage_hub", "x": 0, "y": 0 },
{ "id": "chest_a", "layer": "compound_access", "type": "linked_chest", "parent": "dungeon_loot", "x": 100, "y": 200 },
{ "id": "chest_b", "layer": "compound_access", "type": "linked_chest", "parent": "dungeon_loot", "x": 500, "y": 300 }
```

`chest_a` / `chest_b` は同じ `dungeon_loot.storage` を参照する。

コロニーは `compound.profile: "colony"` 付き `colony_site` として同じ仕組みを使う（敗北・テリトリーは `NestSystem`）。

## Phase 4: ItemStack（バイオマスのアイテム化）

- `ObjectStorage` は内部で `ItemStack`（スロット列）を持つ
- 生物 `InventoryComponent` と同型の `InventorySlot` / `InventoryItem`
- バイオマス = `BiomassItem`（`kind: "biomass"`）。将来の剣等 = `StackItem`（`kind: "item"`）
- `stored_food` / `max_food` はバイオマス量の**互換 API**（中身は ItemStack）
- 移動 API: `src/sim/utils/item_stack_helpers.py`
  - `transfer_biomass_creature_to_storage`
  - `transfer_biomass_storage_to_creature`
- 配置 API: `deposit_carried_to_parent` / `withdraw_biomass_from_parent`
