# 生物JSON定義 共通仕様書

このファイルは全生物（Amoeba, Ant, Plant, Herbivore など）の `config/species/*.json` の構造と各パラメータの意味を定義します。

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
| colony | object | 任意 | コロニー（巣）行動。`enabled: true` で巣システムに参加（主に Ant） |

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

**省略した場合:** `life_cycle` が空の種（例: Ant）は常に Adult 扱いとなり、自然死・ステージ UI は無効になります。

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
| satiety_hungry_below | float | 満腹度比率がこれ以下で **飢餓**（自分優先: 食べる・巣食事） | 0.10〜0.20 | 0.15 |
| satiety_full_above | float | 巣食事の停止目標・HUD「満腹」表示。通常帯と満腹帯の **行動は同じ**（持ち帰り狩り） | 0.80〜0.90 | 0.85 |

**ゲーム内での使われ方（参考）**

- 毎ティック: `satiety -= metabolism_rate`。満腹度が 0 を下回ると HP が減少
- **通常・満腹帯**（`> satiety_hungry_below`）: 探索→狩り→倒したら持ち帰り。行動は同一
- **飢餓**（`≤ satiety_hungry_below`）: 自己給餌モードに入る。`satiety_full_above` に達するまで維持（チャタリング防止）
- **回復モード中**（満腹度は通常帯でも）: 行動は飢餓時と同じ。HUD は瞬間状態＋「回復中」表示
- **巣に帰ったとき**: `satiety_full_above` まで食べてから再び通常行動（飢餓期間を短くする）
- 旧 `hunger_threshold`（空腹度基準）は読み込み時に `satiety_hungry_below = 1 - hunger_threshold` へ変換
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

**登録済み Action 名:** `WanderAction`, `ManaWanderAction`, `ChaseAction`, `HuntAction`, `ScavengeCarriedAction`, `ReturnToNestAction`, `FeedAtNestAction`, `NestPatrolAction`, `SpawnWorkerAction`, `SplitAction`

---

#### WanderAction の params

ランダム方向への徘徊。マナ回復はしない。

| キー | 型 | 意味 | デフォルト |
|------|----|------|-----------|
| angle_range | float | 1 ティックあたりの進路角度の乱れ（±度） | 30 |
| speed_multiplier | float | `base_speed` に対する移動倍率 | 0.85 |

---

#### ManaWanderAction の params

自由徘徊しながら `World.mana` から満腹度を回復（主に Amoeba 向け）。局所マナ濃度が高いほど移動は鈍く、薄いほど速くランダムに探索する。

| キー | 型 | 意味 | デフォルト |
|------|----|------|-----------|
| angle_range_sparse | float | マナが薄いときの進路乱れ（±度） | 32 |
| angle_range_dense | float | マナが濃いときの進路乱れ（±度） | 12 |
| speed_multiplier_sparse | float | マナが薄いときの移動倍率 | 1.0 |
| speed_multiplier_dense | float | マナが濃いときの移動倍率 | 0.35 |
| mana_absorption_rate | float | 1 ティックあたりの最大マナ吸収量（満腹度は max_satiety の 95% まで） | 0.75 |

**utility の目安:** 空腹度が高いほど選ばれやすい（0.75 + hunger × 0.25）

---

#### ChaseAction の params

視界内の指定種族を追跡し、接触時に噛みつき・死骸消費（単独捕食者向け。巣なし）。

| キー | 型 | 意味 | デフォルト |
|------|----|------|-----------|
| target_type | string | 獲物の `species.name`（例: `"Amoeba"`） | `"Amoeba"` |
| speed_multiplier | float | 追跡時の移動倍率 | 1.25 |
| contact_padding | float | 接触判定の余白（サイズに加算） | 8.0 |
| bite_gain | float | 死骸消費時の満腹度変換効率 | 1.35 |
| attack_power | float | 生体への bite ダメージ倍率（実ダメージ = attack_power × 12） | 1.0 |

