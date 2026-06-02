# UI スキン（PNG）

**作成ルールの詳細 → [`../../docs/Skin_Authoring.md`](../../docs/Skin_Authoring.md)**  
（9-slice の切り方、キー一覧、サイズ目安、チェックリスト）

## 同梱

- **`pixel/`** — サンプル。`python scripts/generate_ui_skin.py` で PNG と `skin.json` を再生成できます。

## クイックスタート

1. `pixel/` をコピーして `my_skin/` を作る  
2. PNG を差し替え、`skin.json` のファイル名を合わせる  
3. 読み込み:

```python
from pygame_ui import UITheme

theme = UITheme.from_skin_dir("path/to/my_skin")
```

## 読み込み API

| 方法 | 例 |
|------|-----|
| 組み込み | `UITheme.with_skin("pixel")` |
| 任意フォルダ | `UITheme.from_skin_dir(".../my_skin")` |
| スキンのみ | `UISkin.from_directory(".../my_skin")` |

未設定の画像キーはベクター描画にフォールバックします。
