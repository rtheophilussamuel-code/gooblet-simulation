import math
import random
import time
import tkinter as tk

# --- Constants ---
WIDTH = 800
HEIGHT = 600
INITIAL_GOOBLETS = 24
BERRY_COUNT = 30
LAKE_COUNT = 5
MAX_GOOBLETS = 60
MUTATION_RATE = 0.0
REPRODUCTION_HUNGER_THRESHOLD = 1000
EVOLUTION_ENABLED = False
WANDER_CHANGE_CHANCE = 0.06
COMBAT_DISTANCE = 15
SICKNESS_DURATION = 60 # Seconds until death
COUNTRY_MIN_POPULATION = 3
COUNTRY_DISTANCE = 65


def find_country_groups(gooblets, distance=COUNTRY_DISTANCE, min_population=COUNTRY_MIN_POPULATION):
    living = [gooblet for gooblet in gooblets if getattr(gooblet, "alive", True)]
    unvisited = set(range(len(living)))
    countries = []

    while unvisited:
        start = unvisited.pop()
        group = [start]
        pending = [start]

        while pending:
            current = pending.pop()
            nearby = [
                index for index in unvisited
                if math.hypot(
                    living[current].x - living[index].x,
                    living[current].y - living[index].y,
                ) <= distance
            ]
            for index in nearby:
                unvisited.remove(index)
                group.append(index)
                pending.append(index)

        if len(group) >= min_population:
            countries.append([living[index] for index in group])

    return countries


def country_polygon_points(gooblets, padding=26):
    min_x = min(gooblet.x for gooblet in gooblets)
    max_x = max(gooblet.x for gooblet in gooblets)
    min_y = min(gooblet.y for gooblet in gooblets)
    max_y = max(gooblet.y for gooblet in gooblets)
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    half_width = max((max_x - min_x) / 2 + padding, 42)
    half_height = max((max_y - min_y) / 2 + padding, 34)

    return (
        center_x - half_width + 8, center_y - half_height,
        center_x + half_width - 12, center_y - half_height + 3,
        center_x + half_width, center_y - half_height + 14,
        center_x + half_width - 4, center_y + half_height - 8,
        center_x + half_width - 18, center_y + half_height,
        center_x - half_width + 11, center_y + half_height - 2,
        center_x - half_width, center_y + half_height - 14,
        center_x - half_width + 3, center_y - half_height + 10,
    )


def draw_country_map(world):
    countries = find_country_groups(world.gooblets)
    world.countries = countries
    colors = ("#e6cf83", "#a8c7a0", "#d9a58c", "#9ebbd1")

    for index, country in enumerate(countries, 1):
        center_x = sum(gooblet.x for gooblet in country) / len(country)
        center_y = sum(gooblet.y for gooblet in country) / len(country)
        world.canvas.create_polygon(
            *country_polygon_points(country),
            fill=colors[(index - 1) % len(colors)],
            outline="#594a2d",
            width=3,
            smooth=True,
            splinesteps=24,
            stipple="gray50",
            tags=("country_territory",),
        )
        world.canvas.create_text(
            center_x,
            center_y - 22,
            text=f"COUNTRY {index}",
            fill="#3b3020",
            font=("Georgia", 10, "bold"),
            tags=("country_label",),
        )

    if countries:
        world.canvas.tag_lower("country_territory")

def clamp_gooblet_to_world(gooblet):
    # Guard against invalid coordinates from chained movement patches.
    if not math.isfinite(gooblet.x) or not math.isfinite(gooblet.y):
        gooblet.x = WIDTH / 2
        gooblet.y = HEIGHT / 2

    radius = max(0, getattr(gooblet, "radius", 0))
    min_x = radius
    max_x = max(radius, WIDTH - radius)
    min_y = radius
    max_y = max(radius, HEIGHT - radius)

    gooblet.x = max(min_x, min(max_x, gooblet.x))
    gooblet.y = max(min_y, min(max_y, gooblet.y))

def can_add_gooblets(world, count=1):
    return len(getattr(world, "gooblets", [])) + count <= MAX_GOOBLETS


