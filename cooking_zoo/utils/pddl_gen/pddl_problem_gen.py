from __future__ import annotations
import itertools, json
from pathlib import Path
from typing import Dict, List, Tuple, Sequence, Iterable
import os 
from collections import Counter
import itertools
import argparse

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
    loc_name            = lambda x, y: f"pos-{x}-{y}"

    # all grid points ---------------------------------------------------------
    walls   = {(x, y)
               for y,row in enumerate(layout_rows)
               for x,ch in enumerate(row) if ch == WALL_CHAR}
    floors  = {(x, y) for y in range(height)
                       for x in range(width)} - walls

    # ---------------------------------------------------------------- objects
    # nms is the running counter for unique object names
    nms, objs_by_type = {}, {   # running counters for uniq()
        # "direction"   : [], # comment out as they are constant
        "location"    : [],
        # "agent"       : [],  # comment out as they are constant
        "cutboard"    : [],
        "blender"     : [],
        "switch"      : [],
        "deliversquare"    : [],
        "block"       : [],
        "counter"     : [],      # plain counter (wall) tiles
        "item"        : [],      # plates & ingredients
    }

    # # 4 static direction symbols ---------------------------------------------
    # for d in ("dir-up", "dir-down", "dir-left", "dir-right"):
    #     objs_by_type["direction"].append(d)

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
        "Deliversquare" : "deliversquare",
        "Block"         : "block"
    }

    # instantiate and remember where each station lives
    station_at : dict[str, Tuple[int,int]] = {}
    for obj_desc in level["STATIC_OBJECTS"]:
        name     = next(iter(obj_desc))
        spec     = obj_desc[name]
        for (x, y) in _extract_positions(spec):
            inst = _uniq(name.lower(), nms)
            # special case for switch and block
            if not (name in ['Switch', 'Block']):
                objs_by_type[STATIC_KIND[name]].append(inst)
            station_at[inst] = (x, y)


    
    # ---------------------------------------------------------------- dynamic items
    ITEM_TYPES = {"Plate", "Lettuce", "Tomato", "Banana", "Apple",
                  "Watermelon", "Bread", "Carrot"}

    # Add items like plate, ingredients, etc.
    item_at : dict[str, Tuple[int,int]] = {} # item location
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
            if name.lower() not in objs_by_type:
                objs_by_type[name.lower()] = []
            objs_by_type[name.lower()].append(inst)
            item_at[inst] = (x, y)

    

    
    
    # ---------------------------------------------------------------- agents
    agent_at : dict[str, Tuple[int,int]] = {}
    agent_count = 0 
    for obj_desc in level["AGENTS"]:
        agent_count += 1
        if agent_count > 1:  # currently only support 1 agent
            break
        max_cnt = obj_desc["MAX_COUNT"]
        assert max_cnt == 1, "Only one agent per type is supported in PDDL generation"
        xs, ys  = obj_desc["X_POSITION"], obj_desc["Y_POSITION"]
        for (x, y) in itertools.islice(itertools.product(xs, ys), max_cnt):
            inst = _uniq("agent", nms) 
            # objs_by_type["agent"].append(inst) # comment out as agent will be constant
            agent_at[inst] = (x, y)

    assert len(agent_at) == 1, "Only one agent is supported in PDDL generation"
    # ---------------------------------------------------------------- :objects
    def _dump_obj_block() -> str:
        return "\n        ".join(
            f"{' '.join(sorted(v))} - {k}"
            for k, v in objs_by_type.items() if v
        )

    # ---------------------------------------------------------------- :init
    init_lines : list[str] = []

    static_inits_str = """;; How many quantities when chopping
(quantity-after-chop onion-type num1)
(quantity-after-chop tomato-type num1)
(quantity-after-chop lettuce-type num1)
(quantity-after-chop cucumber-type num1)
(quantity-after-chop apple-type num1)
(quantity-after-chop watermelon-type num1)
(quantity-after-chop bread-type num2)
(quantity-after-chop carrot-type num1)
(quantity-after-chop banana-type num1)
;; numeric successor relation for numbers
(succ num0 num1)
(succ num1 num2)
(succ num2 num3)
(succ num3 num4)
"""
    static_init_splits = static_inits_str.splitlines()
    init_lines.extend(static_init_splits)
    
    # Also assign 'has-type object object-type' facts for each item
    type_type_dict = {
        'lettuce': 'lettuce-type',
        'tomato': 'tomato-type',
        'banana': 'banana-type',
        'apple': 'apple-type',
        'watermelon': 'watermelon-type',
        'bread': 'bread-type',
        'carrot': 'carrot-type',
    }
    init_lines.append(";; type information for items")
    for item, (x, y) in item_at.items():
        item_type = item.split('-')[0]
        if item_type in type_type_dict:
            init_lines.append(f"(has-type {item} {type_type_dict[item_type]})")
            
    init_lines.append(";; init cutboard and blender states -- empty at the start")
    # for each cutboard, set (chopped-food-count cutboard num0) as init 
    # (i.e. no food chopped yet)
    for cutboard in objs_by_type["cutboard"]:
        init_lines.append(f"(chopped-food-count {cutboard} num0)")
    # for each blender, set (smashed-food-count blender num0) as init
    for blender in objs_by_type["blender"]:
        init_lines.append(f"(smashed-food-count {blender} num0)")
        
    # for each plate, set (plate-ingredient-count plate num0) as init
    for plate in objs_by_type["plate"]:
        init_lines.append(f"(plate-ingredient-count {plate} num0)")
    
    # positions of counters and floors ----------------------------------------
    #   (occupied? clear? passable?)  – simplest approach:
    init_lines.append(";; location facts")
    for (x, y) in floors:
        # check if (x, y) is occupied by agent 
        if not ((x, y) in agent_at.values()):
            init_lines.append(f"(clear {loc_name(x, y)})")

    # location of counters tiles ---------------------------------------------
    for counter_name, (x,y) in zip(objs_by_type["counter"], walls):
        init_lines.append(f"(on {counter_name} {loc_name(x, y)})")

    # static stations ---------------------------------------------------------
    for inst, (x, y) in station_at.items():
        
        # * special case for block
        if "block" in inst:
            init_lines.append(f"(is-block {loc_name(x, y)})")
            init_lines.append(f"(block-on {loc_name(x, y)})")
        # * special case for switch 
        elif "switch" in inst:
            init_lines.append(f"(is-switch {loc_name(x, y)})") 
            init_lines.append(f"(switch-on {loc_name(x, y)})")
        else:
            init_lines.append(f"(on {inst} {loc_name(x, y)})")
        
       

    # items (plates, ingredients) -------------------------------------------------------------------
    for inst, (x, y) in item_at.items():
        init_lines.append(f"(at {inst} {loc_name(x, y)})")

    # agents ------------------------------------------------------------------
    for inst, (x, y) in agent_at.items():
        init_lines.append(f"(at {inst} {loc_name(x, y)})")
        # add hand empty 
        init_lines.append(f"(handempty {inst})")


    # directional adjacency facts --------------------------------------------
    init_lines.append(";; directional adjacency facts")
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
    goal_sec = ""

    if goal_clauses:
        clause_counts = Counter(goal_clauses)

        for clause, count in clause_counts.items():
            if count > 1:
                # Generate N variables: ?pl0, ?pl1, ..., ?plN-1
                vars_list = [f"?pl{i}" for i in range(count)]
                vars_str = " ".join(vars_list) + " - plate"

                # Served clauses
                served_clauses = [f"          (served {var} {clause})" for var in vars_list]

                # Inequality constraints: all combinations of vars where i < j
                inequality_clauses = [
                    f"          (not (= {a} {b}))"
                    for a, b in itertools.combinations(vars_list, 2)
                ]

                # Combine all
                inner_and_body = "\n".join(served_clauses + inequality_clauses)

                completed_clause = f"""(exists ({vars_str})
    (and 
{inner_and_body}
    )
)"""
            else:
                completed_clause = f"""(exists (?pl - plate)
    (served ?pl {clause})
)"""

            # Indent nicely
            for line in completed_clause.splitlines():
                goal_sec += "        " + line + "\n"

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
    (and
{goal_sec}
    )
  )
)"""
    return problem_str


if __name__ == "__main__":
    # e.g., ./pddl_problem_gen.py --goal_clauses tomato-salad1 tomato-salad2 tomato-salad3
    parser = argparse.ArgumentParser(description="Generate PDDL problem file for Overcooked level")
    parser.add_argument("--path", type=str, default="/home/sukai/Project/granularity_instruction_nsai/granularity-instruction-nsai/data/00_envs/cooking_zoo/cooking_zoo/utils/level/larger_level_test.json",
                        help="Path to the level specification JSON file")
    parser.add_argument("--problem_id", type=str, default="p001")
    parser.add_argument("--goal_clauses", type=str, nargs='*', default=["tomato-salad-food", "tomato-salad-food"],)
    
    args = parser.parse_args()
    level_spec_path = Path(args.path)
    problem_id = args.problem_id
    goal_clauses = args.goal_clauses
    problem_name = f"{problem_id}-overcooked"
    
    if not level_spec_path.exists():
        raise FileNotFoundError(f"Level specification file not found: {level_spec_path}")
                        
    level = json.loads(level_spec_path.read_text())

    # 2.  Produce the PDDL.  Add your own goal clauses that match the domain.
    pddl = generate_overcooked_pddl(
                level,
                problem_name=problem_name,
                goal_clauses= goal_clauses,
            )

    # 3.  Write to disk, hand over to your favourite planner.
    
    output_path = os.path.join(os.path.dirname(__file__), f"{problem_name}.pddl")
    
    Path(output_path).write_text(pddl)