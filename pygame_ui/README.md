# pygame_ui

ゲーム非依存の Pygame ウィジェット（日本語 UTF-8 対応）。

## 依存

- Python 3.10+
- `pygame>=2.5`

## フォント（日本語）

同梱推奨: `assets/fonts/NotoSansJP-Regular.otf`

```powershell
python scripts/download_ui_font.py
```

未配置時は OS の日本語フォント（Meiryo / MS Gothic / Noto 等）にフォールバックします。

## デモ

```bash
python -m pygame_ui.demo
```

## 使い方

```python
import pygame
from pygame_ui import UIRoot, UITheme, Button, Checkbox

pygame.init()
screen = pygame.display.set_mode((640, 480))
theme = UITheme.from_defaults()
root = UIRoot(theme)
root.add(Button((20, 20, 120, 32), "開始", on_click=lambda: print("ok")))

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        root.handle_event(event)
    screen.fill((0, 0, 0))
    root.draw(screen)
    pygame.display.flip()
```

## ゲーム画面への重ね合わせ（ScreenOverlay）

上下・左右の **ペインだけ** ウィンドウサイズに追従し、ボタン等は固定サイズのままです。

詳細: [`docs/Overlay_On_Game.md`](docs/Overlay_On_Game.md)

```python
from pygame_ui import ScreenOverlay, DockEdge

overlay = ScreenOverlay()
overlay.dock_top(40)
overlay.dock_bottom(180, title="設定")
overlay.set_viewport(*screen.get_size())
# overlay.game_rect にワールド描画 → overlay.draw(screen)
```

サブウインドウ枠の上: `overlay.dock_on(lambda: minimap_rect(), DockEdge.TOP, 28)`

## Panel の子ウィジェット座標

`Panel` は子の `rect` を **画面座標** のまま描画します。パネル内に置くときは `panel.local_rect(...)` を使ってください（`below_title=True` でタイトル下基準）。

## ImageView（単純な画像表示）

ボタンではない画像用。`scale_mode` で伸縮ルールを切り替えます。

| `ImageScaleMode` | 挙動 |
|------------------|------|
| `native` | 原寸（はみ出しはクリップ） |
| `stretch` | 矩形いっぱいに伸縮 |
| `fit` | アスペクト維持・収める（拡大・縮小） |
| `fit_shrink_only` | アスペクト維持・大きいときだけ縮小 |
| `fit_grow_only` | アスペクト維持・小さいときだけ拡大 |
| `cover` | アスペクト維持・矩形を覆う（クロップ） |

`allow_upscale` / `allow_downscale` を指定すると、上記より優先されます。

```python
from pygame_ui import ImageView, ImageScaleMode

icon = ImageView(
    (x, y, w, h),
    image_path="icons/ant.png",
    scale_mode=ImageScaleMode.FIT_SHRINK_ONLY,
    align_x="center",
    align_y="center",
    background=(0, 0, 0, 128),
)
```

## テーマ（見た目の切替）

```python
from pygame_ui import UITheme

theme_soft = UITheme.from_defaults()   # 角丸・落ち着いた緑
theme_pixel = UITheme.pixel_art()      # ドット絵風・ベベル枠・角丸なし

root.set_theme(theme_pixel)  # 実行中の切替
```

デモでは **T キー** または **「テーマ切替」ボタン** で `default` ↔ `pixel_art` を切り替えられます。

`UITheme(...)` で色・`radius`・`pixel_style` を個別に上書きも可能です。

## 画像スキン（PNG）

**自作するときは → [`docs/Skin_Authoring.md`](docs/Skin_Authoring.md)**（9-slice の切り方、キー一覧、サイズ目安、チェックリスト）

`pygame_ui/assets/skins/<名前>/` に `skin.json` と PNG を置く。

```python
from pygame_ui import UITheme

theme = UITheme.with_skin("pixel")          # 組み込み pixel スキン
theme = UITheme.from_skin_dir("path/to/my_skin")
```

### skin.json 例

```json
{
  "name": "pixel",
  "images": {
    "button_idle": "button_idle.png",
    "button_hover": "button_hover.png",
    "button_pressed": "button_pressed.png",
    "checkbox_off": "checkbox_off.png",
    "checkbox_on": "checkbox_on.png",
    "slider_track": "slider_track.png",
    "slider_fill": "slider_fill.png",
    "slider_thumb": "slider_thumb.png",
    "menu_row_hover": "menu_row_hover.png"
  },
  "nine_slice": {
    "panel": {"image": "panel.png", "left": 8, "top": 8, "right": 8, "bottom": 8},
    "menu": {"image": "panel.png", "left": 8, "top": 8, "right": 8, "bottom": 8}
  }
}
```

- **images**: 矩形に伸縮して貼り付け
- **nine_slice**: パネル・メニューなど可変サイズ向け

サンプル生成:

```bash
python scripts/generate_ui_skin.py
```

未設定のパーツは従来どおりベクター描画にフォールバックします。

詳細ルールは上記 **Skin_Authoring.md** を参照してください。

## ウィジェット

| クラス | 説明 |
|--------|------|
| `Button` | クリック |
| `Checkbox` | トグル + ラベル |
| `Slider` | 0..1 |
| `Panel` | 半透明パネル + 子 |
| `ContextMenu` | 右クリックメニュー |
| `VBox` | 縦積みレイアウト |

## ecosystem_evo との関係

このパッケージは `src.game` / `src.sim` を import しません。  
ゲーム側は `src/client/ui_adapter.py`（今後）で薄く接続してください。
