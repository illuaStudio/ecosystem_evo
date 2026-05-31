# creature.py
import random

from src.sim.ai.mind import UtilityMind
from src.sim.components.colony import ColonyComponent
from src.sim.components.corpse import CorpseComponent
from src.sim.components.energy import Energy
from src.sim.components.life_cycle import LifeCycleManager
from src.sim.components.metabolism import MetabolismComponent
from src.sim.components.position import Position
from src.sim.components.reproduction import ReproductionComponent
from src.sim.components.velocity import Velocity
from src.sim.entities.entity import BaseEntity
from src.sim.entities.species import Species
from src.sim.utils.creature_helpers import (
    current_size,
    get_life_stage,
    refresh_flee_latch_from_species,
)
from src.sim.utils.inventory_helpers import build_inventory_from_species
from src.sim.utils.position_helpers import sync_legacy_pos


class Creature(BaseEntity):
    """
    原始的な単細胞生物基底クラス。

    座標の正は Position コンポーネント。pos / last_pos は描画・レガシー API 用に
    sync_legacy_pos() で同期する（直接 pos を書き換えない）。
    """

    def __init__(self, x, y, species_name: str = "springtail"):
        super().__init__(x, y)

        self.species = Species.create(species_name)
        self.traits = dict(self.species.traits)

        self.mind = UtilityMind(self.species.mind_data)
        self.current_action = None
        self.wander_angle = random.uniform(0, 360)

        self.max_hp = float(self.traits.get("max_hp", 100))
        self.hp = self.max_hp
        self.max_satiety = float(self.traits.get("max_satiety", 80))
        self.satiety = self.max_satiety
        self.nutrition_recovery = False
        self.flee_latch = False
        self.shelter = None

        self.world = None
        self.last_pos = self.pos.copy()

        self.position = Position(float(x), float(y))
        self.velocity = Velocity()
        self.energy = Energy()
        self.life_cycle = LifeCycleManager(self, self.species.life_cycle)
        self.metabolism = MetabolismComponent(self)
        self.corpse = CorpseComponent(self)
        self.reproduction = ReproductionComponent(self)
        self.inventory = build_inventory_from_species(self.species)
        self.colony: ColonyComponent | None = None
        if self.species.colony_data.get("enabled"):
            self.colony = ColonyComponent()

    def sync_derived_stats(self) -> None:
        """traits の max_hp / max_satiety を個体ステータスへ反映（生成時用）。"""
        self.max_hp = float(self.traits.get("max_hp", 100))
        self.hp = self.max_hp
        self.max_satiety = float(self.traits.get("max_satiety", 80))
        self.satiety = self.max_satiety

    @property
    def remaining_biomass(self) -> float:
        return self.corpse.remaining_biomass

    @remaining_biomass.setter
    def remaining_biomass(self, value: float) -> None:
        self.corpse.remaining_biomass = value

    @property
    def initial_biomass(self) -> float:
        return self.corpse.initial_biomass

    @initial_biomass.setter
    def initial_biomass(self, value: float) -> None:
        self.corpse.initial_biomass = value

    @property
    def repro_cooldown(self) -> int:
        return self.reproduction.cooldown

    @repro_cooldown.setter
    def repro_cooldown(self, value: int) -> None:
        self.reproduction.cooldown = value

    def get_current_speed(self) -> float:
        base = float(self.traits.get("base_speed", 1.0))
        inv = getattr(self, "inventory", None)
        if inv is None:
            return base
        return base * inv.carry_speed_multiplier()

    def get_current_vision(self) -> float:
        return self.traits["base_vision"]

    def get_current_size(self) -> float:
        return current_size(self)

    def get_life_stage(self) -> str:
        return get_life_stage(self.age, self.life_cycle)

    def scale_size(self, factor: float) -> None:
        self.metabolism.scale_size(factor)

    def set_repro_cooldown(self, ticks: int) -> None:
        self.reproduction.set_cooldown(ticks)

    def is_dead(self) -> bool:
        """生存中は HP 判定。死骸は残存バイオマスが尽きたら削除対象。"""
        if self.alive:
            return self.hp <= 0
        return self.corpse.is_depleted()

    def biomass_ratio(self) -> float:
        return self.corpse.biomass_ratio()

    def become_corpse(self, cause: str = "hp") -> None:
        self.corpse.become_corpse(cause=cause)

    def update(self, dt: float = 1.0) -> None:
        dt = float(dt)
        if not self.alive:
            self.corpse.update(dt)
            return

        self.age += int(dt)
        self.reproduction.update(dt)

        sync_legacy_pos(self, update_last=True)

        if self.life_cycle.update():
            return

        if self.metabolism.update(dt):
            self.become_corpse(cause="metabolism")
            return

        if self.is_dead():
            self.become_corpse(cause="hp")
            return

        refresh_flee_latch_from_species(self)
        self.current_action = self.mind.decide_next_action(self)
        self.current_action.execute(self)
