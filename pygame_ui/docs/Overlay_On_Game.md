# ゲーム画面への UI 重ね合わせ

`ScreenOverlay` で、シミュレーション描画の **上** に `pygame_ui` コントロールを載せます。

## 考え方

| 要素 | リサイズ時の挙動 |
|------|------------------|
| **ペイン（帯）** | 画面上部・下部など、**幅または高さはウィンドウに追従** |
| **ペインの厚み** | `dock_top(48)` の `48` のように **固定 px** |
| **ボタン・チェック等** | 従来どおり **固定サイズ**（VBox でペイン内に並べる） |

コントロールをウィンドウ全体に伸ばす必要はありません。ペインだけが伸び、中身はそのまま — 一般的なゲーム UI と同じです。

## 基本（上下ペイン）

```python
from pygame_ui import ScreenOverlay, UITheme, Button, VBox

overlay = ScreenOverlay(UITheme.from_defaults())
top = overlay.dock_top(40, title="ツール")
bottom = overlay.dock_bottom(200, title="コントロール")

vbox = VBox(0, 0, 280, spacing=8)
vbox.add(Button((0, 0, 200, 32), "一時停止"), 32)
# ...

overlay.set_viewport(*screen.get_size())
overlay.relayout_vbox(bottom, vbox)

while running:
    for event in pygame.event.get():
        if event.type == pygame.VIDEORESIZE:
            overlay.set_viewport(event.w, event.h)
            overlay.relayout_vbox(bottom, vbox)
        if overlay.handle_event(event):
            continue
        # ゲーム入力（overlay.game_rect 内だけなど）

    screen.fill((0, 0, 0))
    draw_world(screen, overlay.game_rect)  # 中央がゲーム領域
    overlay.draw(screen)
```

`overlay.game_rect` … ドック後に残った矩形（カメラ・ワールド描画用）。

## 配置オプション

| API | 用途 |
|-----|------|
| `dock_top(height)` | 画面上部の横長バー |
| `dock_bottom(height)` | 画面下部（設定パネルなど） |
| `dock_left(width)` | 左サイド |
| `dock_right(width)` | 右サイド |
| `dock(edge, size)` | 汎用 |
| `dock_on(anchor, edge, size)` | **サブウインドウ・ミニマップ枠の上** |
| `add_overlay(widget)` | コンテキストメニュー（最前面） |

同じ辺に複数ペインを登録すると、上→下・左→右の順で **積み上げ** ます。

## サブウインドウの上

ミニマップやインベントリ枠など、ゲーム側が持つ矩形の **内側** にツールバーを付けられます。

```python
def minimap_bounds() -> Rect:
    # 毎フレーム更新してもよい
    return Rect(screen_w - 220, 16, 200, 160)

overlay.dock_on(minimap_bounds, DockEdge.TOP, 28, title="")

while running:
    overlay.set_viewport(*screen.get_size())  # anchor も再計算される
```

`anchor` に `lambda: Rect(...)` を渡すと、位置が動く枠にも追従します。

## ecosystem_evo Client への接続（方針）

`pygame_ui` は `src.game` / `src.sim` を import しません。Client 側で薄く:

1. `GameApp.__init__` で `ScreenOverlay` を生成  
2. `resize_display` で `set_viewport` + `relayout_vbox`  
3. メインループでゲーム描画 → `overlay.draw`  
4. `InputHandler` で `overlay.consumes_point` または `handle_event` を先に試す  

既存の `Renderer` HUD と併用する場合は、段階的にウィジェットを移す想定です。

## デモ

```bash
python -m pygame_ui.demo
```

ウィンドウをリサイズすると、上・下ペインが追従し、中央が「ゲーム領域」として表示されます。