**utility の目安:** 視界内に獲物がいないと 0。空腹度が低い（&lt; 0.2）ときも 0。

---

#### colony（コロニー・巣）— Ant 向け

`colony.enabled: true` の種はワールド上に **巣（Nest）** を持ちます。

| キー | 型 | 意味 | デフォルト |
|------|----|------|-----------|
| enabled | bool | コロニー機能を有効化 | false |
| single_colony | bool | 同種はワールドに巣を1つだけ（初期スポーン・P 追加も既存巣へ） | true |
| join_radius | float | `single_colony: false` 時の合流半径（px） | 200 |
| deposit_radius | float | 持ち帰り判定半径（ReturnToNest と共有） | 30 |
| max_food | float | 巣の最大食料備蓄（旧 `max_storage` も可） | 400 |
| initial_stored_food | float | **新設巣**の開始時備蓄（`max_food` でクランプ。合流時は加算しない） | 0 |
| food_leak_rate | float | 1 ティックあたりの余剰食料の漏洩率（腐敗） | 0.0015 |
| food_to_mana_ratio | float | 漏洩食料のうちマナへ還流する比率 | 0.35 |
| food_leak_reserve_ratio | float | この割合までは漏洩しない（底上げ備蓄） | 0.12 |
| nest_x / nest_y | float | 巣が未作成時のスポーン原点（省略時はワールド中央） | 中央 |
| spawn_spread | float | 巣からのスポーンばらつき半径（px） | 28 |
| spawn_food_cost | float | 働きアリ1匹生成に消費する食料 | — |
| max_workers | int | コロニー最大個体数 | — |
| min_food_reserve | float | 生成後も残す最低備蓄（漏洩底上げと併用） | 0 |

**C 案（現状）:** 持ち帰りは **食料（バイオマス）** として `stored_food` に蓄える。コロニーは `FeedAtNest` で満腹度に変換。余剰は `food_leak_rate` で巣タイルへ **マナ還流** し、アメーバの生態系と接続する。

**観察のポイント:** 巣は茶色の円で表示。数字はコロニー人数。捕食者が死骸を運ぶと頭上ラベルが `↩` に変わる。

---

#### HuntAction の params

**通常・満腹帯**（飢餓でない）: 攻撃→殺害→死骸を拾い `ReturnToNestAction` へ。**飢餓時**（`satiety_hungry_below` 以下）: 巣に餌があれば狩らない。なければ狩り、殺害後はその場で `consume_carcass`。

| キー | 型 | 意味 | デフォルト |
|------|----|------|-----------|
| target_type | string | 獲物の種名（単一種） | `"Amoeba"` |
| target_types | string[] | 複数種を狩る場合（`target_type` より優先）。例: `["Amoeba", "Spider"]` | — |
| speed_multiplier | float | 追跡移動倍率 | 1.3 |
| contact_padding | float | 接触・拾い・**接近停止**の余白（両者の `base_size` 之和 + この値で止まる） | 8.0 |
| attack_power | float | bite ダメージ倍率 | 1.2 |
| pickup_on_kill | bool | 満腹時、殺害直後に死骸を拾う | true |
| bite_gain | float | 飢餓時のその場食事効率 | 1.35 |
| colony_hoard_strength | float | **満腹時**のコロニー備蓄のための狩り動機（0〜1） | 0.8 |
| min_usable_food_ratio | float | 備蓄率がこれ未満なら「巣に餌あり」とみなさない | 0.01 |
| min_usable_satiety_gain | float | 1 回の食事で得られる満腹度見積もりがこれ未満なら同左 | 1.0 |

**utility:** 飢餓時は 1.0（巣に食料があれば 0）。通常・満腹帯は `colony_hoard_strength` で備蓄狩り。

---

#### ScavengeCarriedAction の params