class Gooblet:
    def __init__(self, x, y, stats=None, generation=1):
        self.x = x
        self.y = y
        self.generation = generation
        
        # Sickness attributes MUST be initialized before _get_color() is called
        self.is_sick = False
        self.sick_time = 0
        self.curing_progress = 0
        # Small chance to have a different visual variant color (most are red)
        self.variant_color = None
        # if random.random() < 0.22:
        self.variant_color = random.choice(["#119951", "#119951", "#119951", "#feb236", "#a6e22e", "#66d9ef", "#9b59b6", "#f39c12", "#1abc9c"])
        # Track how long this gooblet has been continuously in non-toxic water
        self.in_water_time = 0
        
        # Core Stats
        if stats:
            self.speed = max(1, stats['speed'])
            self.sight = max(20, stats['sight'])
            self.smartness = max(0.1, min(1.0, stats['smartness']))
            self.strength = max(1, stats['strength'])
        else:
            # Stone Age starting stats: low speed, sight, smartness, and strength
            self.speed = random.uniform(1.0, 1.8)
            self.sight = random.uniform(20, 50)
            self.smartness = random.uniform(0.05, 0.18)
            self.strength = random.uniform(2, 5)

        # Survival Needs
        self.hunger = 20
        self.thirst = 20
        self.health = 100
        self.alive = True
        self.color = self._get_color() # This calls is_sick
        self.radius = 6
        
        self.target = None
        self.wander_angle = random.uniform(0, 2 * math.pi)
        self.state = "exploring" 
        self.ready_to_mate = False
        self.in_combat = False

    def _get_color(self):
        # Safety check in case it's called during init
        if hasattr(self, 'is_sick') and self.is_sick: 
            return "#a6e22e" # Sickly green
            
        # r = min(255, int((self.strength / 30) * 255))
        # g = min(255, int((self.sight / 400) * 255))
        # b = min(255, int((self.speed / 8) * 255))
        # return f'#{r:02x}{g:02x}{b:02x}'
        return self.variant_color if self.variant_color else "#EB0202"  # Default red

    def move(self, world):
        if not self.alive: return

        # Update color periodically to reflect sickness status
        self.color = self._get_color()

        # Energy consumption
        self.hunger += 0.06 + (self.speed * 0.01) + (self.strength * 0.005)
        self.thirst += 0.09
        
        # Sickness logic
        if self.is_sick:
            self.health -= 0.05
            self.sick_time += 0.03
            
            if self.sick_time >= SICKNESS_DURATION:
                self.alive = False
                return

        if self.hunger > 100 or self.thirst > 100 or self.health <= 0:
            self.alive = False
            return

        # Healing
        if self.hunger < 30 and self.thirst < 30 and self.health < 100 and not self.is_sick:
            self.health += 0.2

        self.ready_to_mate = False
        self.in_combat = False

        # AI Decision Making
        found_resource = False
        if self.thirst > self.hunger and self.thirst > 30:
            self.state = "searching_water"
            self.target = self.find_nearest_water(world.lakes, self.sight)
            if self.target: found_resource = True
        elif self.hunger > 30:
            self.state = "searching_food"
            self.target = self.find_nearest(world.berries, self.sight)
            if self.target: found_resource = True
        
        if not found_resource:
            self.state = "wandering"
            if random.random() < WANDER_CHANGE_CHANCE:
                self.wander_angle += random.uniform(-0.6, 0.6)
            
            next_x = self.x + math.cos(self.wander_angle) * (self.speed * 0.6)
            next_y = self.y + math.sin(self.wander_angle) * (self.speed * 0.6)
            
            if self.is_on_water(next_x, next_y, world.lakes):
                if random.random() < self.smartness * 0.9:
                    self.wander_angle += math.pi
                else:
                    self.x, self.y = next_x, next_y
            else:
                self.x, self.y = next_x, next_y
        else:
            tx, ty = self.target
            angle = math.atan2(ty - self.y, tx - self.x)
            jitter = (1 - self.smartness) * 0.3
            angle += random.uniform(-jitter, jitter)
            self.x += math.cos(angle) * self.speed
            self.y += math.sin(angle) * self.speed
            self.interact(world)

        # Check for water effects
        # Check for water effects (toxic water causes sickness; normal water can drown)
        if self.is_on_water(self.x, self.y, world.lakes):
            if self.is_on_toxic_water(self.x, self.y, world.lakes):
                # Toxic water: chance to become sick immediately; reset drowning timer
                self.in_water_time = 0
                if not self.is_sick and random.random() < 0.75 * (1 - self.smartness * 0.2):
                    self.is_sick = True
                    self.sick_time = 0
                    self.curing_progress = 0
            else:
                # Non-toxic water: increment drowning timer; smarter gooblets survive longer.
                self.in_water_time += 1
                # Convert smartness to extra tolerance: range [0..80] ticks
                time_to_drown = int(40 + self.smartness * 80)
                # Small immediate drowning chance each tick (to keep variance)
                drown_prob = 0.05 + 0.45 * (1.0 - self.smartness)
                if self.in_water_time >= time_to_drown or random.random() < drown_prob:
                    self.alive = False
        else:
            # Not on water: reset drowning timer
            self.in_water_time = 0

        clamp_gooblet_to_world(self)

    def is_on_water(self, x, y, lakes):
        for l in lakes:
            if math.hypot(l[0] - x, l[1] - y) < l[2] - 5:
                return True
        return False

    def is_on_toxic_water(self, x, y, lakes):
        for l in lakes:
            if l[3] == "toxic" and math.hypot(l[0] - x, l[1] - y) < l[2] - 5:
                return True
        return False

    def find_nearest_water(self, lakes, radius):
        nearest = None
        min_dist = radius
        for l in lakes:
            dist_to_center = math.hypot(l[0] - self.x, l[1] - self.y)
            if dist_to_center < radius + l[2]:
                angle = math.atan2(self.y - l[1], self.x - l[0])
                edge_x = l[0] + math.cos(angle) * (l[2] - 2)
                edge_y = l[1] + math.sin(angle) * (l[2] - 2)
                d = math.hypot(edge_x - self.x, edge_y - self.y)
                if d < min_dist:
                    min_dist = d
                    nearest = (edge_x, edge_y)
        return nearest

    def find_nearest(self, resources, radius):
        nearest = None
        min_dist = radius
        for r in resources:
            d = math.hypot(r[0] - self.x, r[1] - self.y)
            if d < min_dist:
                min_dist = d
                nearest = (r[0], r[1])
        return nearest

    def interact(self, world):
        if self.state == "searching_food":
            for b in world.berries:
                if math.hypot(b[0] - self.x, b[1] - self.y) < 10:
                    world.berries.remove(b)
                    self.hunger = max(0, self.hunger - 50)
                    break
        elif self.state == "searching_water":
            for l in world.lakes:
                dist = math.hypot(l[0] - self.x, l[1] - self.y)
                if abs(dist - l[2]) < 12:
                    self.thirst = max(0, self.thirst - 60)
                    if l[3] == "toxic":
                        if not self.is_sick:
                            self.is_sick = True
                            self.sick_time = 0
                            self.curing_progress = 0
                    break

    def find_nearest_decoration(self, decorations, kind, radius):
        nearest = None
        min_dist = radius
        for obj in decorations:
            if obj.kind != kind:
                continue
            d = math.hypot(obj.x - self.x, obj.y - self.y)
            if d < min_dist:
                min_dist = d
                nearest = obj
        return nearest

    def gather_resources(self, world, stage):
        if not hasattr(world, "decorations"):
            return

        # Prefer to gather trees in early ages, then rocks for metal.
        tree = self.find_nearest_decoration(world.decorations, "tree", 16)
        rock = self.find_nearest_decoration(world.decorations, "rock", 16)

        if tree and stage in ("Stone Age", "Bronze Age", "Medieval Age"):
            world.resources["wood"] += random.randint(2, 5)
            world.decorations.remove(tree)
            self.state = "chopping_tree"
            return

        if rock:
            if stage == "Stone Age":
                world.resources["stone"] += random.randint(1, 3)
                self.state = "collecting_rock"
            elif stage == "Bronze Age":
                world.resources["stone"] += random.randint(2, 4)
                self.state = "mining_bronze"
            elif stage == "Industrial Age":
                world.resources["iron"] += random.randint(1, 2)
                self.state = "mining_iron"
            else:
                world.resources["iron"] += random.randint(1, 3)
                self.state = "mining_modern"
            world.decorations.remove(rock)

