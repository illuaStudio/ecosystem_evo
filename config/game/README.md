# game 層の設定

このゲーム固有のコンテンツを置く。

- `species/` — 種族定義（`name`, `affiliation`, AI など）
- `worlds/` — ワールド JSON（配置・所属プロファイル・初期スポーン）
- `object_types/` — マップに置くオブジェクト型（岩・毒霧・巣部品・女神像の部品など）

シミュレーションエンジンが理解するのは **capabilities**（collision / zone / storage …）のみ。  
`poison_fog` や `rock` という名前付きの型はゲームコンテンツとしてここに置く。

スキーマ説明: `config/sim/object_types/SCHEMA.md`
