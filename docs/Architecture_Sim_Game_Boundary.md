# Architecture: Sim Layer vs Game Layer Boundary

**Date**: 2026-06  
**Status**: **並行開発に必要な境界分離は達成済み（2026-06-03 凍結）**  
追加の意味論的分離（Sim 内 affiliation 解釈の全移管等）は意図的に行わない。

## Core Philosophy (User Directive)

- **シミュ層 (Sim Layer)** は「ゲームに依存しない基盤」であること。
  - 基本的な能力：「AIを持ったキャラクターがマップ上を動き、物理的に相互作用する」世界を回すエンジン。
  - できるだけ純粋に保つ。生態系ゲーム特有の概念（コロニー、勢力、繁殖進行、女王の役割など）は極力入れない。

- **ゲーム層 (Game Layer)** がゲームを進行させる。
  - Sim層からイベントを受け取る。
  - 状況に応じてオブジェクトを追加したり、AIプロファイルを書き換えたり、コマンドを発行したりしてゲームを駆動する。
  - ゲーム特有のルール・進行・意味付けはすべてここに置く。

- **汎化（WorldObjectなどの抽象化）は手段であって目的ではない**。
  - AI（このコードを書いている存在）が長期的にメンテナンスしやすい構造であることが最優先。
  - 人間が読みやすいかどうかは二の次。AIが理解・修正・拡張しやすい「構造のシンプルさ」が価値。
  - 過度な抽象化で認知負荷を上げるのは避ける。

## Sim Layer が持つべき責務（最小限）

- Creature（位置、状態、Mind/AI、基本的な行動実行）
- 空間インデックス・近傍探索
- 基本的な物理（移動、障害物との衝突解決）
- シンプルな WorldObject（「マップに置かれた何か」という極めて薄い概念）
  - ID、位置、形状（circle/rect）、親子関係、汎用データ格納
  - **意味を解釈しない**（これがcolony_siteなのか岩なのかは知らない）
- Eventの発生（Death, Spawn, Item interaction, Combat started など、事実のみ）
- SimBridgeを通じた最小限の命令実行（SpawnCreature, SetMind など）

## Sim Layer が持つべきでないもの（理想。現状は部分残留・凍結）

以下は **長期理想** として記録する。2026-06-03 時点で **全面移管は凍結**（過剰分離のデメリットが大きいと判断）。

- Colony / Faction / 勢力の概念（Sim 内ヘルパーに一部残留 — 触らなくてよい）
- Nest / ColonySite の意味解釈の Game 完全移管
- `colony.profiles` 由来設定の Sim 外への移動

**凍結後のルール**: 新規のゲーム固有ロジックは Game 層に書く。既存 Sim 内コードは動かさなくてよい。

## WorldObject の位置づけ（汎化に関する判断）

現在の WorldObjectSystem はすでにかなりゲーム寄り（colony compound, storage, combat capability など）。

**推奨方針**（ユーザーの哲学に基づく）:

1. **極薄の汎用 WorldObject を Sim に残す**のは許容。
   - 位置・形状・親子・ラベル・汎用プロパティくらいまで。
   - 空間クエリ（近くのオブジェクトを探す）は Sim が提供してよい。

2. **意味のある解釈はすべて Game Layer に押し出す**。
   - `is_colony_root`、`storage`、`compound` などの colony 特化機能は、Game Layer 側のレイヤー（例: `ColonySiteSystem` や `GameWorldObjectInterpreter`）が持つ。
   - Sim の WorldObject は「ただの置かれたデータコンテナ + 空間的存在」として扱う。

3. 過度に汎用化して「すべての可能性を吸収する巨大基底クラス」を作るのは避ける。
   - AIがメンテする観点では、**「colony_site 専用オブジェクト」と「obstacle 専用オブジェクト」を別クラス/別システムで持つ方がシンプル**な場合もある。
   - 汎化の価値は「instances[] という1つのデータ形式でマップ配置を統一できる」程度に留め、ランタイムのクラス階層まで無理に共通化しない。

## 推奨する移行の方向性

- Phase D では「ColonySite を instances から作る」ことを進めるが、その解釈ロジックはできるだけ Game Layer に寄せる。
- NestSystem / CompoundSystem などの多くは、将来的に Game Layer 側の「ColonyOrchestrator」のようなものに移動することを視野に入れる。
- Sim 側の World は「Creature + 薄い WorldObject + 空間 + イベント発生」の最小構成を目指す。
- Game 側が Sim に対して「この位置にこういうデータを持った WorldObject を置け」「このIDのオブジェクトのデータを更新しろ」といった薄い命令を出せるようにする。

## まとめ（判断基準）

今後、何かを抽象化したり汎化したりする判断をするときは、以下の質問を最優先で使う：

> 「この変更は、**AIがこのコードを長期的にメンテ・拡張しやすくなる**か？  
> それとも、きれいな設計のための抽象化で、結果的に認知負荷を上げていないか？」

この原則に従って、Phase D 以降の設計を進めていく。

---

**Next Actions**: なし（境界分離プロジェクト凍結）。日常開発は [Layer_Interfaces.md](./Layer_Interfaces.md) の契約に従う。

**実施済み (2026-06)**

- 敗北状態・`AffiliationDefeatedEvent` を Game 層へ移動。
- `World.mark_affiliation_defeated` / `is_affiliation_defeated` による中立参照。
- テスト: `tests/sim/conftest.py`（`@pytest.mark.no_colony`）、`tests/game/conftest.py`。
- **2-AI 並行開発**: `docs/Layer_Interfaces.md` + `tests/contracts/test_layer_imports.py` + `src/game/client_api.py`。
- **境界分離凍結 (2026-06-03)**: `docs/REVIEW_Sim_Game_Layer_Independence_Problems.md` §0。
- **ゲーム企画確定**: `docs/Game_Vision.md`。