class SimulationWorld:
    def __init__(self, root):
        self.root = root
        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg="#fdf6e3")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.visual_scale_x = 1.0
        self.visual_scale_y = 1.0
        
        self.info_panel = tk.Frame(root, width=220, bg="#eee8d5", padx=15, pady=15)
        self.info_panel.pack(side=tk.RIGHT, fill=tk.Y)
        
        tk.Label(self.info_panel, text="Gooblet Evolution", font=("Arial", 14, "bold"), bg="#eee8d5").pack(pady=5)
        self.stats_label = tk.Label(self.info_panel, text="Click a Gooblet", font=("Arial", 10), justify=tk.LEFT, bg="#eee8d5")
        self.stats_label.pack(anchor="nw", pady=10)
        self.gen_label = tk.Text(self.info_panel, height=14, width=28, bg="#f4efe2", wrap="word", relief="flat")
        self.gen_label.pack(anchor="nw", pady=(0, 6))
        self.gen_label.configure(state="disabled")
        self.stage_label = tk.Label(self.info_panel, text="Stage: Stone Age", font=("Arial", 10), bg="#eee8d5")
        self.stage_label.pack(anchor="nw")
        self.count_label = tk.Label(self.info_panel, text="Trees: 0 | Rocks: 0", font=("Arial", 10), bg="#eee8d5")
        self.count_label.pack(anchor="nw", pady=(4, 8))
        self.resource_label = tk.Label(self.info_panel, text="Wood: 0 Stone: 0\nBronze: 0 Iron: 0", font=("Arial", 9), justify=tk.LEFT, bg="#eee8d5")
        self.resource_label.pack(anchor="nw", pady=(0, 8))

        tk.Label(self.info_panel, text="Seed:", font=("Arial", 9, "bold"), bg="#eee8d5").pack(anchor="nw")
        self.seed_var = tk.StringVar(value="")
        self.seed_entry = tk.Entry(self.info_panel, textvariable=self.seed_var)
        self.seed_entry.pack(fill=tk.X, pady=(2, 6))
        self.seed_entry.bind("<Return>", lambda _event: self.start_new_simulation())
        self.seed_status_label = tk.Label(self.info_panel, text="Seed: random", font=("Arial", 9), bg="#eee8d5")
        self.seed_status_label.pack(anchor="nw", pady=(0, 4))
        self.btn_new_sim = tk.Button(self.info_panel, text="Start New Simulation", command=self.start_new_simulation)
        self.btn_new_sim.pack(fill=tk.X, pady=(0, 8))
        self.btn_toggle = tk.Button(self.info_panel, text="Pause Simulation", command=self.toggle_running)
        self.btn_toggle.pack(fill=tk.X, pady=10)

        self.lakes = []
        toxic_lake_index = random.randrange(LAKE_COUNT)
        for i in range(LAKE_COUNT):
            while True:
                lx = random.randint(60, WIDTH-60)
                ly = random.randint(60, HEIGHT-60)
                lr = random.randint(30, 55)
                if all(math.hypot(lx - ol[0], ly - ol[1]) > (lr + ol[2] + 20) for ol in self.lakes):
                    ltype = "toxic" if i == toxic_lake_index else "clean"
                    self.lakes.append([lx, ly, lr, ltype])
                    break

        self.berries = []
        self.spawn_berries(BERRY_COUNT)
        self.gooblets = [Gooblet(random.randint(0, WIDTH), random.randint(0, HEIGHT)) for _ in range(INITIAL_GOOBLETS)]
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
        self.stage = "Stone Age"
        self.resource_respawn_tick = 0
        self.selected_gooblet = None
        self.last_population_count = len(self.gooblets)
        self.shift_down = False
        self.ctrl_down = False
        self.time_multiplier = 1.0
        self.base_update_delay = 40
        self.last_draw_time = 0.0
        self.last_stats_update = 0.0
        self.canvas.bind("<Button-1>", self.on_click)
        self.bind_time_controls()
        self.running = True
        self.update()

    def spawn_berries(self, count):
        for _ in range(count):
            while True:
                bx = random.randint(20, WIDTH-20)
                by = random.randint(20, HEIGHT-20)
                if not any(math.hypot(bx - l[0], by - l[1]) < l[2] + 5 for l in self.lakes):
                    self.berries.append([bx, by])
                    break

    def can_place_decoration(self, x, y, radius):
        if any(math.hypot(x - lx, y - ly) < (lr + radius + 4) for lx, ly, lr, _ in self.lakes):
            return False
        for obj in getattr(self, "decorations", []):
            other_r = 12 if obj.kind == "tree" else 7 if obj.kind == "rock" else 6
            if math.hypot(x - obj.x, y - obj.y) < (radius + other_r + 2):
                return False
        return True

    def spawn_decoration(self, kind, count=1):
        radius = 12 if kind == "tree" else 7 if kind == "rock" else 12 if kind == "house" else 6
        for _ in range(count):
            attempts = 0
            while attempts < 300:
                attempts += 1
                x = random.randint(20, WIDTH - 20)
                y = random.randint(20, HEIGHT - 20)
                if self.can_place_decoration(x, y, radius):
                    self.decorations.append(WorldObject(x, y, kind))
                    break

    def respawn_resources(self):
        tree_count = len([d for d in self.decorations if d.kind == 'tree'])
        rock_count = len([d for d in self.decorations if d.kind == 'rock'])
        if tree_count < 40:
            self.spawn_decoration("tree")
        if rock_count < 35:
            self.spawn_decoration("rock")

    def screen_to_world(self, x, y):
        sx = self.visual_scale_x if self.visual_scale_x > 0 else 1.0
        sy = self.visual_scale_y if self.visual_scale_y > 0 else 1.0
        return (x / sx, y / sy)

    def on_click(self, event):
        self.selected_gooblet = None
        wx, wy = self.screen_to_world(event.x, event.y)
        for g in self.gooblets:
            if math.hypot(g.x - wx, g.y - wy) < 15:
                self.selected_gooblet = g
                break

    def bind_time_controls(self):
        self.root.bind_all("<KeyPress-Shift_L>", self.on_shift_press)
        self.root.bind_all("<KeyRelease-Shift_L>", self.on_shift_release)
        self.root.bind_all("<KeyPress-Shift_R>", self.on_shift_press)
        self.root.bind_all("<KeyRelease-Shift_R>", self.on_shift_release)
        self.root.bind_all("<KeyPress-Control_L>", self.on_ctrl_press)
        self.root.bind_all("<KeyRelease-Control_L>", self.on_ctrl_release)
        self.root.bind_all("<KeyPress-Control_R>", self.on_ctrl_press)
        self.root.bind_all("<KeyRelease-Control_R>", self.on_ctrl_release)

    def on_shift_press(self, event):
        self.shift_down = True
        self.update_time_multiplier()

    def on_shift_release(self, event):
        self.shift_down = False
        self.update_time_multiplier()

    def on_ctrl_press(self, event):
        self.ctrl_down = True
        self.update_time_multiplier()

    def on_ctrl_release(self, event):
        self.ctrl_down = False
        self.update_time_multiplier()

    def update_time_multiplier(self):
        if self.shift_down and not self.ctrl_down:
            self.time_multiplier = 3.0
        elif self.ctrl_down and not self.shift_down:
            self.time_multiplier = 0.4
        else:
            self.time_multiplier = 1.0

    def toggle_running(self):
        self.running = not self.running
        self.btn_toggle.config(text="Pause Simulation" if self.running else "Start Simulation")
        if self.running:
            self.refresh_overview()
            self.update()
        else:
            self.refresh_overview()

    def refresh_overview(self):
        if not hasattr(self, "gen_label"):
            return

        if self.gooblets:
            avg_gen = sum(g.generation for g in self.gooblets) / len(self.gooblets)
            avg_smartness = sum(g.smartness for g in self.gooblets) / len(self.gooblets)
        else:
            avg_gen = 0.0
            avg_smartness = 0.0

        lines = [
            f"Population: {len(self.gooblets)}",
            f"Avg Gen: {avg_gen:.1f}",
            f"Avg Smart: {avg_smartness:.2f}",
            "",
            "All gooblets:",
        ]

        if self.gooblets:
            for index, g in enumerate(self.gooblets, 1):
                lines.append(f"{index}. G{g.generation} S{g.smartness:.2f}")
        else:
            lines.append("None")

        self.gen_label.configure(state="normal")
        self.gen_label.delete("1.0", tk.END)
        self.gen_label.insert("1.0", "\n".join(lines))
        self.gen_label.configure(state="disabled")
        self.last_population_count = len(self.gooblets)

    def start_new_simulation(self):
        seed_text = self.seed_var.get().strip()
        if seed_text:
            try:
                seed_value = int(seed_text)
            except ValueError:
                seed_value = seed_text
        else:
            seed_value = None
        self.reset_simulation(seed_value=seed_value)

    def reset_simulation(self, seed_value=None):
        self.running = False
        self.selected_gooblet = None
        self.shift_down = False
        self.ctrl_down = False
        self.time_multiplier = 1.0
        self.base_update_delay = 40
        self.last_draw_time = 0.0
        self.last_stats_update = 0.0
        self.canvas.delete("all")

        global cure_discovered, cure_location
        cure_discovered = False
        cure_location = None

        if seed_value is None:
            random.seed()
        else:
            random.seed(seed_value)

        self.current_seed = seed_value
        self.seed_status_label.config(text=f"Seed: {seed_value if seed_value is not None else 'random'}")

        self.lakes = []
        toxic_lake_index = random.randrange(LAKE_COUNT)
        for i in range(LAKE_COUNT):
            while True:
                lx = random.randint(60, WIDTH-60)
                ly = random.randint(60, HEIGHT-60)
                lr = random.randint(30, 55)
                if all(math.hypot(lx - ol[0], ly - ol[1]) > (lr + ol[2] + 20) for ol in self.lakes):
                    ltype = "toxic" if i == toxic_lake_index else "clean"
                    self.lakes.append([lx, ly, lr, ltype])
                    break

        self.berries = []
        self.spawn_berries(BERRY_COUNT)
        self.gooblets = [Gooblet(random.randint(0, WIDTH), random.randint(0, HEIGHT)) for _ in range(INITIAL_GOOBLETS)]
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
        self.decorations = []
        self.berry_bushes = []
        self.grass = []
        self.flower_patches = []
        self.forest_centers = []
        self.stage = "Stone Age"
        self.resource_respawn_tick = 0
        self.generate_decorations()

        self.btn_toggle.config(text="Pause Simulation")
        self.stats_label.config(text="Click a Gooblet\nto see stats")
        self.refresh_overview()
        self.stage_label.config(text="Stage: Stone Age")
        self.count_label.config(text="Trees: 0 | Rocks: 0")
        self.resource_label.config(text="Wood: 0 Stone: 0\nBronze: 0 Iron: 0")
        self.running = True
        self.draw()
        self.update()

    def update(self):
        if not self.running: return

        if len(self.berries) < BERRY_COUNT and random.random() < 0.05:
            self.spawn_berries(1)

        new_borns = []

        for g in self.gooblets[:]:
            g.move(self)
            if not g.alive:
                if g == self.selected_gooblet: self.selected_gooblet = None
                self.gooblets.remove(g)

        if len(self.gooblets) != self.last_population_count:
            self.refresh_overview()

        now = time.time()
        should_draw = now - self.last_draw_time >= 0.05
        if should_draw:
            self.draw()
            self.last_draw_time = now

        if self.selected_gooblet:
            g = self.selected_gooblet
            sick_status = f"\nSICK: {int(SICKNESS_DURATION - g.sick_time)}s left" if g.is_sick else ""
            status = f"ID: {id(g) % 1000}\nGen: {g.generation}\n\nHealth: {int(g.health)}%\nSmart: {g.smartness:.2f}{sick_status}\nStrength: {g.strength:.1f}\nSpeed: {g.speed:.2f}\nSight: {g.sight:.1f}\n\nHunger: {int(g.hunger)}%\nThirst: {int(g.thirst)}%\nState: {g.state}"
            self.stats_label.config(text=status)
        else:
            self.stats_label.config(text="Click a Gooblet\nto see stats")

        if now - self.last_stats_update >= 1.0 and len(self.gooblets) != self.last_population_count:
            self.refresh_overview()
            self.last_stats_update = now

        self.root.after(16, self.update)

    def draw(self):
        self.canvas.delete("all")
        for l in self.lakes:
            color = "#859900" if l[3] == "toxic" else "#268bd2"
            self.canvas.create_oval(l[0]-l[2], l[1]-l[2], l[0]+l[2], l[1]+l[2], fill=color, outline="#073642")
        for b in self.berries:
            self.canvas.create_oval(b[0]-3, b[1]-3, b[0]+3, b[1]+3, fill="#dc322f", outline="#990000")
        for g in self.gooblets:
            outline = "#b58900" if g.ready_to_mate else ("#cb4b16" if g.in_combat else ("black" if g == self.selected_gooblet else ""))
            width = 3 if (g == self.selected_gooblet or g.in_combat or g.ready_to_mate) else 1
            self.canvas.create_oval(g.x-g.radius, g.y-g.radius, g.x+g.radius, g.y+g.radius, fill=g.color, outline=outline, width=width)
            if g == self.selected_gooblet:
                self.canvas.create_oval(g.x-g.sight, g.y-g.sight, g.x+g.sight, g.y+g.sight, outline="#93a1a1", dash=(4, 4))

