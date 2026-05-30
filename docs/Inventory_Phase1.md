# インベントリ Phase 1 設計書

全生物に共通する「持ち物（インベントリ）」を導入し、現行のアリ専用運搬（`ColonyComponent` のバイオマス運搬）を置き換える第一段階の仕様です。  
**本書の時点では実装しません。** 合意した方針と変更範囲の共有用です。

---

## 1. 目的

| 目的 | 説明 |
|------|------|
| 汎化 | 運搬を「アリのコロニー専用フラグ」から、**すべての生物が持てるインベントリ**へ移す |
| 拡張性 | スロット（枠）は将来、バイオマス以外のアイテムも入る**共通の入れ物**とする |
| 体感 | **総重量**に応じて移動速度が落ちる（Phase 1 で式と配線まで行う） |
| 社会性との分離 | 巣への預け入れ・帰巣は**コロニー行動**として残しつつ、「何を持っているか」は生物本体の責務とする |

「アリの社会性を模倣した小人」など、コロニーが無い種でも **箱と重量・速度** のルールは同じにできるようにする。

---

## 2. 合意したルール（設計判断）

### 2.1 空きスロットの選び方

- 拾う・入れるときは **先頭から見て、最初の空きスロット** に入れる。
- 優先スロットや種別ごとの割当ては Phase 1 では行わない。

### 2.2 死骸からのチャンク

- 1 回の拾い操作で、**空きスロットの数だけ**チャンクを切り出す（枠が 1 なら 1 チャンク、3 なら最大 3 チャンク）。
- 各チャンクは **そのスロットの入力量上限（`max_mass`）** まで。死骸に残量が足りなければ、取れる分だけ各枠に入れる。

### 2.3 重量（`weight`）

- **すべてのアイテムは重量を持つ**（Phase 1 で実装するのはバイオマスのみ）。
- 表示・速度計算に使う重量は、**アイテム定義から計算**する（例: バイオマス量 × 単位重量）。
- **複数スロットをまたぐ 1 個のアイテム**（大きい荷物）は Phase 1 では考慮しない。常に **1 スロット = 最大 1 アイテム**。

### 2.4 コロニー・巣との関係

- **インベントリ = アイテム管理の箱**。コロニーの有無や巣の有無と**独立**。
- **総重量は常に速度に影響**する（帰巣中か、戦闘中か、隠れ中かは問わない。隠れ中の移動禁止など、既存の別ルールはそのまま）。
- 巣への預け入れ（`deposit`）は「コロニー＋巣システムの行動」だが、預ける**中身の読み取り元**は `ColonyComponent` ではなく **`InventoryComponent`** に統一する。

### 2.5 表示（HUD）

- インベントリに入っている **アイテム一覧**（Phase 1 はバイオマスのみ）。
- **総重量**（全スロットの合計）。

---

## 3. 現状と Phase 1 後の責務分担

### 3.1 現状（置き換え対象）

| 場所 | 内容 |
|------|------|
| `ColonyComponent` | `carried_biomass`, `carried_carcass`, `is_carrying` |
| `get_haul_max_carry` | `ReturnToNestAction` の JSON から上限を読む |
| `try_pickup_carcass` 等 | コロニー必須・1 チャンクのみ |
| 各 Action | `colony.is_carrying` で分岐 |

### 3.2 Phase 1 後

| コンポーネント | 責務 |
|----------------|------|
| **`InventoryComponent`**（全 `Creature`） | スロット配列、入力量、総重量、空き判定、速度倍率の材料 |
| **`BiomassItem`**（アイテム型の一種） | バイオマス量、元死骸参照（任意）、重量計算 |
| **`ColonyComponent`** | 巣 ID・敗北フラグのみ（運搬フィールドは削除） |
| **`NestSystem.deposit_*`** | インベントリ内のバイオマスを巣の食料へ移す（コロニー所属者向け） |
| **種 JSON `inventory`** | 枠数・枠ごとの上限・単位重量・速度参照重量 |

---

## 4. データ構造（概念）

### 4.1 インベントリ（`InventoryComponent`）

- **`slots`**: スロットの配列。長さ = **`slot_count`**（種定義）。
- 各 **スロット（`InventorySlot`）**:
  - **`item`**: 入っているアイテム、または空（`None`）
  - **`max_mass`**: この枠に入れられるバイオマス量の上限（Phase 1 では主にバイオマス用）
  - **`allowed_kinds`**: 入れられるアイテム種別（Phase 1 は `["biomass"]` のみ）

