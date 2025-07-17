"""Deterministic JSON‑level generator for the PDDL‑compatible Overcooked
benchmark described in the domain file you supplied.

Key design choices
------------------
*  **Determinism** – every call with identical arguments returns byte‑for‑byte
   identical JSON.  We achieve this by seeding Python's std‑lib `random`
   with *map_id*.
*  **Layout** – a simple rectilinear “pillar” maze: the border and every
   third column are counters (`'-'`).  Interior cells are walkable floor
   (`' '`).
*  **Placement policy**  
   •  *Counters* (`'-'`) receive all appliances, deliver squares,
      ingredients and plates.  
   •  *Floor* (`' '`) receives switches, blocks and agents.  
   •  Coordinates are picked uniformly from the eligible cells while
      avoiding collisions.  
   •  The number of plates is `max( len(goal_recipes) + 1 ,
      int(1.5 * len(goal_recipes)) )`.  
   •  Ingredients are generated so that **every recipe is completable**
      plus one spare copy of each required ingredient.
*  **No OPTIONAL keys** – stochasticity is handled entirely inside Python; the
   JSON itself is fully deterministic.
*  **DYNAMIC_EXCLUDED_POSITIONS** – every top‑row and bottom‑row counter
   (usually unreachable) is excluded so that respawn mechanics, if any,
   will never place items there.
"""




import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from time import time
from typing import Dict, List, Sequence, Tuple
import os
from tqdm.auto import tqdm
from copy import deepcopy

Coordinate = Tuple[int, int]       # (x, y)

# ---------------------------------------------------------------------------

# High‑level recipe spec

# ---------------------------------------------------------------------------

RECIPE_INGREDIENTS: Dict[str, Sequence[str]] = {
    "tomato-salad-food": ["Tomato"],
    "tomato-lettuce-salad-food": ["Tomato", "Lettuce"],
    "tomato-lettuce-onion-salad-food": ["Tomato", "Lettuce", "Onion"],
    "carrot-banana-food": ["Carrot", "Banana"],
    "mashed-carrot-banana-food": ["Carrot", "Banana"],
    "cucumber-onion-food": ["Cucumber", "Onion"],
    "apple-watermelon-food": ["Apple", "Watermelon"],
}

SYMBOL_DICT = {
    "Cutboard": "C",
    "Blender": "B",
    "Deliversquare": "D",
    "Switch": "S",
    "Block": "X",
    "Plate": "P",
    "Tomato": "T",
    "Lettuce": "L",
    "Onion": "O",
    "Carrot": "R",
    "Banana": "A",
    "Cucumber": "U",
    "Apple": "E",
    "Watermelon": "W",
    "Agent": "@",
}

# Static objects that must sit on a counter

COUNTER_OBJECTS = {"Cutboard", "Blender", "Deliversquare"}

# ---------------------------------------------------------------------------

# Helper dataclass

# ---------------------------------------------------------------------------

@dataclass
class PlacementPool:
    """Keeps track of free coordinates for different tile kinds."""
    counters: List[Coordinate] = field(default_factory=list)
    floor: List[Coordinate] = field(default_factory=list)
    excluded: List[Coordinate] = field(default_factory=list)

    def take(self, pool_name: str) -> Coordinate:
        """Pop one coordinate from the requested pool."""
        # need to assert that counter and floor elements are unique in the list
        pool = getattr(self, pool_name, None)
        assert pool is not None, f"Unknown pool: {pool_name}"
        if not pool:
            raise RuntimeError(f"No free {pool_name} tiles left to place object.")
        return pool.pop(random.randrange(len(pool)))

# ---------------------------------------------------------------------------

# Main generator implementation

# ---------------------------------------------------------------------------