############################################################
# GOOBLET EVOLUTION EXPANSION
# PART 1A - WORLD DECORATIONS
############################################################

# ---------- Decorative Objects ----------

class WorldObject:
    def __init__(self, x, y, kind):
        self.x = x
        self.y = y
        self.kind = kind


# Add a list of decorative objects to the world
_old_world_init = SimulationWorld.__init__

def _new_world_init(self, root):
    # Base init triggers an immediate update/draw, so pre-create fields used by draw patches.
    self.decorations = []
    self.berry_bushes = []
    self.grass = []
    self.flower_patches = []
    self.forest_centers = []

    _old_world_init(self, root)

    self.generate_decorations()

SimulationWorld.__init__ = _new_world_init


def generate_decorations(self):

    import random

    decoration_radius = {
        "tree": 12,
        "rock": 7,
        "bush": 9,
        "flower": 3,
        "mushroom": 5,
    }

    def can_place(x, y, kind):
        radius = decoration_radius[kind]

        # Keep decorations out of lakes.
        for lx, ly, lr, _ in self.lakes:
            if math.hypot(x - lx, y - ly) < (lr + radius + 4):
                return False

        # Keep decorations from stacking on top of each other.
        for obj in self.decorations:
            other_r = decoration_radius.get(obj.kind, 6)
            if math.hypot(x - obj.x, y - obj.y) < (radius + other_r + 2):
                return False

        return True

    def place_many(kind, count):
        placed = 0
        attempts = 0
        max_attempts = count * 80

        while placed < count and attempts < max_attempts:
            attempts += 1
            x = random.randint(20, WIDTH - 20)
            y = random.randint(20, HEIGHT - 20)
            if can_place(x, y, kind):
                self.decorations.append(WorldObject(x, y, kind))
                placed += 1

    # Trees
    place_many("tree", 40)

    # Rocks
    place_many("rock", 35)

    # Bushes
    place_many("bush", 30)

    # Flowers
    place_many("flower", 60)

    # Mushrooms
    place_many("mushroom", 20)

SimulationWorld.generate_decorations = generate_decorations


# -------- Drawing Patch --------

_old_draw = SimulationWorld.draw

def _draw_with_decorations(self):

    _old_draw(self)

    for obj in self.decorations:

        if obj.kind == "tree":

            self.canvas.create_rectangle(
                obj.x-2,
                obj.y,
                obj.x+2,
                obj.y+10,
                fill="#6b4423",
                outline=""
            )

            self.canvas.create_oval(
                obj.x-10,
                obj.y-12,
                obj.x+10,
                obj.y+8,
                fill="#228B22",
                outline=""
            )

        elif obj.kind == "rock":

            self.canvas.create_oval(
                obj.x-6,
                obj.y-4,
                obj.x+6,
                obj.y+4,
                fill="gray55",
                outline="gray30"
            )

        elif obj.kind == "bush":

            self.canvas.create_oval(
                obj.x-8,
                obj.y-6,
                obj.x+8,
                obj.y+6,
                fill="#2E8B57",
                outline=""
            )

        elif obj.kind == "flower":

            self.canvas.create_oval(
                obj.x-2,
                obj.y-2,
                obj.x+2,
                obj.y+2,
                fill="yellow",
                outline=""
            )

            self.canvas.create_line(
                obj.x,
                obj.y+2,
                obj.x,
                obj.y+7,
                fill="green"
            )

        elif obj.kind == "mushroom":

            self.canvas.create_rectangle(
                obj.x-1,
                obj.y,
                obj.x+1,
                obj.y+5,
                fill="#EEE8AA",
                outline=""
            )

            self.canvas.create_arc(
                obj.x-4,
                obj.y-4,
                obj.x+4,
                obj.y+4,
                start=0,
                extent=180,
                fill="red",
                outline=""
            )

        elif obj.kind == "house":

            self.canvas.create_rectangle(
                obj.x-10,
                obj.y-6,
                obj.x+10,
                obj.y+10,
                fill="#deb887",
                outline="#8b4513"
            )
            self.canvas.create_polygon(
                obj.x-12,
                obj.y-6,
                obj.x+12,
                obj.y-6,
                obj.x,
                obj.y-18,
                fill="#a52a2a",
                outline="#8b4513"
            )
            self.canvas.create_rectangle(
                obj.x-4,
                obj.y,
                obj.x+4,
                obj.y+6,
                fill="#654321",
                outline=""
            )

