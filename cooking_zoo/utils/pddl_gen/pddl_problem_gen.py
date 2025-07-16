from __future__ import annotations
import itertools, json
from pathlib import Path
from typing import Dict, List, Tuple, Sequence, Iterable
import os 

###############################################################################
# Utility for producing unique object names
###############################################################################
def _uniq(prefix: str, counter: Dict[str, int]) -> str:
    counter[prefix] = counter.get(prefix, 0) + 1
    return f"{prefix}-{counter[prefix]:02d}"

###############################################################################
# Main converter
###############################################################################
def generate_overcooked_pddl(level: Dict,
                             *,
                             problem_name: str = "overcooked-instance",
                             domain_name : str = "overcooked",
                             goal_clauses : Sequence[str] | None = None
                             ) -> str:
    """
    Convert an Overcooked JSON level (after Cooking‑Zoo's randomisation) into
    a fully‑instantiated PDDL problem file.
    --------------------------------------------------------------------------
    Parameters
    ----------
    level          : the already‑*sampled* level dictionary, i.e. the one that
                     your runtime parser actually used for building the world
                     (so that COUNT/OPTIONAL have been resolved).
    problem_name   : the name that appears in (define (problem …)).
    domain_name    : the PDDL domain this problem should refer to.
    goal_clauses   : list of **ground** predicate strings, e.g.
                     ['(served salad‑01)', '(served smoothie‑01)'].
                     They will be wrapped inside the (:goal (and …)) section.
                     If None (default) a dummy tautology is inserted.
    """
    # ---------------------------------------------------------------- layout --
    layout_rows         = level["LEVEL_LAYOUT"].splitlines()
    height, width       = len(layout_rows), max(len(r) for r in layout_rows)
    WALL_CHAR           = '-'                       # counter tiles
    loc_name            = lambda x, y: f"pos-{x+1}-{y+1}"

    # all grid points ---------------------------------------------------------
    walls   = {(x, y)
               for y,row in enumerate(layout_rows)
               for x,ch in enumerate(row) if ch == WALL_CHAR}
    floors  = {(x, y) for y in range(height)
                       for x in range(width)} - walls

    # ---------------------------------------------------------------- objects
    nms, objs_by_type = {}, {   # running counters for uniq()
        "direction"   : [],
        "location"    : [],
        "agent"       : [],
        "cutboard"    : [],
        "blender"     : [],
        "switch"      : [],
        "delivery"    : [],
        "block"       : [],
        "counter"     : [],      # plain counter (wall) tiles
        "item"        : [],      # plates & ingredients
    }

    # 4 static direction symbols ---------------------------------------------
    for d in ("dir-up", "dir-down", "dir-left", "dir-right"):
        objs_by_type["direction"].append(d)

    # every grid coord is a location object -----------------------------------
    for (x, y) in itertools.product(range(width), range(height)):
        objs_by_type["location"].append(loc_name(x, y))

    # plain counters (= Overcooked walls) -------------------------------------
    for _ in walls:
        objs_by_type["counter"].append(_uniq("counter", nms))

    # ---------------------------------------------------------------- static stations
    # helper to find concrete (x,y) tuples for each static object *after* the
    # cooking_zoo random placement
    def _extract_positions(spec: Dict) -> Iterable[Tuple[int,int]]:
        xs = spec["X_POSITION"]
        ys = spec["Y_POSITION"]
        # The runtime parser random‑samples one coordinate for each COUNT,
        # so we mimic the simplest deterministic choice: zip the first N.
        for x, y in itertools.islice(itertools.product(xs, ys), spec["COUNT"]):
            yield int(x), int(y)

    # mapping from JSON symbol to our PDDL type bucket
    STATIC_KIND = {
        "Cutboard"      : "cutboard",
        "Blender"       : "blender",
        "Switch"        : "switch",
        "Deliversquare" : "delivery",
        "Block"         : "block"
    }

    # instantiate and remember where each station lives
    station_at : dict[str, Tuple[int,int]] = {}
    for obj_desc in level["STATIC_OBJECTS"]:
        name     = next(iter(obj_desc))
        spec     = obj_desc[name]
        for (x, y) in _extract_positions(spec):
            inst = _uniq(name.lower(), nms)
            objs_by_type[STATIC_KIND[name]].append(inst)
            station_at[inst] = (x, y)

    # for each cutboard, set (chopped-food-count cutboard num0) as init 
    # (i.e. no food chopped yet)
    # TODO need to confirm this is correct
    for cutboard in objs_by_type["cutboard"]:
        objs_by_type["block"].append(f"(chopped-food-count {cutboard} num0)")
    # for each blender, set (smashed-food-count blender num0) as init
    for blender in objs_by_type["blender"]:
        objs_by_type["block"].append(f"(smashed-food-count {blender} num0)")
    # for each switch, set (is-switch location) as init
    for switch in objs_by_type["switch"]:
        objs_by_type["block"].append(f"(is-switch {switch})")
        objs_by_type["block"].append(f"switch-on {switch}")  
    
    # ---------------------------------------------------------------- dynamic items
    ITEM_TYPES = {"Plate", "Lettuce", "Tomato", "Banana", "Apple",
                  "Watermelon", "Bread", "Carrot"}

    item_at : dict[str, Tuple[int,int]] = {}
    for obj_desc in level["DYNAMIC_OBJECTS"]:
        name = next(iter(obj_desc))
        spec = obj_desc[name]

        # skip optional items that the runtime may have *not* created
        count = spec["COUNT"]
        prob  = spec.get("OPTIONAL", 1.0)
        real_count = count if prob >= 1.0 else round(count * prob)

        for idx, (x, y) in enumerate(_extract_positions(spec)):
            if idx >= real_count:
                break
            inst = _uniq(name.lower(), nms)
            objs_by_type["item"].append(inst)
            item_at[inst] = (x, y)

    # Also assign 'has-type object object-type' facts for each item
    type_type_dict = {
        'lettuce': 'lettuce-type',
        'tomato': 'tomato-type',
        'banana': 'banana-type',
        'apple': 'apple-type',
        'watermelon': 'watermelon-type',
        'bread': 'bread-type',
        'carrot': 'carrot-type',
        'plate': 'plate-type'
    }
    
    for item, (x, y) in item_at.items():
        item_type = item.split('-')[0]
        if item_type in type_type_dict:
            objs_by_type["item"].append(f"has-type {item} {type_type_dict[item_type]}")

    
    
    # ---------------------------------------------------------------- agents
    agent_at : dict[str, Tuple[int,int]] = {}
    for obj_desc in level["AGENTS"]:
        max_cnt = obj_desc["MAX_COUNT"]
        xs, ys  = obj_desc["X_POSITION"], obj_desc["Y_POSITION"]
        for (x, y) in itertools.islice(itertools.product(xs, ys), max_cnt):
            inst = _uniq("agent", nms)
            objs_by_type["agent"].append(inst)
            agent_at[inst] = (x, y)

    # ---------------------------------------------------------------- :objects
    def _dump_obj_block() -> str:
        return "\n        ".join(
            f"{' '.join(sorted(v))} - {k}"
            for k, v in objs_by_type.items() if v
        )

    # ---------------------------------------------------------------- :init
    init_lines : list[str] = []

    static_inits_str = """(quantity-after-chop onion-type num1)
(quantity-after-chop tomato-type num1)
(quantity-after-chop lettuce-type num1)
(quantity-after-chop cucumber-type num1)
(quantity-after-chop apple-type num1)
(quantity-after-chop watermelon-type num1)
(quantity-after-chop bread-type num2)
(quantity-after-chop carrot-type num1)
(quantity-after-chop banana-type num1)
"""
    static_init_splits = static_inits_str.splitlines()
    init_lines.extend(static_init_splits)
    
    # positions of counters and floors ----------------------------------------
    #   (occupied? clear? passable?)  – simplest approach:
    for (x, y) in floors:
        init_lines.append(f"(clear {loc_name(x, y)})")

    # location of counters tiles ---------------------------------------------
    for counter_name, (x,y) in zip(objs_by_type["counter"], walls):
        init_lines.append(f"(at {counter_name} {loc_name(x, y)})")

    # static stations ---------------------------------------------------------
    for inst, (x, y) in station_at.items():
        init_lines.append(f"(at {inst} {loc_name(x, y)})")

    # items -------------------------------------------------------------------
    for inst, (x, y) in item_at.items():
        init_lines.append(f"(at {inst} {loc_name(x, y)})")

    # agents ------------------------------------------------------------------
    for inst, (x, y) in agent_at.items():
        init_lines.append(f"(at {inst} {loc_name(x, y)})")


    # directional adjacency facts --------------------------------------------
    DIRS = {"dir-left":(-1,0), "dir-right":(1,0),
            "dir-up":(0,-1),   "dir-down":(0,1)}
    passable = list(floors) + list(walls)         # agents can stand on floor (and delivery etc.)
    for (x, y) in passable:
        for d_name, (dx, dy) in DIRS.items():
            nx, ny = x+dx, y+dy
            if (nx, ny) in passable:
                init_lines.append(
                    f"(move-dir {loc_name(x, y)} {loc_name(nx, ny)} {d_name})"
                )

    # ---------------------------------------------------------------- :goal
    if goal_clauses:
        goal_sec = "\n            ".join(goal_clauses)
    else:                       # default “do‑nothing” goal
        goal_sec = "(true)"

    # ---------------------------------------------------------------- render
    indent_join = lambda seq: "\n        ".join(seq)
    problem_str = f"""(define (problem {problem_name})
  (:domain {domain_name})

  (:objects
        { _dump_obj_block() }
  )

  (:init
        { indent_join(init_lines) }
  )

  (:goal
        {goal_sec}
  )
)"""
    return problem_str


if __name__ == "__main__":
    # 1.  Sample the level exactly once with your cooking_zoo parser so that every
    #     OPTIONAL object is either present or absent.
    level_spec_path = Path("/home/sukai/Project/granularity_instruction_nsai/granularity-instruction-nsai/data/00_envs/cooking_zoo/cooking_zoo/utils/level/larger_level_test.json")          # uploaded file
    level = json.loads(level_spec_path.read_text())

    # 2.  Produce the PDDL.  Add your own goal clauses that match the domain.
    pddl = generate_overcooked_pddl(
                level,
                problem_name="p001-overcooked",
                goal_clauses=["(served salad-01)", "(served smoothie-01)"]
            )

    # 3.  Write to disk, hand over to your favourite planner.
    
    output_path = os.path.join(os.path.dirname(__file__), "p001-overcooked.pddl")
    
    Path(output_path).write_text(pddl)