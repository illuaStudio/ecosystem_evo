# 生物JSON定義 共通仕様書

このファイルは全生物（Amoeba, Predator, Plant, Herbivore など）の `config/species/*.json` の構造と各パラメータの意味を定義します。

**実装の参照先:** `species.py`（読み込み・正規化）、`mind.py`（行動選択）、`actions.py`（各 Action のデフォルト値）

---

## ファイルの置き場所

| 項目 | 内容 |
|------|------|
| ディレクトリ | `config/species/` |
| ファイル名 | 任意（例: `amoeba.json`）。ゲーム内の識別は JSON 内の **`name`** フィールドで行う |
| 読み込み | `config.py` がフォルダ内の全 `.json` を読み、`name` をキーに辞書化する |

---

## 全体構造

```json
{
  "name": "Amoeba",
  "color": [180, 100, 220],
  "description": "（任意）UIやデバッグ用の短い説明",
  "life_cycle": {
    "mature": 280,
    "elder": 1800,
    "death": 3500
  },
  "traits": {
    "base_size": 9.0,
    "max_size": 18.0,
    "growth_rate": 0.008,
    "base_speed": 1.8,
    "base_vision": 140,
    "max_hp": 60.0,
    "max_satiety": 45.0,
    "metabolism_rate": 0.55
  },
  "mind": {
    "type": "utility",
    "actions": [
      {
        "name": "ManaWanderAction",
        "weight": 1.0,
        "description": "（任意）設計メモ",
        "params": { }
      }
    ]
  }
}
```

### トップレベルフィールド一覧

| キー | 型 | 必須 | 意味 |
|------|----|------|------|
| name | string | **必須** | 種族名。`CreatureFactory` / `Species.create("Amoeba")` などで参照する ID |
| color | [int, int, int] | 推奨 | 描画色 RGB（0〜255）。省略時は `[120, 200, 120]` |
| description | string | 任意 | 種の説明文（現状は Species に保持するのみ） |
| life_cycle | object | 条件付き | 年齢ステージ・寿命。省略可（後述） |
| traits | object | 推奨 | 身体・基礎能力。欠損キーは `species.py` のデフォルトで補完 |
| mind | object | 推奨 | 行動 AI。省略時は空の actions リスト |
| colony | object | 任意 | コロニー（巣）行動。`enabled: true` で巣システムに参加（主に Predator） |

---

## 詳細説明

### life_cycle（寿命・成長段階）

**年齢（ティック）に応じたライフステージ**を定義します。`creature_helpers.LIFE_STAGE_PIPELINE` に従い、次の段階に進みます。

| 年齢の範囲 | ステージ名 | 境界キー |
|------------|------------|----------|
| `age < mature` | Juvenile（幼体） | mature |
| `mature ≤ age < elder` | Adult（成体） | elder |
| `elder ≤ age < death` | Elder（老齢） | death |
| `age ≥ death` | 自然死（表示上は Expired 扱いの前に死亡処理） | — |

**省略した場合:** `life_cycle` が空の種（例: Predator）は常に Adult 扱いとなり、自然死・ステージ UI は無効になります。

| キー | 型 | 意味 | 例 |
|------|----|------|----|
| mature | int | 成熟年齢。この年齢以降、SplitAction など `life_cycle.mature` を参照する繁殖が可能 | 280 |
| elder | int | 老化開始年齢（Adult → Elder の境界） | 1800 |
| death | int | 寿命。この年齢で自然死（HP 0 → 死骸化） | 3500 |

> **設計上の注意:** 3 キーすべてを書くことが望ましいです。一部だけ書いた場合、未定義の境界はスキップされ、パイプライン上の判定がずれることがあります。

---

### traits（生物の基礎能力）

**身体特性のみ**をここに置きます。行動固有の数値（マナ吸収率、分裂条件など）は **`mind.actions[].params`** に書き、traits には入れません（`species.ESSENTIAL_TRAIT_KEYS` でフィルタされます）。