SimulationWorld.draw = _draw_with_decorations

print("Expansion Part 1A Loaded")
############################################################
# GOOBLET EVOLUTION EXPANSION
# PART 1B - INTERACTIVE DECORATIONS
############################################################

# ---------- Berry Bushes ----------

if not hasattr(SimulationWorld, "berry_bushes"):
    SimulationWorld.berry_bushes = []


_old_generate = SimulationWorld.generate_decorations


def _generate_plus(self):

    _old_generate(self)

    import random

    self.berry_bushes = []

    def is_valid_bush_spot(x, y):
        for lx, ly, lr, _ in self.lakes:
            if math.hypot(x - lx, y - ly) < (lr + 12):
                return False
        return True

    placed = 0
    attempts = 0
    while placed < 15 and attempts < 1500:
        attempts += 1
        x = random.randint(30, WIDTH-30)
        y = random.randint(30, HEIGHT-30)
        if is_valid_bush_spot(x, y):
            self.berry_bushes.append({
                "x": x,
                "y": y,
                "timer": random.randint(0, 200)
            })
            placed += 1


SimulationWorld.generate_decorations = _generate_plus


##########################################################
# Regrow berries automatically
##########################################################

_prev_update_for_berries = SimulationWorld.update


def _update_plus(self, _prev=_prev_update_for_berries):

    for bush in getattr(self, "berry_bushes", []):
        bush["timer"] += 1
        if bush["timer"] > 250:
            bush["timer"] = 0
            self.berries.append([
                bush["x"] + random.randint(-12, 12),
                bush["y"] + random.randint(-12, 12),
            ])

    _prev(self)


SimulationWorld.update = _update_plus


##########################################################
# Rocks block movement
##########################################################

_prev_move_for_rocks = Gooblet.move


def _move_plus(self, world, _prev=_prev_move_for_rocks):

    oldx = self.x
    oldy = self.y

    _prev(self, world)

    if hasattr(world, "decorations"):

        for obj in world.decorations:

            if obj.kind != "rock":
                continue

            d = math.hypot(

                self.x-obj.x,

                self.y-obj.y

            )

            if d < 12:

                self.x = oldx
                self.y = oldy
                break


Gooblet.move = _move_plus


##########################################################
# Draw berry bushes
##########################################################

_old_draw2 = SimulationWorld.draw


def _draw_plus(self):

    _old_draw2(self)

    for bush in self.berry_bushes:

        x = bush["x"]
        y = bush["y"]

        self.canvas.create_oval(

            x-9,
            y-9,
            x+9,
            y+9,

            fill="#2E8B57",
            outline="darkgreen"

        )

        self.canvas.create_oval(

            x-2,y-2,x+2,y+2,

            fill="red",

            outline=""

        )


SimulationWorld.draw = _draw_plus


##########################################################
# Tree shade
##########################################################

_old_draw3 = SimulationWorld.draw


def _draw_shadows(self):

    _old_draw3(self)

    for obj in self.decorations:

        if obj.kind == "tree":

            self.canvas.create_oval(

                obj.x-16,

                obj.y-8,

                obj.x+16,

                obj.y+8,

                outline="",

                fill="#000000"

            )


SimulationWorld.draw = _draw_shadows


print("Expansion Part 1B Loaded")
############################################################
# GOOBLET EVOLUTION EXPANSION
# PART 1C - BIOMES & WORLD LIFE
############################################################

# ---------- Grass Tufts ----------

if not hasattr(SimulationWorld, "grass"):
    SimulationWorld.grass = []

_old_generate_biomes = SimulationWorld.generate_decorations

def _generate_biomes(self):

    _old_generate_biomes(self)

    import random

    self.grass = []

    self.flower_patches = []

    self.forest_centers = []

    def lake_clear(x, y, margin):
        for lx, ly, lr, _ in self.lakes:
            if math.hypot(x - lx, y - ly) < (lr + margin):
                return False
        return True

    def safe_point(xmin, xmax, ymin, ymax, margin, fallback):
        for _ in range(200):
            x = random.randint(xmin, xmax)
            y = random.randint(ymin, ymax)
            if lake_clear(x, y, margin):
                return (x, y)
        return fallback

    # Tall grass
    for _ in range(220):
        gx, gy = safe_point(5, WIDTH-5, 5, HEIGHT-5, 6, (random.randint(5, WIDTH-5), random.randint(5, HEIGHT-5)))
        self.grass.append((
            gx,
            gy,
            random.randint(4,10)
        ))

    # Flower patches
    for _ in range(18):
        self.flower_patches.append(
            safe_point(40, WIDTH-40, 40, HEIGHT-40, 20, (random.randint(40, WIDTH-40), random.randint(40, HEIGHT-40)))
        )

    # Forest centers
    for _ in range(5):
        self.forest_centers.append(
            safe_point(100, WIDTH-100, 100, HEIGHT-100, 35, (random.randint(100, WIDTH-100), random.randint(100, HEIGHT-100)))
        )

SimulationWorld.generate_decorations = _generate_biomes


############################################################
# Add forest trees
############################################################

_old_draw_world = SimulationWorld.draw

def _draw_world(self):

    _old_draw_world(self)

    # Grass
    for x,y,h in self.grass:

        self.canvas.create_line(
            x,
            y,
            x,
            y-h,
            fill="#3fa34d"
        )

    # Flower patches
    colors = [
        "red",
        "yellow",
        "white",
        "pink",
        "purple"
    ]

    for cx,cy in self.flower_patches:

        for i in range(15):

            angle = (i / 15.0) * 2 * math.pi
            radius = 8 + (i % 5)
            px = cx + int(math.cos(angle) * radius)
            py = cy + int(math.sin(angle) * radius)
            color = colors[i % len(colors)]

            self.canvas.create_oval(
                px-2,
                py-2,
                px+2,
                py+2,
                fill=color,
                outline=""
            )

    # Dense forests
    for fx,fy in self.forest_centers:

        for i in range(12):

            angle = (i / 12.0) * 2 * math.pi
            radius = 15 + (i % 4) * 5
            tx = fx + int(math.cos(angle) * radius)
            ty = fy + int(math.sin(angle) * radius)

            self.canvas.create_rectangle(
                tx-2,
                ty,
                tx+2,
                ty+9,
                fill="#6b4423",
                outline=""
            )

            self.canvas.create_oval(
                tx-10,
                ty-10,
                tx+10,
                ty+8,
                fill="#1f7a1f",
                outline=""
            )

SimulationWorld.draw = _draw_world


############################################################
# Gooblets slow slightly in tall grass
############################################################

_old_move_biomes = Gooblet.move

def _move_biomes(self, world):

    original_speed = self.speed

    if hasattr(world, "grass"):

        for gx,gy,h in world.grass:

            if math.hypot(self.x-gx,self.y-gy) < 5:

                self.speed *= 0.92
                break

    _old_move_biomes(self, world)

    self.speed = original_speed

Gooblet.move = _move_biomes