派生プロパティ（コード上のヘルパ）:

| 名前 | 意味 |
|------|------|
| `is_loaded` | いずれかのスロットにアイテムがある |
| `total_weight` | 全スロットのアイテム重量の合計 |
| `first_empty_slot_index` | 最初の空きスロット番号（無ければ `None`） |
| `empty_slot_count` | 空きスロット数 |

### 4.2 アイテム（`InventoryItem` 基底）

- **`kind`**: 種別文字列（Phase 1 は `"biomass"` のみ）。
- **`weight`**: そのアイテムの重量（プロパティまたはメソッドで算出）。

**バイオマスアイテム（`BiomassItem`）**

| フィールド | 意味 |
|------------|------|
| `amount` | バイオマス量 |
| `source_carcass` | 切り出し元の死骸（現行の `carried_carcass` 相当、任意） |
| 重量 | `amount × biomass_weight_per_unit`（種または世界共通の係数） |

### 4.3 種定義 JSON（例: 働きアリ）

```json
"inventory": {
  "slot_count": 1,
  "slots": [
    {
      "max_mass": 100,
      "allowed_kinds": ["biomass"]
    }
  ],
  "biomass_weight_per_unit": 1.0,
  "carry_speed_reference_weight": 80
}
```

| キー | 意味 |
|------|------|
| `slot_count` | スロット数（枠数） |
| `slots[].max_mass` | 枠ごとのバイオマス入力量上限 |
| `slots[].allowed_kinds` | 入れ可能な `kind`（Phase 1 は `biomass` のみ） |
| `biomass_weight_per_unit` | バイオマス 1 単位あたりの重量 |
| `carry_speed_reference_weight` | 速度低下の基準重量（大きいほど、同じ荷物で遅くなりにくい） |

**移行**: 既存の `ReturnToNestAction.params.base_max_carry` は、**スロット 0 の `max_mass` に吸収**し、二重定義をやめる。

コロニー無しの種（アメーバ・クモなど）も同じ `inventory` ブロックを書ける。`slot_count: 0` ならインベントリ無し（重量 0）でもよい。

---

## 5. 速度への影響

- **適用箇所**: `get_current_speed()`（または移動系が参照する速度の単一入口）で、**総重量**から倍率を掛ける。
- **式（案・Phase 1 で採用する想定）**:

  ```
  速度倍率 = 1 / (1 + 総重量 / carry_speed_reference_weight)
  実効速度 = base_speed × 種のその他倍率 × 速度倍率
  ```

- **コロニー・行動に依存しない**（帰巣・狩り・隠れと無関係に、荷物があれば遅い）。
- Phase 2 で「運搬専用の追加ペナルティ」を足すかは別判断。Phase 1 は**重量のみ**。

---

## 6. 操作の振る舞い（Phase 1）

### 6.1 拾う（`try_pickup_carcass` → インベントリ API に改名・一般化）

1. 対象が食べられる死骸であること（現行と同様）。
2. 接触範囲内であること。
3. **空きスロット数**を数える。0 なら失敗。
4. スロット **0 → 1 → …** の順で、空きごとに:
   - 死骸の残量と当該スロットの `max_mass` の小さい方をチャンクとする。
   - `BiomassItem` を生成してスロットに入れる。
   - 死骸の `remaining_biomass` を減らす。
5. 死骸が枯渇したらフィールドから削除（現行と同様）。

### 6.2 預ける（巣・コロニーあり）

- `NestSystem.deposit_carried` を **`deposit_inventory_biomass`** 等に発展させ、**インベントリ内のすべてのバイオマス**（または全スロット）を巣の `stored_food` へ移す。
- コロニー未所属・巣なしの生物は呼ばない（行動側で従来どおりガード）。

### 6.3 その場で食べる（`consume_carried_biomass`）

- 対象はインベントリ内バイオマス（Phase 1 は「運搬チャンクをかじる」＝実質 1 スロット目または全バイオマススロットの先頭から消費、**現行挙動に近い 1 口ずつ**を維持）。
- コロニー必須チェックをやめ、**インベントリにバイオマスがあれば**実行可能にする（コロニー無し種の将来用）。

