# Client層 レンダリング：シェイプ → 画像 + 大量表示パフォーマンス方針

**対象**: Client層のみ（src/client/rendering/ および関連アセット管理）
**背景**: 現在は pygame.draw.circle / rect で生物・巣などを描画。画像（スプライト）に置き換えたい + 大量個体（数千〜数万）表示時の速度向上。
**制約**: Game層は別AIが修正中。Clientは client_api や公開データ経由でしかGame情報に触れない。Sim直接依存は最小限に（現状の安定ヘルパーは許容）。

## 1. 全体方針（推奨アプローチ）

### 段階的移行（安全・測定重視）
1. **Phase 1: 基本画像化（1〜2日相当）**
   - シェイプ描画を画像blitに置き換え。
   - 種ごとの色はティント（色乗算）で再現（スプライト資産を最小化）。
   - 運搬中・選択中などの状態はオーバーレイ or バリエーションで表現。
   - 既存のshapeモードをフラグで残し、A/B比較可能に。

2. **Phase 2: パフォーマンス基礎最適化（pygameの範囲で）**
   - 回転・スケールのキャッシュ。
   - 静的レイヤーの事前レンダリング（地形、テリトリー）。
   - より厳密な視野カリング + LOD（ズームアウト時は簡易ドット表現）。
   - 実測しながら進める（FPSカウンター必須）。

3. **Phase 3: 大量表示のための本気GPU検討**
   - 純pygame（CPU blit）では限界がある。
   - 「2Dだけど内部3Dテクスチャ」アプローチは**有効**。
   - 選択肢を評価して決定。

この段階的アプローチにより、Game層の変更を最小に抑えつつ、Client単独で進められる。

## 2. 画像置き換えの具体策

### アセット構成
- 新規フォルダ推奨: `pygame_ui/assets/sprites/` （UIスキンと分離）または `assets/game_sprites/`。
  - `creatures/red_ant.png`, `red_ant_soldier.png`, `spider.png` など。
  - `nests/red_ant_nest.png`（基本形状 + 貯蔵量オーバーレイ）。
  - `obstacles/rock.png`, `items/biomass_chunk.png`。
- サイズ: 32x32 や 64x64 のベース。実行時に `base_size` trait でスケール。
- 方向: 可能なら8方向 or 360度用に1枚の正面スプライト + 回転。回転は重いのでキャッシュ。
- アニメ: 最初は静止画。後でwalk cycle用スプライトシート。

**種定義との連携**:
- 現状species.jsonに "color" しかない。
- Client側で `species_name -> sprite_name` のマッピングをハードコード or シンプルなJSONで開始。
- 将来的にGame層のspecies.jsonに `"sprite": "red_ant_worker"` を追加したい場合は、別途Game担当AI向けドキュメントを作成して依頼。

### レンダラー側の変更
- `CreatureRenderer.draw` を大幅リファクタ。
  - 画像取得 → スケール → 必要なら回転 → ティント → blit。
  - 状態（carrying, sheltered, selected）は追加blitや色変更で。
- 同様に `NestRenderer`, `ObstacleRenderer` も画像対応。
- 新クラス: `SpriteManager`（Client層）
  - `load_all()`
  - `get_sprite(species_name, state="default") -> Surface`
  - `tint(surface, color)`
  - `get_rotated_cached(sprite, angle) -> Surface` （辞書キャッシュ、メモリ注意）

### 状態表現のアイデア
- 運搬中: 頭上に小さなバイオマスアイコン + 線（現在と同じビジュアルを画像で）。
- 兵隊/女王: 別スプライト or 少し大きいサイズ + 色ティント。
- コロニーラベル: 画像の上に小さくテキストblit継続（または画像に埋め込み）。

## 3. 大量表示パフォーマンス戦略

### 現在のボトルネック（推測）
- 毎フレーム全クリーチャーをループ + 視野チェック + 複数draw/blit。
- pygameの `draw.circle` / `blit` は1回あたりそこそこ重い。
- カメラパン中はほぼ全画面更新。

### pygame純正での高速化テクニック（Phase 2で実施）
- **スプライトの事前処理**:
  - 起動時に全必要なスケールバージョンを生成して保持。
  - 回転は `pygame.transform.rotate` を呼ぶたびに重い → 角度を量子化（8方向や16方向）してキャッシュ。
- **レイヤー分離**:
  - バイオーム・地形・静的オブジェクト → 1枚の大きなサーフェスに事前描画。毎フレームは `blit( cached_background, ... )`。
  - 動くもの（クリーチャー、飛沫、エフェクト）だけ個別描画。