############################################################
# Ambient world statistics
############################################################

_old_update_stats = SimulationWorld.update

def _update_stats(self):

    _old_update_stats(self)

    if hasattr(self, "gen_label"):
        try:
            self.gen_label.configure(state="normal")
            current_text = self.gen_label.get("1.0", tk.END).rstrip()
            extra_lines = [
                f"Trees: {len([d for d in self.decorations if d.kind=='tree'])}",
                f"Rocks: {len([d for d in self.decorations if d.kind=='rock'])}",
                f"Bushes: {len(self.berry_bushes)}",
            ]
            if current_text:
                updated_text = current_text + "\n" + "\n".join(extra_lines)
            else:
                updated_text = "\n".join(extra_lines)
            self.gen_label.delete("1.0", tk.END)
            self.gen_label.insert("1.0", updated_text)
            self.gen_label.configure(state="disabled")
        except Exception:
            pass

SimulationWorld.update = _update_stats

print("Expansion Part 1C Loaded")
############################################################
# GOOBLET EVOLUTION EXPANSION CORE
# CORE A1
############################################################

print("Loading Expansion Core A1...")

# ==========================================================
# Extension Manager
# ==========================================================

class ExpansionManager:

    def __init__(self):

        self.update_hooks = []
        self.draw_hooks = []
        self.spawn_hooks = []
        self.click_hooks = []

    def add_update(self, func):
        if func not in self.update_hooks:
            self.update_hooks.append(func)

    def add_draw(self, func):
        if func not in self.draw_hooks:
            self.draw_hooks.append(func)

    def add_spawn(self, func):
        if func not in self.spawn_hooks:
            self.spawn_hooks.append(func)

    def add_click(self, func):
        if func not in self.click_hooks:
            self.click_hooks.append(func)


EXPANSION = ExpansionManager()


# ==========================================================
# World Data
# ==========================================================

def expansion_initialize(world):

    if hasattr(world, "_expansion_initialized"):
        return

    world._expansion_initialized = True

    world.expansion = {}

    world.expansion["objects"] = []

    world.expansion["terrain"] = []

    world.expansion["weather"] = "clear"

    world.expansion["season"] = "spring"

    world.expansion["day"] = 1

    world.expansion["ticks"] = 0

    print("Expansion World Initialized")


# ==========================================================
# Patch SimulationWorld.__init__
# ==========================================================

_original_init = SimulationWorld.__init__

def _core_init(self, root):

    _original_init(self, root)

    expansion_initialize(self)

    for func in EXPANSION.spawn_hooks:
        func(self)

SimulationWorld.__init__ = _core_init


# ==========================================================
# Utility Functions
# ==========================================================

def world_add_object(world, obj):

    world.expansion["objects"].append(obj)


def world_objects(world):

    return world.expansion["objects"]


def world_tick(world):

    world.expansion["ticks"] += 1


print("Expansion Core A1 Loaded")
############################################################
# GOOBLET EVOLUTION EXPANSION CORE
# CORE A2
############################################################

print("Loading Expansion Core A2...")

# ==========================================================
# Patch UPDATE
# ==========================================================

_core_original_update = SimulationWorld.update

def _core_update(self):

    # Make sure expansion exists
    if not hasattr(self, "expansion"):
        expansion_initialize(self)

    # World clock
    world_tick(self)

    # Run registered update hooks
    for hook in list(EXPANSION.update_hooks):
        try:
            hook(self)
        except Exception as e:
            print("[Expansion Update Hook]", e)

    # Original simulation
    _core_original_update(self)

SimulationWorld.update = _core_update


# ==========================================================
# Patch DRAW
# ==========================================================

_core_original_draw = SimulationWorld.draw

def _core_draw(self):

    # Draw normal simulator first
    _core_original_draw(self)

    # Draw expansion objects afterwards
    for hook in list(EXPANSION.draw_hooks):

        try:
            hook(self)

        except Exception as e:
            print("[Expansion Draw Hook]", e)

SimulationWorld.draw = _core_draw


# ==========================================================
# Patch Mouse Clicks
# ==========================================================

_core_original_click = SimulationWorld.on_click

def _core_click(self, event):

    _core_original_click(self, event)

    for hook in list(EXPANSION.click_hooks):

        try:
            hook(self, event)

        except Exception as e:
            print("[Expansion Click Hook]", e)

SimulationWorld.on_click = _core_click


# ==========================================================
# Helper Functions
# ==========================================================

def expansion_message(text):

    print("[Expansion]", text)


def expansion_tick(world):

    return world.expansion["ticks"]


def expansion_day(world):

    return world.expansion["day"]


def expansion_weather(world):

    return world.expansion["weather"]


def expansion_season(world):

    return world.expansion["season"]


# ==========================================================
# Debug Overlay
# ==========================================================

SHOW_DEBUG = False

def expansion_debug_draw(world):

    if not SHOW_DEBUG:
        return

    t = world.expansion["ticks"]

    world.canvas.create_text(

        10,
        10,

        anchor="nw",

        text=f"Expansion Tick: {t}",

        fill="white",

        font=("Arial",10,"bold")

    )


EXPANSION.add_draw(expansion_debug_draw)

print("Expansion Core A2 Loaded")
############################################################
# GOOBLET EXPANSION
# OLD AGE SYSTEM
############################################################

import random

# Average lifespan (in simulation updates)
AVERAGE_LIFESPAN = 1800
LIFESPAN_VARIATION = 600


_old_gooblet_init = Gooblet.__init__

def _age_init(self, *args, **kwargs):
    _old_gooblet_init(self, *args, **kwargs)

    self.age = 0

    self.max_age = random.randint(
        AVERAGE_LIFESPAN - LIFESPAN_VARIATION,
        AVERAGE_LIFESPAN + LIFESPAN_VARIATION
    )

Gooblet.__init__ = _age_init


_old_gooblet_move = Gooblet.move

def _age_move(self, world):
    # Disabled: superseded by the later age-per-second system.
    _old_gooblet_move(self, world)

Gooblet.move = _age_move

print("Old Age System Loaded")
############################################################
# AGE SYSTEM
############################################################

import time

# ----- Add age to every new Gooblet -----

_old_init = Gooblet.__init__

def _new_init(self, *args, **kwargs):
    _old_init(self, *args, **kwargs)

    self.age = 0
    self.last_age_tick = time.time()

Gooblet.__init__ = _new_init


# ----- Age increases every second -----

_prev_move_for_age_seconds = Gooblet.move

def _new_move(self, world, _prev=_prev_move_for_age_seconds):

    if self.alive:

        now = time.time()

        if now - self.last_age_tick >= 1:
            self.age += 1
            self.last_age_tick = now

        if self.age >= 200:
            self.alive = False
            return

    _prev(self, world)

Gooblet.move = _new_move


# ----- Show age when clicked -----

_prev_update_for_age_ui = SimulationWorld.update

def _new_update(self, _prev=_prev_update_for_age_ui):

    _prev(self)

    if self.selected_gooblet and self.selected_gooblet.alive:

        g = self.selected_gooblet

        sick = ""

        if g.is_sick:
            sick = f"\nSICK: {int(SICKNESS_DURATION-g.sick_time)}s"

        self.stats_label.config(
            text=
            f"ID: {id(g)%1000}\n"
            f"Generation: {g.generation}\n"
            f"Age: {g.age}/200\n\n"
            f"Health: {int(g.health)}%\n"
            f"Smartness: {g.smartness:.2f}\n"
            f"Strength: {g.strength:.1f}\n"
            f"Speed: {g.speed:.2f}\n"
            f"Sight: {g.sight:.1f}"
            f"{sick}"
            f"\n\n"
            f"Hunger: {int(g.hunger)}%\n"
            f"Thirst: {int(g.thirst)}%\n"
            f"State: {g.state}"
        )