### 6.4 放す（`release_carried_carcass`）

- インベントリのバイオマスを元死骸へ戻す／マナ還元（現行ロジックをスロット単位に拡張）。

### 6.5 判定の置き換え

| 現行 | Phase 1 |
|------|---------|
| `colony.is_carrying` | `inventory.is_loaded` |
| `get_haul_max_carry(creature)` | `inventory.slot_max_mass(i)` またはスロット設定の参照 |
| `colony.carried_biomass` | 該当スロットの `BiomassItem.amount` |

**行動 AI**（`ReturnToNestAction`, `ScavengeCarriedAction`, `SeekShelterAction`, `UtilityMind` の運搬維持など）は **`inventory.is_loaded`** を参照するよう変更。

---

## 7. 表示（HUD）

選択個体のパネル（現行 `format_carry_status` の置き換え）:

```
インベントリ:
  [1] バイオマス 42.0 / 100.0  (重量 42.0)
総重量: 42.0
```

- Phase 1 は **バイオマス行のみ**。スロット番号・量／上限・行ごとの重量。
- **総重量**は常に最後に 1 行表示。
- 空のときは「インベントリ: 空」または「総重量: 0」。

---

## 8. 変更ファイル一覧（実装時の目安）

| 区分 | ファイル／領域 |
|------|----------------|
| 新規 | `src/components/inventory.py`（コンポーネント＋`BiomassItem`） |
| 新規 | `src/utils/inventory_helpers.py`（拾う・預ける・食べる・重量・HUD 文面） |
| 変更 | `src/entities/creature.py`（生成時に `InventoryComponent` を種定義から構築） |
| 変更 | `src/components/colony.py`（運搬フィールド削除） |
| 変更 | `src/utils/combat_helpers.py`（pickup / release をインベントリ経由） |
| 変更 | `src/utils/nutrition_helpers.py`（`get_haul_max_carry` 削除またはインベントリ委譲） |
| 変更 | `src/systems/nest_system.py`（deposit の読み取り元） |
| 変更 | `src/ai/actions/colony.py`, `predation.py`, `mind.py`, `shelter.py` 等（`is_carrying` → `is_loaded`） |
| 変更 | 速度算出（`MetabolismComponent` または `Creature.get_current_speed`） |
| 変更 | `config/species/*_ant.json`（`inventory` ブロック追加、`base_max_carry` 統合） |
| 変更 | `docs/Species_JSON_Spec.md`（`inventory` セクション追加） |
| テスト | `test_chunk_carry.py`, `test_ant_nest.py`, `test_hunger_behavior.py` 等の更新＋インベントリ単体テスト |

---

## 9. Phase 1 に含めないもの

- バイオマス以外のアイテムの実装（`kind` の枠だけ用意）。
- 複数スロットを占有する 1 アイテム。
- クモ 3 枠のバランス・行動（データは書けるが、必須ではない）。
- 運搬中に餌を捨てて逃げる（以前の Phase 2 案）。
- 非コロニー種向けの「巣以外への deposit」。

---

## 10. 受け入れ条件（実装後の確認用）

1. 働きアリが死骸から拾うと、**枠数分**チャンクが入り、HUD にバイオマスと**総重量**が出る。
2. 荷物があるとき **誰でも**（コロニー無し含む）移動が遅くなる。荷物がなければ従来速度。
3. 帰巣・預け入れ・その場消費が、**インベントリ API** だけで完結し、`ColonyComponent` にバイオマス量が無い。
4. 既存のチャンク運搬・満タン巣・飢餓時のその場食事テストが、インベントリ版に更新されて通る。

---

## 11. 用語対照（コード名）

| 日本語 | コード上の名前（目安） |
|--------|------------------------|
| インベントリ | `InventoryComponent` |
| スロット（枠） | `InventorySlot` |
| アイテム | `InventoryItem` |
| バイオマスアイテム | `BiomassItem` |
| 入力量上限 | `max_mass` |
| 総重量 | `total_weight` |
| 何か持っている | `is_loaded` |
| 速度の基準重量 | `carry_speed_reference_weight` |
| バイオマス単位重量 | `biomass_weight_per_unit` |

---

*最終更新: Phase 1 設計合意（実装前）*
