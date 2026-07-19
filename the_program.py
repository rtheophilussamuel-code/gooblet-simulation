import tkinter as tk
import random
import math
import time

# --- Constants ---
WIDTH = 800
HEIGHT = 600
INITIAL_GOOBLETS = 25
BERRY_COUNT = 35
LAKE_COUNT = 5
MUTATION_RATE = 0.15
REPRODUCTION_HUNGER_THRESHOLD = 45
WANDER_CHANGE_CHANCE = 0.06
COMBAT_DISTANCE = 15
SICKNESS_DURATION = 60 # Seconds until death

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

class Gooblet:
    def __init__(self, x, y, stats=None, generation=1):
        self.x = x
        self.y = y
        self.generation = generation
        
        # Sickness attributes MUST be initialized before _get_color() is called
        self.is_sick = False
        self.sick_time = 0
        self.curing_progress = 0
        
        # Core Stats
        if stats:
            self.speed = max(1, stats['speed'] + random.uniform(-MUTATION_RATE, MUTATION_RATE) * 2)
            self.sight = max(20, stats['sight'] + random.uniform(-MUTATION_RATE, MUTATION_RATE) * 40)
            self.smartness = max(0.1, min(1.0, stats['smartness'] + random.uniform(-MUTATION_RATE, MUTATION_RATE)))
            self.strength = max(1, stats['strength'] + random.uniform(-MUTATION_RATE, MUTATION_RATE) * 5)
        else:
            self.speed = random.uniform(2, 4)
            self.sight = random.uniform(70, 130)
            self.smartness = random.uniform(0.3, 0.6)
            self.strength = random.uniform(5, 15)

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
            
        r = min(255, int((self.strength / 30) * 255))
        g = min(255, int((self.sight / 400) * 255))
        b = min(255, int((self.speed / 8) * 255))
        return f'#{r:02x}{g:02x}{b:02x}'

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

        self.ready_to_mate = self.hunger < REPRODUCTION_HUNGER_THRESHOLD and self.thirst < REPRODUCTION_HUNGER_THRESHOLD and not self.is_sick
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

        # Check for drowning
        if self.is_on_water(self.x, self.y, world.lakes):
            if random.random() > self.smartness * 0.5:
                self.alive = False

        clamp_gooblet_to_world(self)

    def is_on_water(self, x, y, lakes):
        for l in lakes:
            if math.hypot(l[0] - x, l[1] - y) < l[2] - 5:
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
        self.gen_label = tk.Label(self.info_panel, text="Gen: 1 | Pop: 0", font=("Arial", 10, "bold"), bg="#eee8d5")
        self.gen_label.pack(anchor="nw")
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
        self.selected_gooblet = None
        self.canvas.bind("<Button-1>", self.on_click)
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

    def toggle_running(self):
        self.running = not self.running
        self.btn_toggle.config(text="Pause Simulation" if self.running else "Start Simulation")
        if self.running: self.update()

    def update(self):
        if not self.running: return
        if len(self.berries) < BERRY_COUNT and random.random() < 0.1:
            self.spawn_berries(1)

        new_borns = []
        ready_mates = [g for g in self.gooblets if g.ready_to_mate]
        random.shuffle(ready_mates)
        while len(ready_mates) >= 2:
            p1 = ready_mates.pop(); p2 = ready_mates.pop()
            if math.hypot(p1.x - p2.x, p1.y - p2.y) < 35:
                child_stats = {
                    'speed': (p1.speed + p2.speed) / 2,
                    'sight': (p1.sight + p2.sight) / 2,
                    'smartness': (p1.smartness + p2.smartness) / 2,
                    'strength': (p1.strength + p2.strength) / 2
                }
                child = Gooblet((p1.x + p2.x)/2, (p1.y + p2.y)/2, stats=child_stats, generation=max(p1.generation, p2.generation) + 1)
                new_borns.append(child)
                p1.hunger += 25; p2.hunger += 25
                p1.ready_to_mate = False; p2.ready_to_mate = False

        for g in self.gooblets[:]:
            g.move(self)
            if not g.alive:
                if g == self.selected_gooblet: self.selected_gooblet = None
                self.gooblets.remove(g)
        
        self.gooblets.extend(new_borns)
        self.draw()
        
        if self.selected_gooblet:
            g = self.selected_gooblet
            sick_status = f"\nSICK: {int(SICKNESS_DURATION - g.sick_time)}s left" if g.is_sick else ""
            status = f"ID: {id(g) % 1000}\nGen: {g.generation}\n\nHealth: {int(g.health)}%\nSmart: {g.smartness:.2f}{sick_status}\nStrength: {g.strength:.1f}\nSpeed: {g.speed:.2f}\nSight: {g.sight:.1f}\n\nHunger: {int(g.hunger)}%\nThirst: {int(g.thirst)}%\nState: {g.state}"
            self.stats_label.config(text=status)
        else:
            self.stats_label.config(text="Click a Gooblet\nto see stats")
            
        avg_gen = sum(g.generation for g in self.gooblets) / len(self.gooblets) if self.gooblets else 0
        self.gen_label.config(text=f"Avg Gen: {avg_gen:.1f}\nPop: {len(self.gooblets)}")
        self.root.after(30, self.update)

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

    for bush in self.berry_bushes:

        bush["timer"] += 1

        if bush["timer"] > 250:

            bush["timer"] = 0

            self.berries.append([

                bush["x"] + random.randint(-12,12),

                bush["y"] + random.randint(-12,12)

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

        for _ in range(15):

            px = cx + random.randint(-15,15)
            py = cy + random.randint(-15,15)

            self.canvas.create_oval(
                px-2,
                py-2,
                px+2,
                py+2,
                fill=random.choice(colors),
                outline=""
            )

    # Dense forests
    for fx,fy in self.forest_centers:

        for _ in range(12):

            tx = fx + random.randint(-35,35)
            ty = fy + random.randint(-35,35)

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

    if hasattr(self,"gen_label"):

        self.gen_label.config(

            text=self.gen_label.cget("text") +

            f"\nTrees: {len([d for d in self.decorations if d.kind=='tree'])}"

            f"\nRocks: {len([d for d in self.decorations if d.kind=='rock'])}"

            f"\nBushes: {len(self.berry_bushes)}"

        )

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

_prev_update_for_cure_station = SimulationWorld.update

def _update_cure_station(self, _prev=_prev_update_for_cure_station):

    global cure_discovered, cure_location

    if (not cure_discovered) and len(self.gooblets):

        avg_smart = sum(g.smartness for g in self.gooblets) / len(self.gooblets)

        if avg_smart >= SMARTNESS_STATION_THRESHOLD and random.random() < STATION_SPAWN_CHANCE:

            cure_discovered = True

            cure_location = (
                random.randint(40, WIDTH-40),
                random.randint(40, HEIGHT-40)
            )

            print("A curing station has appeared!")

    _prev(self)

SimulationWorld.update = _update_cure_station


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
# LIGHT REPRODUCTION BOOST (Gentle Increase)
# ============================================================

print("Light Reproduction Boost Loaded")

_original_update_repro = SimulationWorld.update

def _update_repro_light(self):
    # Use a single reproduction pass from the base update chain.
    _original_update_repro(self)

SimulationWorld.update = _update_repro_light
# ============================================================
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

    # Only spawn on left click while S is held.
    if _spawn_s_down and getattr(event, "num", 1) == 1:
        x, y = world.screen_to_world(event.x, event.y)
        g = Gooblet(x, y)
        clamp_gooblet_to_world(g)
        world.gooblets.append(g)
        print("Spawned Gooblet at", int(x), int(y))


def _bind_spawn_keys(world):
    # Track S key globally and hook canvas click directly for reliable spawning.
    world.root.bind_all("<KeyPress-s>", _spawn_key_press)
    world.root.bind_all("<KeyRelease-s>", _spawn_key_release)
    world.root.bind_all("<KeyPress-S>", _spawn_key_press)
    world.root.bind_all("<KeyRelease-S>", _spawn_key_release)
    world.canvas.bind("<Button-1>", lambda event, w=world: _spawn_gooblet_click(w, event), add="+")
    world.canvas.focus_set()


EXPANSION.add_spawn(_bind_spawn_keys)

print("Spawn-On-Click (S Key) Loaded")

# ============================================================
# VISUAL CANVAS SCALING (RESIZE)
# ============================================================

_old_draw_visual_scale = SimulationWorld.draw


def _draw_visual_scale(self):
    _old_draw_visual_scale(self)

    current_w = max(1, self.canvas.winfo_width())
    current_h = max(1, self.canvas.winfo_height())

    self.visual_scale_x = current_w / WIDTH
    self.visual_scale_y = current_h / HEIGHT

    self.canvas.scale("all", 0, 0, self.visual_scale_x, self.visual_scale_y)


SimulationWorld.draw = _draw_visual_scale

print("Visual Canvas Scaling Loaded")


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Gooblet Evolution Simulator")
    sim = SimulationWorld(root)
    root.mainloop()