class OvercookedJSONMapGenerator:
    """Generate deterministic Overcooked layout JSON."""

    def __init__(
        self,
        width: int,
        height: int,
        num_switch: int,
        num_block: int,
        goal_recipes: Sequence[str],
        map_id: int | str | bytes | bytearray,
    ) -> None:
        if width < 5 or height < 5:
            raise ValueError("Minimum map size is 5×5.")
        if any(r not in RECIPE_INGREDIENTS for r in goal_recipes):
            unknown = {r for r in goal_recipes if r not in RECIPE_INGREDIENTS}
            raise ValueError(f"Unknown recipe tags: {unknown}")

        self.W, self.H = width, height
        self.WALL = "-"
        self.FLOOR = " "
        self.num_switch = num_switch
        self.num_block = num_block
        self.goal_recipes = list(goal_recipes)
        self.map_id = map_id
        random.seed(map_id)  # make everything that follows deterministic

        self.grid = [[" " for _ in range(self.W)] for _ in range(self.H)]
        self.pool = PlacementPool()
        self.static_objects: Dict[str, List[Coordinate]] = defaultdict(list)
        self.dynamic_objects: Dict[str, List[Coordinate]] = defaultdict(list)
        self.agents: List[List[int]] = []  # each element is [x, y]

        self._build_maze()
        self._fill_pools()

    # ------------------------- public entry point ------------------------- #
    def generate(self, save_to: Path | None = None) -> Dict:
        self._place_static_objects()
        self._place_dynamic_objects()
        self._place_agents()

        level_json = {
            "LEVEL_LAYOUT": self._ascii_layout(),
            "STATIC_OBJECTS": self._serialize_objects(self.static_objects),
            "DYNAMIC_OBJECTS": self._serialize_objects(self.dynamic_objects),
            "AGENTS": [
                {"MAX_COUNT": 1, "X_POSITION": [x], "Y_POSITION": [y]}
                for x, y in self.agents
            ],
            "DYNAMIC_EXCLUDED_POSITIONS": self._obtain_excluded_tiles(),
        }

        if save_to:
            save_to.write_text(json.dumps(level_json, indent=2))
        return level_json

    # ------------------------- map construction --------------------------- #
    def _build_maze(self):
        """Depth‑first back‑tracker → perfect maze, then add a few loops."""
        self.grid = [[self.WALL] * self.W for _ in range(self.H)]
        # total number of interior cells (excluding the border)
        total_cells = (self.W - 2) * (self.H - 2)
        threshold = random.uniform(0.9, 1.5)  # random threshold for floor/wall ratio
        # pick a random starting position *inside* the border
        x = random.randrange(1, self.W - 1)
        y = random.randrange(1, self.H - 1)
        self.grid[y][x] = self.FLOOR

        floor_count = 1
        wall_count = total_cells - 1

        # random‐walk until we've carved out enough floors
        pbar = tqdm(desc="Creating maze", total=30, leave=False) # only allow 3.0 seconds for maze carving
        start_time = time()
        cur_time = time()
        while floor_count / wall_count < threshold and cur_time - start_time < 3.0:
            dx, dy = random.choice([(0,1),(0,-1),(1,0),(-1,0)])
            nx, ny = x + dx, y + dy
            # skip moves that hit the border
            if not (1 <= nx < self.W - 1 and 1 <= ny < self.H - 1):
                continue
            x, y = nx, ny
            # carve if it's a wall
            if self.grid[y][x] == self.WALL:
                self.grid[y][x] = self.FLOOR
                floor_count += 1
                wall_count  -= 1
            cur_time_t = time()
            interm_time = cur_time_t - cur_time
            cur_time = cur_time_t
            pbar.update(int(interm_time * 10))
            
        # now add loops
        self._add_loops()
            
        pbar.close()
        # print(f"Carved {floor_count} floors, {wall_count} walls.")
        # print(f"floor/wall ratio: {floor_count / wall_count:.2f}")
        # re-enforce the outer border as walls
        for i in range(self.W):
            self.grid[0][i]          = self.WALL
            self.grid[self.H - 1][i] = self.WALL
        for j in range(self.H):
            self.grid[j][0]          = self.WALL
            self.grid[j][self.W - 1] = self.WALL
                
    def _add_loops(self):
        self.loop_ratio = 0.05  # ratio of walls to convert to floors
        potential = []
        # find walls with floor on opposite sides
        for y in range(1, self.H - 1):
            for x in range(1, self.W - 1):
                if self.grid[y][x] != self.WALL:
                    continue
                # vertical bridge?
                if (
                    self.grid[y - 1][x] == self.FLOOR
                    and self.grid[y + 1][x] == self.FLOOR
                ) or (
                    # horizontal bridge?
                    self.grid[y][x - 1] == self.FLOOR
                    and self.grid[y][x + 1] == self.FLOOR
                ):
                    potential.append((x, y))

        k = max(1, int(self.loop_ratio * len(potential)))
        if len(potential) > 1:
            for x, y in random.sample(potential, k):
                self.grid[y][x] = self.FLOOR
            
    def display_grid(self):
        """Print the grid to the console for debugging."""
        print(self._ascii_layout())
        
    def display_full_map(self):
        full_map = deepcopy(self.grid)
        # replace symbols with letters
        # agent 
        for i, agent in enumerate(self.agents):
            x, y = agent
            full_map[y][x] = SYMBOL_DICT["Agent"]
        # static objects
        for kind, coords in self.static_objects.items():
            for x, y in coords:
                full_map[y][x] = SYMBOL_DICT.get(kind, kind[0].upper())
        # dynamic objects
        for kind, coords in self.dynamic_objects.items():
            for x, y in coords:
                full_map[y][x] = SYMBOL_DICT.get(kind, kind[0].upper())
        # print the full map
        print("\n".join("".join(row) for row in full_map))

    def _fill_pools(self):
        """Collect free coordinates for counters and floor."""
        for y in range(self.H):
            for x in range(self.W):
                ch = self.grid[y][x]
                if ch == "-":
                    self.pool.counters.append((x, y))
                else:  # floor space
                    self.pool.floor.append((x, y))

        # ! calculate excluded positions
        # rule: for each counter, find its 4 corners (x+-1, y+-1), if none of them are floor, add to excluded
        for x, y in self.pool.counters:
            # check 4 corners
            corners = [
                (x - 1, y), (x + 1, y),
                (x, y - 1), (x, y + 1)
            ]
            found_floor = False 
            for corner in corners:
                if corner in self.pool.floor:
                    found_floor = True
                    break

            if not found_floor: # means no floor around this counter
                self.pool.excluded.append((x, y))
                # find the index of this counter in the pool and remove it
                assert (x, y) in self.pool.counters, "Counter not found in pool."
        
        # remove excluded positions from the counters pool
        for x, y in self.pool.excluded:
            if (x, y) in self.pool.counters:
                self.pool.counters.remove((x, y))
        
        random.shuffle(self.pool.counters)
        random.shuffle(self.pool.floor)

    # ----------------------- object placement helpers --------------------- #
    def _place_static_objects(self):
        # Mandatory appliances
        self._add_static("Cutboard", count=1, on_counter=True)
        self._add_static("Blender", count=1, on_counter=True)

        # Deliver squares (randomly pick from len(goal_recipes) to + 2)
        num_ds = max(1, len(self.goal_recipes) + random.randint(0, 2))
        self._add_static("Deliversquare", num_ds, on_counter=True)

        # Switches & blocks on floor
        self._add_static("Switch", self.num_switch, on_counter=False)
        self._add_static("Block", self.num_block, on_counter=False)

    def _place_dynamic_objects(self):
        # Plates
        min_plate = len(self.goal_recipes)
        num_plate = min_plate + random.randint(0, 2) 
        self._add_dynamic("Plate", num_plate, on_counter=True)

        # Ingredients (every recipe completable + one spare per required ingredient)
        need_counts: Dict[str, int] = defaultdict(int)
        for recipe in self.goal_recipes:
            for ing in RECIPE_INGREDIENTS[recipe]:
                need_counts[ing] += 1

        # add a spare copy of each required ingredient
        for ing in list(need_counts):
            need_counts[ing] += random.randint(0, 1) # add 0 or 1 spare

        for ing, cnt in need_counts.items():
            self._add_dynamic(ing, cnt, on_counter=True)

    def _place_agents(self):
        """Put agents.(currently just one)"""
        if not self.pool.floor:
            raise RuntimeError("No floor tiles available to place agents.")
        # Left side
        self.agents.append(list(self.pool.take("floor")))
     

    # -------------------------- low‑level helpers ------------------------- #
    def _add_static(self, kind: str, count: int, *, on_counter: bool):
        pool_name = "counters" if on_counter else "floor"
        for _ in range(count):
            x, y = self.pool.take(pool_name)
            self.static_objects[kind].append([x, y])

    def _add_dynamic(self, kind: str, count: int, *, on_counter: bool):
        pool_name = "counters" if on_counter else "floor"
        for _ in range(count):
            x, y = self.pool.take(pool_name)
            self.dynamic_objects[kind].append([x, y])

    # -------------------------- serialization ----------------------------- #
    @staticmethod
    def _serialize_objects(obj_map: Dict[str, List[Coordinate]]) -> List[Dict]:
        serialized: List[Dict] = []
        for kind, coords in obj_map.items():
            for c in coords:
                serialized.append(
                    {
                        kind: {
                            "COUNT": 1,
                            "X_POSITION": [c[0]],
                            "Y_POSITION": [c[1]],
                        }
                    }
                )
        return serialized

    def _ascii_layout(self) -> str:
        return "\n".join("".join(row) for row in self.grid)

    def _obtain_excluded_tiles(self) -> List[List[int]]:
        """Exclude top & bottom rows where x is a counter column."""
        excluded: List[List[int]] = []
        for x, y in self.pool.excluded:
            excluded.append([x, y])
        return excluded
    
    @staticmethod
    def output_level_dict(level_dict: Dict, output_path: Path) -> None:
        with open(output_path, "w") as f:
            output_str = json.dumps(level_dict, indent=2)
            # replace \n within any [ ] to "" (remove newlines within lists)
            l_list_char_list = [] 
            r_list_char_list = []
            new_output_str = ""
            for character in output_str:
                if character == "[":
                    l_list_char_list.append(character)
                elif character == "]":
                    r_list_char_list.append(character)
                
                if character == "\n":
                    if abs(len(l_list_char_list) - len(r_list_char_list)) <= 1:
                        new_output_str += character
                    else:
                        new_output_str += ""
                else:
                    new_output_str += character
                
            f.write(new_output_str)  # Write to file