**飢餓時のみ**。運搬中の死骸をその場で食べる（`ReturnToNestAction` より優先）。

| キー | 型 | 意味 | デフォルト |
|------|----|------|-----------|
| bite_gain | float | 死骸消費効率 | 1.35 |

---

#### ReturnToNestAction の params

**満腹時のみ**運搬中に高スコア。飢餓時は utility 0（`ScavengeCarriedAction` が担当）。

| キー | 型 | 意味 | デフォルト |
|------|----|------|-----------|
| speed_multiplier | float | 帰巣移動倍率 | 1.1 |
| deposit_radius | float | 貯蔵判定半径 | 30 |

---

#### FeedAtNestAction の params

**飢餓時**に巣へ向かい `satiety_full_above` まで回復。巣にいる通常帯でも同上限まで食べる。餌がなければ utility 0（`HuntAction` が狩りを担当）。帰巣途中の地上死骸は `scavenge_species` で食べる。

| キー | 型 | 意味 | デフォルト |
|------|----|------|-----------|
| bite_gain | float | 貯蔵→満腹度の変換効率 | 1.2 |
| max_take_ratio | float | 1 ティックで巣から取れる最大比率 | 0.35 |
| feed_radius | float | 食事可能半径 | 36 |

---

#### SpawnWorkerAction の params

巣付近・備蓄が `min_food_reserve + spawn_food_cost` 以上・個体数が `max_workers` 未満のとき、巣の食料を消費して子個体を1匹生成。`colony` の `spawn_food_cost` / `max_workers` / `min_food_reserve` を参照。

| キー | 型 | 意味 | デフォルト |
|------|----|------|-----------|
| spawn_radius | float | 生成可能半径（巣中心から） | 40 |
| approach_speed_multiplier | float | 巣外から近づく速度倍率 | 0.9 |
| spawn_cooldown | int | 生成者の再生成クールダウン（ティック） | 900 |

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
- 同種の生存数 `< population_limits`（ワールド JSON。未設定なら制限なし）
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

### Ant（コロニー・狩り・持ち帰り・巣で食事）

`config/species/ant.json` を参照。満腹時は **Amoeba + Spider** を狩って巣へ貯蔵。飢餓時のみ巣食事・その場食事を優先。

### Spider（アメーバ捕食・大型獲物）

`config/species/spider.json` を参照。高 HP・大サイズ。空腹時は `ChaseAction` で **Amoeba** を追跡し、接触時に `try_predate`（殺害→その場で `consume_carcass`）。巣・コロニーなし。満腹時は `WanderAction`。アリの狩り対象。`life_cycle` なし（常に Adult、自然死なし）。

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
| 2026-05-21 | 初版（Amoeba / Ant 実装に基づく共通仕様） |
| 2026-05-25 | Ant コロニー（巣・Hunt/Return/Feed/NestPatrol） |
| 2026-05-26 | Predator → Ant にリネーム（プレイヤー関与種） |
| 2026-05-25 | 巣備蓄を食料＋マナ漏洩（C 案）に変更 |
| 2026-05-25 | SpawnWorkerAction・colony 成長パラメータ |
| 2026-05-25 | Hunt コロニー備蓄動機・死骸運搬の排他 |
| 2026-05-26 | Spider（フェーズ1大型獲物）・Ant の target_type を Spider に |
| 2026-05-26 | Spider: ChaseAction で Amoeba をその場捕食（巣なし） |
| 2026-05-26 | 飢餓 traits（hunger/starvation_threshold）・ScavengeCarriedAction |
| 2026-05-26 | 栄養3帯（satiety_hungry_below / satiety_full_above）、hunger_drive 廃止 |
| 2026-05-26 | 回復モード（nutrition_recovery）: 飢餓後は full_above まで自己給餌を維持 |
| 2026-05-26 | ワールド `population_limits`（種ごとの個体数上限）。`ReproductionAction` 共通で参照 |
