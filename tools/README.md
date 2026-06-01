# 開発ツール

## 開発エディタ（推奨）

`run_dev_editor.py` が次をまとめて起動します。

| 部品 | 技術 | 役割 |
|------|------|------|
| 設定 UI | FastAPI + ブラウザ | `config/game/species`, `object_types` の編集・検証 |
| マップ | Pygame (`tools/map_editor`) | ワールド配置・ドラッグ（ゲームと同じ描画） |

```bash
pip install -r requirements.txt
python run_dev_editor.py
python run_dev_editor.py --no-map      # Web のみ
python run_dev_editor.py --no-browser  # ブラウザは手動
```

**Windows:** `noise` パッケージは C++ ビルドが要るため `requirements.txt` には含めていません。  
ゲーム・エディタは未インストールでも動作します（バイオームは簡易ノイズ）。Perlin を使う場合のみ `pip install noise`（要 [Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)）。

**Method Not Allowed / 新規・削除が効かない:** ポート `8765` に古い API が残っていることがあります。  
いったん他の `python run_dev_editor.py` を終了してから再起動するか、`python run_dev_editor.py --port 8766` を使ってください。

- ソース: `tools/editor_server/`, `tools/editor_web/`
- マップ選択は `.editor_shared_state.json` 経由で Web に表示（読み取り専用）
- Web UI: **＋ 新規**（テンプレート JSON でファイル作成）、**削除**（ファイル削除）
- ID 規則: 英小文字で始まり、`a-z` `0-9` `_` のみ（例: `my_rock`）

## その他

- `run_map_editor.py` — マップエディタ単体
- `tools/dev_launcher.py` — シミュレーション数値・ゲーム起動（tkinter）
