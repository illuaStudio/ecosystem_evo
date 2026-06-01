# game 層の設定

このゲーム固有のコンテンツを置く。

- `species/` — 種族定義（`name`, `affiliation`, AI など）
- `worlds/` — ワールド JSON（配置・所属プロファイル・初期スポーン）
- `object_types/` — マップに置くオブジェクト型（岩・毒霧・巣部品・女神像の部品など）

シミュレーションエンジンが理解するのは **capabilities**（collision / zone / storage …）のみ。  
`poison_fog` や `rock` という名前付きの型はゲームコンテンツとしてここに置く。

スキーマ説明: `config/sim/object_types/SCHEMA.md`

## Web 設定エディタ

種族・オブジェクト型の編集はブラウザ UI、マップ配置は Pygame です。

```bash
pip install -r requirements.txt
python run_dev_editor.py
```

- 設定 UI: http://127.0.0.1:8765/
- API のみ: `python run_dev_editor.py --no-map`
- マップのみ（API は別途）: `python run_map_editor.py`

詳細: `tools/README.md`