| キー | 型 | 意味 | 調整の目安 | デフォルト（省略時） |
|------|----|------|-----------|---------------------|
| base_size | float | 初期サイズ（表示・当たり判定・成長の現在値） | 6.0〜20.0 | 9.0 |
| max_size | float | 成長上限サイズ。`growth_rate > 0` のとき満腹度に応じて `base_size` が増加 | base_size の 1.5〜2.5 倍 | base_size と同じ |
| growth_rate | float | 1 ティックあたりの成長量（× 満腹度比率）。0 で成長なし | 0.005〜0.015 | 0.0 |
| base_speed | float | 基本移動速度（各 Action の `speed_multiplier` と掛け算） | 1.0〜4.0 | 1.0 |
| base_vision | float | 視界半径（ピクセル）。ChaseAction の獲物探索に使用 | 80〜300 | 120.0 |
| max_hp | float | 最大体力 | 40〜150 | 100.0 |
| max_satiety | float | 最大満腹度 | 30〜120 | 80.0 |
| metabolism_rate | float | 1 ティックあたりの満腹度減少。大きいほど空腹になりやすい | 0.3〜1.2 | 0.5 |

**ゲーム内での使われ方（参考）**

- 毎ティック: `satiety -= metabolism_rate`。満腹度が 0 を下回ると HP が減少
- 成長: 生存中かつ `base_size < max_size` のとき、`growth_rate × satiety_ratio` だけ `base_size` 増加
- 分裂後: SplitAction が親の `base_size` に `size_reduction` を乗算

---

### mind（行動 AI）

| キー | 型 | 意味 |
|------|----|------|
| type | string | 現在は **`"utility"`** のみ（Utility AI: 各 Action の utility × weight で最大スコアを選択） |
| actions | array | 利用可能な行動のリスト（下記） |

**行動選択の流れ**

1. `actions` の各要素について `name` でクラスを解決し、`params` でインスタンス化
2. `calculate_utility(creature) × weight` が最大の Action を採用
3. 前ティックと同型で未完了の Action があれば、そのインスタンスを継続（ChaseAction のターゲット保持など）
4. 有効な Action が一つもない場合は **WanderAction** にフォールバック

#### actions（行動一覧）— 共通フィールド

各行動オブジェクトは次の形です。

```json
{
  "name": "SplitAction",
  "weight": 0.9,
  "description": "任意の設計メモ（実行時は無視）",
  "params": { }
}
```

| キー | 型 | 必須 | 意味 |
|------|----|------|------|
| name | string | **必須** | Action クラス名（`mind.ACTION_BY_NAME` に登録済みのもの） |
| weight | float | 任意 | 效用スコアの倍率。省略時 `1.0` |
| description | string | 任意 | 人間向けメモ。コードでは未使用 |
| params | object | 任意 | Action 固有パラメータ。省略時は `actions.py` の `DEFAULT_PARAMS` |

**登録済み Action 名:** `WanderAction`, `ManaWanderAction`, `ChaseAction`, `HuntAction`, `ReturnToNestAction`, `FeedAtNestAction`, `NestPatrolAction`, `SplitAction`

---

#### WanderAction の params

ランダム方向への徘徊。マナ回復はしない。

| キー | 型 | 意味 | デフォルト |
|------|----|------|-----------|
| angle_range | float | 1 ティックあたりの進路角度の乱れ（±度） | 30 |
| speed_multiplier | float | `base_speed` に対する移動倍率 | 0.85 |

---

#### ManaWanderAction の params

徘徊しながら `World.mana` から満腹度を回復（主に Amoeba 向け）。

| キー | 型 | 意味 | デフォルト |
|------|----|------|-----------|
| angle_range | float | 進路の乱れ（±度） | 30 |
| speed_multiplier | float | 移動倍率 | 0.85 |
| mana_absorption_rate | float | 1 ティックあたりの最大マナ吸収量（満腹度は max_satiety の 95% まで） | 0.8 |