- **カリング強化**:
  - 既存の画面外チェックを強化（空間グリッドがあれば活用、ただしClientは直接使わず）。
  - ズームレベルでLOD: 遠くは小さい円や1ピクセル、近くはフルスプライト。
- **Dirty / 部分更新**:
  - 難しいが、カメラが止まっている間は前フレーム差分だけ再描画（高度）。
- **その他**:
  - `pygame.sprite.Group` + `group.draw(screen)` を試す（内部最適化されている場合あり）。
  - テキスト描画は重いので、可能なら画像化 or キャッシュ。
  - `config.client` に "max_draw_entities" や "lod_distance" を追加して調整可能に。

**期待効果**: 数千匹なら快適に、1万匹前後まで粘れる可能性。

### GPU / 内部3Dアプローチの検討（Phase 3）

**質問への回答**:
- はい、**2D表示でも内部的にテクスチャ付きクアッドとして3D扱い（オルソグラフィック投影）するのは非常に高速**です。
- これが現代の2Dゲーム（特に大量ユニット・弾幕・RTS）で使われる標準手法。
- GPUは数万のスプライトを1回のドローコール（instanced rendering）で描ける。
- CPU blitのpygameとは桁が違うスケーラビリティ。

**現実的な選択肢（Client層で）**:

1. **軽めGPU移行（おすすめ）**:
   - `moderngl` + pygameを組み合わせ。
   - ワールドビュー部分だけOpenGLコンテキストで描画 → pygameのscreenにテクスチャとして貼り付け。
   - クリーチャーはすべて同じメッシュ（クアッド）で、位置・UV・色をインスタンスデータとして渡す。
   - 利点: 数万匹でも60fps可能。見た目は完全に2D。
   - 欠点: コード量が増える。UIパネルはpygameのままハイブリッド。

2. **ライブラリ移行**:
   - `arcade` ライブラリ（pygletベース、OpenGL、2Dに最適化済み、スプライトバッチング優秀）。
   - メリット: スプライト管理・カメラ・パーティクルが最初から高速。
   - デメリット: プロジェクト全体の依存が変わる。pygame_uiとの統合が必要。

3. **pygame-ce + 実験的機能**:
   - pygame community editionには一部高速化が入っている。まずはこれを試す価値あり。

**推奨判断フロー**:
- まずPhase1+2で実装・実測（1000匹、5000匹、10000匹でFPS記録）。
- 10000匹で30fps以下が安定して出るようなら、Phase3のGPU検討を開始。
- その際は **Client_Rendering_GPU_Backend_Proposal.md** という別ドキュメントを作成して、Game層への影響（新しい描画用データが必要か？）を整理し、Game担当AIに共有。

**GPUを使う場合の注意**:
- 現在の `species.color` や `traits.base_size` はそのまま使える（シェーダー側で tint/scale）。
- 運搬状態などはテクスチャUVや追加インスタンス属性で表現。
- カメラはGPU側でビュー行列として扱うとさらに高速。

## 4. 実装時の注意点（層分離遵守）

- **新しい視覚状態が必要になったら**:
  - まずClient内で既存データから導出（velocityからfacing angleを計算、inventoryからcarryingフラグ）。
  - 足りない場合 → `client_api` に新関数を追加する形。直接Gameコードは触らない。
  - 必要なら `docs/Client_Game_Rendering_Data_Request.md` を作成してGame担当に依頼。

- **アセットの置き場所**:
  - ゲーム固有スプライトは `pygame_ui/assets/sprites/` 以下が自然（pygame_uiは汎用UI、spritesはゲーム用と分離）。
  - またはプロジェクトルートに `assets/sprites/` を作ってClientから参照。

- **後方互換**:
  - 設定で "use_shapes": true を残して、画像化が不安定な間はshape描画にフォールバック可能に。

- **デバッグ**:
  - 画像化後も "F1でshape overlay表示" などのデバッグ機能を残す。

## 5. 次のアクション提案（私がClient層で進められること）

1. `SpriteManager` クラスのスケルトン作成（src/client/ 配下）。
2. 仮のシンプルなPNGを置いてCreatureRendererを画像blitに部分置き換え（1体種だけでも）。
3. FPS表示と大量スポーンテスト用のデバッグキーを追加。
4. 測定結果を報告 → Phase2 or Phase3に進むかを判断。
5. 必要に応じて Game担当向けの「追加で欲しい視覚データ」ドキュメントを作成。

この方針で進めますか？  
具体的に「まずSpriteManagerを作って」「nestも含めて一気に画像化して」など優先順位を教えてください。
GPUの本格導入は実測後がベストだと思います。