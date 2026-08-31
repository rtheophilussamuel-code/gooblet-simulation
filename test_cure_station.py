import types

import the_program as tp


class DummyLabel:
    def config(self, *args, **kwargs):
        pass


class DummyGooblet:
    def __init__(self, smartness):
        self.smartness = smartness


def test_cure_station_triggered_by_smart_gooblet():
    tp.cure_discovered = False
    tp.cure_location = None

    world = types.SimpleNamespace(gooblets=[DummyGooblet(0.6), DummyGooblet(0.2)])
    tp._update_cure_station_hook(world)

    assert tp.cure_discovered is True, "cure station should be discovered"
    assert tp.cure_location is not None, "cure station location should be set"


def test_berries_regrow_from_bushes():
    class DummyWorld:
        def __init__(self):
            self.running = True
            self.gooblets = []
            self.berries = []
            self.berry_bushes = [{"x": 100, "y": 100, "timer": 300}]
            self.lakes = []
            self.decorations = []
            self.resources = {
                "wood": 10,
                "stone": 10,
                "bronze": 10,
                "iron": 10,
                "tool": 10,
                "tent": 10,
                "fire": 10,
                "house": 10,
                "cannon": 10,
                "musket": 10,
                "phone": 10,
                "pistol": 10,
                "machine_gun": 10,
            }
            self.selected_gooblet = None
            self.resource_respawn_tick = 0
            self.base_update_delay = 30
            self.time_multiplier = 1.0
            self.stage = "Stone Age"
            self.root = types.SimpleNamespace(after=lambda *args, **kwargs: None)
            self.stats_label = DummyLabel()
            self.gen_label = DummyLabel()
            self.stage_label = DummyLabel()
            self.count_label = DummyLabel()
            self.resource_label = DummyLabel()
            self.btn_toggle = DummyLabel()
            self.update = lambda: None

        def draw(self):
            return None

        def spawn_decoration(self, *args, **kwargs):
            return None

    world = DummyWorld()
    tp._static_world_update(world)

    assert world.berries, "berries should regrow from berry bushes"


def test_population_cap_prevents_excess_growth():
    world = types.SimpleNamespace(gooblets=[DummyGooblet(0.6) for _ in range(60)])

    assert tp.can_add_gooblets(world, 1) is False
    assert tp.can_add_gooblets(world, 0) is True


def test_evolution_disabled_keeps_smartness_stable():
    tp.EVOLUTION_ENABLED = False
    gooblet = tp.Gooblet(10, 20, stats={"speed": 1.5, "sight": 30, "smartness": 0.42, "strength": 4}, generation=1)

    assert gooblet.smartness == 0.42
    assert gooblet.speed == 1.5


if __name__ == "__main__":
    test_cure_station_triggered_by_smart_gooblet()
    test_berries_regrow_from_bushes()
    test_population_cap_prevents_excess_growth()
    print("test passed")