**utility の目安:** 空腹度が高いほど選ばれやすい（0.75 + hunger × 0.25）

---

#### ChaseAction の params

視界内の指定種族を追跡し、接触時に噛みつき・死骸消費（Predator 向け）。

| キー | 型 | 意味 | デフォルト |
|------|----|------|-----------|
| target_type | string | 獲物の `species.name`（例: `"Amoeba"`） | `"Amoeba"` |
| speed_multiplier | float | 追跡時の移動倍率 | 1.25 |
| contact_padding | float | 接触判定の余白（サイズに加算） | 8.0 |
| bite_gain | float | 死骸消費時の満腹度変換効率 | 1.35 |
| attack_power | float | 生体への bite ダメージ倍率（実ダメージ = attack_power × 12） | 1.0 |

**utility の目安:** 視界内に獲物がいないと 0。空腹度が低い（&lt; 0.2）ときも 0。

---

#### colony（コロニー・巣）— Predator 向け

`colony.enabled: true` の種はワールド上に **巣（Nest）** を持ちます。

| キー | 型 | 意味 | デフォルト |
|------|----|------|-----------|
| enabled | bool | コロニー機能を有効化 | false |
| single_colony | bool | 同種はワールドに巣を1つだけ（初期スポーン・P 追加も既存巣へ） | true |
| join_radius | float | `single_colony: false` 時の合流半径（px） | 200 |
| deposit_radius | float | 持ち帰り判定半径（ReturnToNest と共有） | 30 |
| max_food | float | 巣の最大食料備蓄（旧 `max_storage` も可） | 400 |
| food_leak_rate | float | 1 ティックあたりの余剰食料の漏洩率（腐敗） | 0.0015 |
| food_to_mana_ratio | float | 漏洩食料のうちマナへ還流する比率 | 0.35 |
| food_leak_reserve_ratio | float | この割合までは漏洩しない（底上げ備蓄） | 0.12 |
| nest_x / nest_y | float | 巣が未作成時のスポーン原点（省略時はワールド中央） | 中央 |
| spawn_spread | float | 巣からのスポーンばらつき半径（px） | 28 |

**C 案（現状）:** 持ち帰りは **食料（バイオマス）** として `stored_food` に蓄える。コロニーは `FeedAtNest` で満腹度に変換。余剰は `food_leak_rate` で巣タイルへ **マナ還流** し、アメーバの生態系と接続する。

**観察のポイント:** 巣は茶色の円で表示。数字はコロニー人数。捕食者が死骸を運ぶと頭上ラベルが `↩` に変わる。

---

#### HuntAction の params

`ChaseAction` と違い **その場で食べない**。攻撃→殺害→死骸を拾い `ReturnToNestAction` へ渡す。

| キー | 型 | 意味 | デフォルト |
|------|----|------|-----------|
| target_type | string | 獲物の種名 | `"Amoeba"` |
| speed_multiplier | float | 追跡移動倍率 | 1.3 |
| contact_padding | float | 接触・拾い判定の余白 | 8.0 |
| attack_power | float | bite ダメージ倍率 | 1.2 |
| pickup_on_kill | bool | 殺害直後に死骸を拾う | true |

---

#### ReturnToNestAction の params

運搬中のみ高スコア。巣到達で死骸バイオマスを巣貯蔵へ移す。

| キー | 型 | 意味 | デフォルト |
|------|----|------|-----------|
| speed_multiplier | float | 帰巣移動倍率 | 1.1 |
| deposit_radius | float | 貯蔵判定半径 | 30 |

---

#### FeedAtNestAction の params

巣の貯蔵から満腹度を回復（コロニー共有の餌）。

| キー | 型 | 意味 | デフォルト |
|------|----|------|-----------|
| bite_gain | float | 貯蔵→満腹度の変換効率 | 1.2 |
| max_take_ratio | float | 1 ティックで巣から取れる最大比率 | 0.35 |
| feed_radius | float | 食事可能半径 | 36 |