SimulationWorld.update = _new_update

print("Age System Loaded")
############################################################
# CONTAGIOUS SICKNESS EXPANSION
############################################################

import random
import math
import time

SNEEZE_RADIUS = 50
SNEEZE_CHANCE = 0.006      # Chance each update while sick

# -----------------------------
# Add sneeze timer
# -----------------------------

_old_init_sneeze = Gooblet.__init__

def _init_sneeze(self, *args, **kwargs):
    _old_init_sneeze(self, *args, **kwargs)
    self.last_sneeze = 0

Gooblet.__init__ = _init_sneeze


# -----------------------------
# Infect nearby gooblets
# -----------------------------

_old_move_sneeze = Gooblet.move

def _move_sneeze(self, world):

    if self.alive and self.is_sick:

        if random.random() < SNEEZE_CHANCE:

            self.last_sneeze = time.time()

            # Infect nearby gooblets
            for other in world.gooblets:

                if other is self:
                    continue

                if not other.alive:
                    continue

                if other.is_sick:
                    continue

                dist = math.hypot(
                    self.x - other.x,
                    self.y - other.y
                )

                if dist <= SNEEZE_RADIUS:

                    infection_chance = 0.75 * (1 - other.smartness * 0.5)

                    if random.random() < infection_chance:

                        other.is_sick = True
                        other.sick_time = 0
                        other.curing_progress = 0

    _old_move_sneeze(self, world)

Gooblet.move = _move_sneeze


# -----------------------------
# Draw sneeze cloud
# -----------------------------

_old_draw_sneeze = SimulationWorld.draw

def _draw_sneeze(self):

    _old_draw_sneeze(self)

    now = time.time()

    for g in self.gooblets:

        if hasattr(g, "last_sneeze"):

            if now - g.last_sneeze < 0.35:

                self.canvas.create_oval(
                    g.x-SNEEZE_RADIUS,
                    g.y-SNEEZE_RADIUS,
                    g.x+SNEEZE_RADIUS,
                    g.y+SNEEZE_RADIUS,
                    outline="#88ff88",
                    dash=(4,4)
                )

                self.canvas.create_text(
                    g.x,
                    g.y-15,
                    text="ACHOO!",
                    fill="green",
                    font=("Arial",8,"bold")
                )

SimulationWorld.draw = _draw_sneeze


# -----------------------------
# Cure progress modifier removed.
# Curing should only happen at the cure station.
# -----------------------------

_prev_update_after_sneeze = SimulationWorld.update

def _update_after_sneeze(self, _prev=_prev_update_after_sneeze):
    _prev(self)

SimulationWorld.update = _update_after_sneeze

print("Contagious Sickness Loaded")
############################################################
# CURE RESEARCH SYSTEM
############################################################

import random
import time
import math

SMARTNESS_STATION_THRESHOLD = 0.5
STATION_SPAWN_CHANCE = 0.01
cure_discovered = False
cure_location = None


# ----------------------------
# Draw cure station
# ----------------------------

_old_draw_cure = SimulationWorld.draw

def _draw_cure(self):

    global cure_discovered, cure_location

    _old_draw_cure(self)

    if cure_discovered and cure_location:

        x, y = cure_location

        self.canvas.create_oval(
            x-14, y-14,
            x+14, y+14,
            fill="cyan",
            outline="blue",
            width=3
        )

        self.canvas.create_text(
            x,
            y-22,
            text="CURE",
            fill="blue",
            font=("Arial",9,"bold")
        )

SimulationWorld.draw = _draw_cure


# ----------------------------
# Cure research
# ----------------------------

def _update_cure_station_hook(world):

    global cure_discovered, cure_location

    if cure_discovered or not getattr(world, "gooblets", None):
        return

    smartness_values = [getattr(g, "smartness", 0.0) for g in world.gooblets]
    if not smartness_values:
        return

    avg_smart = sum(smartness_values) / len(smartness_values)
    max_smart = max(smartness_values)

    if avg_smart >= SMARTNESS_STATION_THRESHOLD or max_smart >= SMARTNESS_STATION_THRESHOLD:
        cure_discovered = True
        cure_location = (
            random.randint(40, WIDTH-40),
            random.randint(40, HEIGHT-40)
        )
        print("A curing station has appeared!")

EXPANSION.add_update(_update_cure_station_hook)


# ----------------------------
# Sick gooblets seek cure
# ----------------------------

_old_move_cure = Gooblet.move

def _move_cure(self, world):

    global cure_discovered, cure_location

    if (
        self.alive
        and self.is_sick
        and cure_discovered
        and cure_location
    ):

        # Preserve existing aging/sickness/needs updates before cure seeking.
        _old_move_cure(self, world)
        clamp_gooblet_to_world(self)

        if not self.alive or not self.is_sick:
            return

        tx, ty = cure_location

        angle = math.atan2(
            ty-self.y,
            tx-self.x
        )

        self.x += math.cos(angle) * self.speed
        self.y += math.sin(angle) * self.speed
        clamp_gooblet_to_world(self)

        if math.hypot(
            self.x-tx,
            self.y-ty
        ) < 15:

            self.is_sick = False
            self.sick_time = 0
            self.curing_progress = 0
            self.health = min(100, self.health + 40)

        return

    _old_move_cure(self, world)
    clamp_gooblet_to_world(self)

Gooblet.move = _move_cure

print("Cure Research System Loaded")
# ============================================================
# STATIC WORLD UPDATE (Gooblets only)
# ============================================================

print("Static World Update Loaded")