# ---------------------------------------------------------------------------

# Convenience script entry point

# ---------------------------------------------------------------------------

if __name__ == "__main__":
    map_id = 42  
    args = dict(
        width=10,
        height=10,
        num_switch=1,
        num_block=2,
        goal_recipes=["carrot-banana-food", "apple-watermelon-food"],
        map_id=42 
    )
    generator = OvercookedJSONMapGenerator(
        **args                   # any hashable seed
    )

    level_dict = generator.generate()        # python dict
    import json, pprint
    generator.display_grid()  # print the grid to console
    generator.display_full_map()  # print the full map to console

    # output to file 
    output_path = Path(os.path.join(os.path.dirname(__file__), f"../level/p{map_id}-overcooked.json"))
    generator.output_level_dict(level_dict, output_path)
    
        
    # import argparse

    # parser = argparse.ArgumentParser(description="Generate Overcooked level JSON.")
    # parser.add_argument("--width", type=int, default=10)
    # parser.add_argument("--height", type=int, default=10)
    # parser.add_argument("--switches", type=int, default=1)
    # parser.add_argument("--blocks", type=int, default=2)
    # parser.add_argument(
    #     "--recipes",
    #     nargs="+",
    #     default=["carrot-banana-food", "apple-watermelon-food"],
    #     help="Goal recipes (space‑separated list).",
    # )
    # parser.add_argument("--map-id", type=int, default=0, help="Random seed.")
    # parser.add_argument("--output", type=Path, help="File to write JSON.")
    # args = parser.parse_args()

    # gen = OvercookedMapGenerator(
    #     width=args.width,
    #     height=args.height,
    #     num_switch=args.switches,
    #     num_block=args.blocks,
    #     goal_recipes=args.recipes,
    #     map_id=args.map_id,
    # )
    # level = gen.generate(save_to=args.output)
    # # Pretty print to stdout if not writing to file
    # if args.output is None:
    #     print(json.dumps(level, indent=2))