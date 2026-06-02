# creature_renderer.py
import math

import pygame

from src.client.sprite_manager import get_default_sprite_manager
from src.sim.components.inventory import BiomassItem
from src.sim.utils.creature_helpers import hp_ratio, satiety_ratio
from src.sim.utils.inventory_helpers import get_haul_max_carry, inventory_is_loaded, carried_mass_for_kind
from src.sim.utils.position_helpers import entity_xy

# コロニー種の頭上ラベル（勢力色）
COLONY_SPECIES_LABELS: dict[str, str] = {
    "red_ant": "R",
    "red_ant_soldier": "R",
    "red_ant_vanguard": "R>",
}

# コロニー非所属（ウェーブ侵入蟻など）
UNAFFILIATED_SPECIES_LABELS: dict[str, str] = {
    "invader_ant": "×",
}


class CreatureRenderer:
    """生物描画クラス（見えやすく強化）"""

    @staticmethod
    def draw(
        creature,
        screen,
        camera,
        *,
        is_selected: bool = False,
        show_sheltered_debug: bool = False,
    ):
        from src.sim.shelter.state import is_creature_sheltered

        sheltered = is_creature_sheltered(creature)
        if sheltered and not show_sheltered_debug:
            return

        if not creature.alive:
            return

        cx, cy = entity_xy(creature)
        sx, sy = camera.world_to_screen(cx, cy)

        # ズーム考慮カリング（画面座標ベース）
        pad = max(20, int(50 * camera.zoom))
        if not (-pad <= sx <= camera.screen_w + pad and -pad <= sy <= camera.screen_h + pad):
            return

        color = creature.species.color
        base_size = float(creature.traits.get("base_size", 8))
        size = max(1, int(base_size * camera.zoom))
        if sheltered and show_sheltered_debug:
            color = tuple(min(255, max(0, c // 2 + 50)) for c in color)

        if hasattr(creature, "last_pos"):
            lx, ly = camera.world_to_screen(creature.last_pos[0], creature.last_pos[1])
            if abs(lx - sx) + abs(ly - sy) > 2:
                trail_color = (max(0, color[0] - 80), max(0, color[1] - 80), max(0, color[2] - 80))
                pygame.draw.line(screen, trail_color, (lx, ly), (sx, sy), max(2, int(2 * camera.zoom)))

        # === 画像描画優先（SpriteManager経由、ズーム対応） ===
        manager = get_default_sprite_manager()
        has_real_sprites = manager.has_sprites

        # アニメーション時間（移動中のみアニメ。Client側で velocity から判断）
        vel = getattr(creature, "velocity", None)
        speed = 0.0
        if vel and hasattr(vel, 'x') and hasattr(vel, 'y'):
            speed = (vel.x ** 2 + vel.y ** 2) ** 0.5
        anim_time = pygame.time.get_ticks() if speed > 0.05 else None

        # get_for_creature には base (ズーム前) サイズを渡す
        frame = manager.get_for_creature(
            creature.species.name,
            base_size,
            carrying=inventory_is_loaded(creature),
            color_override=color if not has_real_sprites else None,
            animation_time_ms=anim_time,
            walk_fps=12.0,
        )

        # ここでズーム分のスケール（sprite manager は base サイズで返す）
        vis_diam = max(4, int(base_size * camera.zoom * 2))
        if frame.get_width() != vis_diam or frame.get_height() != vis_diam:
            frame = pygame.transform.smoothscale(frame, (vis_diam, vis_diam))

        # 方向
        angle = 0.0
        if base_size >= 6 and speed > 0.01:
            angle = math.degrees(math.atan2(vel.y, vel.x))

        carry_flag = "carry" if inventory_is_loaded(creature) else "default"
        # ズームサイズでキーイング（vis_diamが変わると別キャッシュ）。これによりスクロールズームで画像サイズが追従する。
        # stable_key に現在表示サイズを含めないと、回転キャッシュが古いズーム時の小さいサーフェスを返し続けサイズ固定になる。
        stable_key = f"{creature.species.name}|{carry_flag}|{int(base_size)}|vis{vis_diam}"
        sprite = manager.get_rotated(frame, angle, stable_key=stable_key)

        # ズーム適用後の位置でセンタリング描画
        rect = sprite.get_rect(center=(sx, sy))
        screen.blit(sprite, rect)

        # 選択リング（右クリック選択時のみ表示。is_selected は renderer から正しく渡される）
        if is_selected:
            sel_r = max(2, int(12 * camera.zoom))
            pygame.draw.circle(screen, (255, 240, 120), (sx, sy), size + sel_r, max(1, int(2 * camera.zoom)))
            pygame.draw.circle(screen, (255, 200, 80), (sx, sy), size + max(2, int(16 * camera.zoom)), max(1, int(camera.zoom)))
        if sheltered and show_sheltered_debug:
            pygame.draw.circle(screen, (100, 200, 255), (sx, sy), size + max(2, int(10 * camera.zoom)), max(1, int(camera.zoom)))

        # シェイプフォールバック（画像なし時、ズーム適用）
        if not has_real_sprites:
            r = size + max(1, int(2 * camera.zoom))
            pygame.draw.circle(screen, color, (sx, sy), r)
            outline = (100, 200, 255) if sheltered and show_sheltered_debug else (255, 255, 255)
            pygame.draw.circle(screen, outline, (sx, sy), r, max(1, int(2 * camera.zoom)))

        # ステータスバー（ズームスケール）
        bar_w = max(6, int(base_size * 3.0 * camera.zoom))
        bar_x = sx - bar_w // 2
        bar_h = max(2, int(6 * camera.zoom))

        bar_y_sat = sy - size - max(8, int(24 * camera.zoom))
        bar_y_hp = sy - size - max(4, int(14 * camera.zoom))
        sat_fill = satiety_ratio(creature)
        hp_fill = hp_ratio(creature)

        pygame.draw.rect(screen, (40, 40, 40), (bar_x, bar_y_sat, bar_w, bar_h))
        pygame.draw.rect(
            screen,
            (80 + int(sat_fill * 175), 255, 80),
            (bar_x, bar_y_sat, int(bar_w * sat_fill), bar_h),
        )
        pygame.draw.rect(screen, (40, 40, 40), (bar_x, bar_y_hp, bar_w, bar_h))
        pygame.draw.rect(
            screen,
            (255, 80 + int(hp_fill * 100), 80),
            (bar_x, bar_y_hp, int(bar_w * hp_fill), bar_h),
        )

        # コロニーラベル・運搬表示（ズームスケール）
        colony = getattr(creature, "colony", None)
        colony_label = COLONY_SPECIES_LABELS.get(creature.species.name)
        if colony_label is None:
            colony_label = UNAFFILIATED_SPECIES_LABELS.get(creature.species.name)
        if colony_label is not None and creature.alive:
            font_size = max(8, int(12 * camera.zoom))
            font = pygame.font.SysFont("msgothic", font_size)
            label = colony_label
            label_color = tuple(creature.species.color)
            if inventory_is_loaded(creature):
                label = "↩"
                inv = creature.inventory
                cap = sum(s.max_mass for s in inv.slots) if inv.slots else get_haul_max_carry(creature)
                max_carry = max(cap, 0.001)
                chunk_ratio = min(1.0, carried_mass_for_kind(creature) / max_carry)
                prey_color = (120, 90, 70)
                slot = inv.first_biomass_slot()
                if (
                    slot is not None
                    and isinstance(slot.item, BiomassItem)
                    and slot.item.source_loot is not None
                    and slot.item.source_loot.color
                ):
                    prey_color = tuple(max(0, c // 2) for c in slot.item.source_loot.color)
                csize = max(2, int(base_size * 0.35 * camera.zoom + chunk_ratio * base_size * 0.45 * camera.zoom))
                carry_off = max(2, int(6 * camera.zoom))
                pygame.draw.circle(screen, prey_color, (sx + size + carry_off, sy), csize)
                pygame.draw.line(
                    screen,
                    (255, 200, 80),
                    (sx, sy),
                    (sx + size + carry_off, sy),
                    max(1, int(2 * camera.zoom)),
                )
            text = font.render(label, True, label_color)
            label_y_off = max(10, int(35 * camera.zoom))
            screen.blit(text, (sx - max(4, int(8 * camera.zoom)), sy - size - label_y_off))

    @staticmethod
    def _biomass_bar_color(ratio: float) -> tuple:
        """残存バイオマス 1.0→緑, 0.5→黄, 0.0→赤"""
        ratio = max(0.0, min(1.0, ratio))
        if ratio > 0.5:
            t = (ratio - 0.5) * 2.0
            return (int(255 * (1.0 - t)), 255, 0)
        t = ratio * 2.0
        return (255, int(255 * t), 0)