def _static_world_update(self):
    if not self.running:
        return

    now = time.time()
    should_draw = now - getattr(self, "last_draw_time", 0.0) >= 0.05
    should_update_stats = now - getattr(self, "last_stats_update", 0.0) >= 0.25

    for bush in getattr(self, "berry_bushes", []):
        bush["timer"] += 1
        if bush["timer"] > 250:
            bush["timer"] = 0
            self.berries.append([
                bush["x"] + random.randint(-12, 12),
                bush["y"] + random.randint(-12, 12),
            ])

    if len(self.gooblets) == 0:
        for _ in range(2):
            while True:
                x = random.randint(20, WIDTH-20)
                y = random.randint(20, HEIGHT-20)
                if not any(math.hypot(x - lx, y - ly) < l[2] + 5 for l in self.lakes):
                    self.gooblets.append(Gooblet(x, y))
                    break

    new_borns = []

    for g in self.gooblets[:]:
        g.move(self)
        if g.alive:
            g.gather_resources(self, self.stage)
        if not g.alive:
            if g == self.selected_gooblet:
                self.selected_gooblet = None
            self.gooblets.remove(g)

    if should_draw:
        self.draw()
        self.last_draw_time = now

    if self.selected_gooblet:
        g = self.selected_gooblet
        sick_status = f"\nSICK: {int(SICKNESS_DURATION - g.sick_time)}s left" if g.is_sick else ""
        status = (
            f"ID: {id(g) % 1000}\nGen: {g.generation}\n\n"
            f"Health: {int(g.health)}%\nSmart: {g.smartness:.2f}{sick_status}\n"
            f"Strength: {g.strength:.1f}\nSpeed: {g.speed:.2f}\nSight: {g.sight:.1f}\n\n"
            f"Hunger: {int(g.hunger)}%\nThirst: {int(g.thirst)}%\nState: {g.state}"
        )
        self.stats_label.config(text=status)
    else:
        self.stats_label.config(text="Click a Gooblet\nto see stats")

    self.resource_respawn_tick += 1
    if self.resource_respawn_tick >= 150:
        self.resource_respawn_tick = 0
        self.respawn_resources()

    if should_update_stats:
        avg_gen = sum(g.generation for g in self.gooblets) / len(self.gooblets) if self.gooblets else 0
        avg_smartness = sum(g.smartness for g in self.gooblets) / len(self.gooblets) if self.gooblets else 0
        self.gen_label.config(text=f"Avg Gen: {avg_gen:.1f}\nAvg Smart: {avg_smartness:.2f}\nPop: {len(self.gooblets)}")
        self.last_stats_update = now

    if self.gooblets:
        avg_speed = sum(g.speed for g in self.gooblets) / len(self.gooblets)
        avg_sight = sum(g.sight for g in self.gooblets) / len(self.gooblets)
        avg_smartness = sum(g.smartness for g in self.gooblets) / len(self.gooblets)
        avg_strength = sum(g.strength for g in self.gooblets) / len(self.gooblets)
        evolution_score = (
            (avg_speed / 5.0) +
            (avg_sight / 130.0) +
            avg_smartness +
            (avg_strength / 15.0)
        ) / 4.0
        if evolution_score < 0.22:
            stage = "Stone Age"
        elif evolution_score < 0.38:
            stage = "Bronze Age"
        elif evolution_score < 0.56:
            stage = "Medieval Age"
        elif evolution_score < 0.74:
            stage = "Industrial Age"
        else:
            stage = "Modern Age"
    else: 
        stage = "Stone Age"

    self.stage = stage
    self.stage_label.config(text=f"Stage: {stage}")

    if stage == "Stone Age":
        while self.resources["wood"] >= 10 and self.resources["stone"] >= 6:
            self.resources["wood"] -= 10
            self.resources["stone"] -= 6
            self.resources["tent"] += 1
        while self.resources["wood"] >= 6 and self.resources["stone"] >= 4:
            self.resources["wood"] -= 6
            self.resources["stone"] -= 4
            self.resources["fire"] += 1
        while self.resources["wood"] >= 4 and self.resources["stone"] >= 2:
            self.resources["wood"] -= 4
            self.resources["stone"] -= 2
            self.resources["tool"] += 1
    elif stage == "Bronze Age":
        while self.resources["stone"] >= 3 and self.resources["bronze"] >= 2:
            self.resources["stone"] -= 3
            self.resources["bronze"] -= 2
            self.resources["tool"] += 1
        while self.resources["bronze"] >= 5 and self.resources["stone"] >= 4:
            self.resources["bronze"] -= 5
            self.resources["stone"] -= 4
            self.resources["tent"] += 1
    elif stage == "Industrial Age":
        while self.resources["wood"] >= 10 and self.resources["stone"] >= 6:
            self.resources["wood"] -= 10
            self.resources["stone"] -= 6
            self.resources["house"] += 1
            self.spawn_decoration("house")
        while self.resources["iron"] >= 5 and self.resources["stone"] >= 2:
            self.resources["iron"] -= 5
            self.resources["stone"] -= 2
            self.resources["cannon"] += 1
        while self.resources["iron"] >= 3:
            self.resources["iron"] -= 3
            self.resources["musket"] += 1
    elif stage == "Modern Age":
        while self.resources["iron"] >= 5 and self.resources["bronze"] >= 2:
            self.resources["iron"] -= 5
            self.resources["bronze"] -= 2
            self.resources["machine_gun"] += 1
        while self.resources["iron"] >= 2 and self.resources["wood"] >= 2:
            self.resources["iron"] -= 2
            self.resources["wood"] -= 2
            self.resources["phone"] += 1
        while self.resources["iron"] >= 2 and self.resources["bronze"] >= 1:
            self.resources["iron"] -= 2
            self.resources["bronze"] -= 1
            self.resources["pistol"] += 1

    if hasattr(self, "decorations"):
        tree_count = len([d for d in self.decorations if d.kind == 'tree'])
        rock_count = len([d for d in self.decorations if d.kind == 'rock'])
        self.count_label.config(text=f"Trees: {tree_count} | Rocks: {rock_count}")
    self.resource_label.config(
        text=(
            f"Wood: {self.resources['wood']} Stone: {self.resources['stone']}\n"
            f"Bronze: {self.resources['bronze']} Iron: {self.resources['iron']}\n"
            f"Tents: {self.resources['tent']} Fires: {self.resources['fire']} Tools: {self.resources['tool']}\n"
            f"Houses: {self.resources['house']} Cannons: {self.resources['cannon']} Muskets: {self.resources['musket']}\n"
            f"Phones: {self.resources['phone']} Pistols: {self.resources['pistol']} MGs: {self.resources['machine_gun']}"
        )
    )

    delay = max(20, min(80, int(self.base_update_delay / self.time_multiplier)))
# SPAWN GOOBLETS BY HOLDING S AND CLICKING
# ============================================================

print("Gooblet Spawn-On-Click Loaded")

# Track S key state
_spawn_s_down = False


def _spawn_key_press(event):
    global _spawn_s_down
    _spawn_s_down = True


def _spawn_key_release(event):
    global _spawn_s_down
    _spawn_s_down = False


def _spawn_gooblet_click(world, event):
    global _spawn_s_down

    # Spawn on left click while S is held, OR allow spawning by left-click
    # when there are no gooblets alive so the user can repopulate the world.
    if getattr(event, "num", 1) == 1 and (_spawn_s_down or not getattr(world, "gooblets", [])):
        x, y = world.screen_to_world(event.x, event.y)
        g = Gooblet(x, y)
        clamp_gooblet_to_world(g)
        world.gooblets.append(g)
        # If no gooblets existed before, select the newly spawned one.
        world.selected_gooblet = g
        print("Spawned Gooblet at", int(x), int(y))


def _bind_spawn_keys(world):
    # Track S key globally and hook mouse clicks globally for reliable spawning.
    world.root.bind_all("<KeyPress-s>", _spawn_key_press, add="+")
    world.root.bind_all("<KeyRelease-s>", _spawn_key_release, add="+")
    world.root.bind_all("<KeyPress-S>", _spawn_key_press, add="+")
    world.root.bind_all("<KeyRelease-S>", _spawn_key_release, add="+")
    world.root.bind_all("<Button-1>", lambda event, w=world: _spawn_gooblet_click(w, event), add="+")
    world.canvas.bind("<Button-1>", lambda event, w=world: _spawn_gooblet_click(w, event), add="+")
    world.root.focus_set()


EXPANSION.add_spawn(_bind_spawn_keys)

print("Spawn-On-Click (S Key) Loaded")

# ============================================================
# VISUAL CANVAS SCALING (RESIZE)
# ============================================================

# Disabled: scaling the canvas each frame caused visual jitter.
# Keep the canvas size fixed and let Tkinter handle resizing naturally.

print("Visual Canvas Scaling Disabled to prevent jitter")


_draw_before_countries = SimulationWorld.draw


def _draw_with_countries(self):
    _draw_before_countries(self)
    draw_country_map(self)


SimulationWorld.draw = _draw_with_countries


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Gooblet Evolution Simulator")
    sim = SimulationWorld(root)
    root.mainloop()

