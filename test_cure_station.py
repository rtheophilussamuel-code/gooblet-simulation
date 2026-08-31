import types

import the_program as tp


class DummyLabel:
    def config(self, *args, **kwargs):
        pass


class DummyGooblet:
    def __init__(self, smartness, x=0, y=0, alive=True):
        self.smartness = smartness
        self.x = x
        self.y = y
        self.alive = alive


class DummyCanvas:
    def __init__(self):
        self.polygons = []
        self.text = []
        self.lowered = []

    def create_polygon(self, *points, **options):
        self.polygons.append((points, options))

    def create_text(self, *position, **options):
        self.text.append((position, options))

    def tag_lower(self, tag):
        self.lowered.append(tag)


def test_three_nearby_gooblets_form_country():
    nearby = [DummyGooblet(0.2, x=index * 5, y=100) for index in range(3)]
    isolated = DummyGooblet(0.2, x=500, y=500)

    countries = tp.find_country_groups(nearby + [isolated])

    assert len(countries) == 1
    assert countries[0] == nearby


def test_fewer_than_three_gooblets_do_not_form_country():
    nearby = [DummyGooblet(0.2, x=index * 5, y=100) for index in range(2)]

    assert tp.find_country_groups(nearby) == []


def test_country_is_drawn_as_map_territory():
    gooblets = [DummyGooblet(0.2, x=100 + index * 5, y=100) for index in range(3)]
    world = types.SimpleNamespace(gooblets=gooblets, canvas=DummyCanvas())

    tp.draw_country_map(world)

    assert len(world.canvas.polygons) == 1
    assert world.canvas.polygons[0][1]["tags"] == ("country_territory",)
    assert world.canvas.text[0][1]["text"] == "COUNTRY 1"
    assert world.canvas.lowered == ["country_territory"]


def test_two_gooblets_do_not_draw_country_territory():
    gooblets = [DummyGooblet(0.2, x=100 + index * 5, y=100) for index in range(2)]
    world = types.SimpleNamespace(gooblets=gooblets, canvas=DummyCanvas())

    tp.draw_country_map(world)

    assert world.canvas.polygons == []


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
                "wood": 0,
                "stone": 0,
                "bronze": 0,
                "iron": 0,
                "tool": 0,
                "tent": 0,
                "fire": 0,
                "house": 0,
                "cannon": 0,
                "musket": 0,
                "phone": 0,
                "pistol": 0,
                "machine_gun": 0,
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