---

#### NestPatrolAction の params

空腹が低いとき巣周辺を巡回。メンバーが多いほどやや選ばれやすい。

| キー | 型 | 意味 | デフォルト |
|------|----|------|-----------|
| angle_range | float | 徘徊の角度乱れ | 40 |
| speed_multiplier | float | 移動倍率 | 0.75 |
| patrol_radius | float | 巣からの巡回半径 | 130 |
| nest_pull_strength | float | 巣方向への引き寄せ（0〜1） | 0.55 |

---

#### SplitAction の params

無性分裂（ReproductionAction 系）。条件を満たすと 1 子を隣接生成し、親は縮小・満腹度消費・クールダウン。

**実行条件（すべて必須）**

- 生存・ワールド在籍
- `repro_cooldown == 0`
- `age >= life_cycle.mature`（**mature 未定義の種では分裂不可**）
- `base_size >= min_reproduce_size`
- `satiety / max_satiety >= satiety_threshold`

| キー | 型 | 意味 | デフォルト |
|------|----|------|-----------|
| satiety_threshold | float | 分裂可能な満腹度比率（0〜1） | 0.75 |
| energy_cost | float | 分裂時に消費する満腹度（max_satiety に対する比率） | 0.39 |
| min_reproduce_size | float | 分裂に必要な最小 `base_size`（小型個体の連続分裂防止） | 8.5 |
| size_reduction | float | 分裂後の親サイズ倍率（`base_size` に乗算） | 0.75 |
| offspring_size_ratio | float | 子のサイズ = 親分裂前サイズ × この比率 | 0.48 |
| offspring_satiety_ratio | float | 子の初期満腹度 = 親分裂前満腹度 × この比率 | 0.60 |
| cooldown | int | 分裂後の再分裂禁止ティック数 | 160 |
| separation_distance | float | 子の生成位置（親からの距離・ピクセル） | 13.0 |

**utility の目安:** `can_execute` を満たし、満腹度が threshold を超えるほど高スコア（最大 1.0 付近）

---

#### （将来追加用）その他の Action

| Action 名 | 用途メモ | params |
|-----------|----------|--------|
| （未定） | 例: 植物の光合行動 | |
| （未定） | 例: 草食の採食 Action | |
| （未定） | 例: 卵生・交配（ReproductionAction サブクラス） | |

新しい Action を追加するときは:

1. `actions.py` にクラスと `DEFAULT_PARAMS` を定義
2. `mind.py` の `ACTION_BY_NAME` に登録
3. **この仕様書** の該当セクションに params 表を追記

---

## 記述例

### Amoeba（成長・寿命・マナ徘徊・分裂）

`config/species/amoeba.json` を参照。

### Predator（コロニー・狩り・持ち帰り・巣で食事）

`config/species/predator.json` を参照。`colony.enabled` で巣を共有。行動は **狩り → 持ち帰り → 巣で食事 → 巡回** のループを想定。

---

## 仕様変更時の運用

この仕様書は **1 箇所だけで管理** します。

JSON の構造やパラメータを変更したときは、次をセットで更新してください。

1. **このファイル**（`docs/Species_JSON_Spec.md`）
2. 実装（`species.py` / `actions.py` / `mind.py` など）
3. 既存の `config/species/*.json`（必要な種のみ）

コードと JSON だけ直して仕様書を忘れると、後から種を追加するときに齟齬が出ます。**仕様書 → 実装 → 各種 JSON** の順で揃えるのがおすすめです。

---

## 変更履歴

| 日付 | 内容 |
|------|------|
| 2026-05-21 | 初版（Amoeba / Predator 実装に基づく共通仕様） |
| 2026-05-25 | Predator コロニー（巣・Hunt/Return/Feed/NestPatrol） |
| 2026-05-25 | 巣備蓄を食料＋マナ漏洩（C 案）に変更 |
