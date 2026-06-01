# ゲーム層設定（`config/game/`）

シミュレーションエンジン（`src/sim/`）が読み込む**コンテンツ**。数値の意味づけ（食料・バイオマスドロップ等）はここで定義する。

## 死後処理（`death_policy`）

sim は **PostLife のパーツ列**だけ実行する。種 JSON に `death_policy` が無い／空なら **何もしない**。

| 値 | 意味 |
|----|------|
| `"field_drop"` | 地面に `field_bulk` を出して個体を `remove`（本ゲームの通常死骸） |

地面ドロップの型:

| 型 | 用途 |
|----|------|
| `field_bulk` | バイオマス（連続量・死骸ドロップ） |
| `field_item` / `field_gold` | `StackItem`（剣・金貨など個数物） |

ゾーン（毒霧など）は `instances` の `layer: "zone"` のみ。旧 `zones.sources` / `field_emitters` は読み込み時に zone インスタンスへ正規化される。
| `"corpse_on_creature"` | 個体のまま残留量を持ち分解（レガシー挙動） |
| `"immediate_remove"` / `"remove"` | 即ワールドから削除 |
| `{ "steps": [ ... ] }` | パーツを直列指定（`spawn_drop`, `convert_corpse_mass`, `warp_to` 等） |

例（`species/spider.json`）:

```json
"death_policy": "field_drop"
```

カスタム:

```json
"death_policy": {
  "steps": [
    { "step": "spawn_drop", "type": "field_bulk" },
    "remove"
  ]
}
```
