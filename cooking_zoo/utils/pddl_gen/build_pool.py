"""Build, or check, a versioned level pool (see cooking_zoo.pools).

Every level comes from OvercookedJSONMapGenerator with a recorded map id, gets its PDDL problem from
generate_overcooked_pddl and one plan from Fast Downward (`lama-first`, deterministic), and is accepted only
if replaying that plan in the engine completes the recipe within the step limit. Candidates whose map cannot
be generated or that have no plan are rejected and recorded with the reason.

    python -m cooking_zoo.utils.pddl_gen.build_pool --fast-downward <downward>/fast-downward.py
    python -m cooking_zoo.utils.pddl_gen.build_pool --fast-downward <downward>/fast-downward.py --check

--check rebuilds into a temporary directory and exits 1 unless every file equals the committed pool.
"""
import argparse
import filecmp
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

from cooking_zoo.pools import (DOMAIN_FILE, ENV_SETTINGS, RECIPE_NAMES, make_env, plan_actions, pool_dir,
                               replay, sha256_file)
from cooking_zoo.utils.pddl_gen.overcooded_json_map_generator import OvercookedJSONMapGenerator
from cooking_zoo.utils.pddl_gen.pddl_problem_gen import generate_overcooked_pddl

# A level slot whose candidates keep failing points at a generator or domain bug, not at bad luck.
MAX_REJECTIONS_PER_LEVEL = 20


# Versioned pool specifications. A new or changed pool gets a new name; a released spec never changes.
POOL_SPECS = {
    "pool50_7x7_v1": {
        "description": "50 generated 7x7 levels, no switches or blocks, one recipe each, 10 levels per "
                       "recipe; study R0 (ticket #12)",
        "num_levels": 50,
        "pool_seed": 12,
        "generator": {"width": 7, "height": 7, "num_switch": 0, "num_block": 0, "num_recipes": 1},
        # Each recipe appears num_levels / len(recipes) times, in an order shuffled with the pool seed.
        "recipes": ["tomato-salad-food", "tomato-lettuce-salad-food", "tomato-lettuce-onion-salad-food",
                    "carrot-banana-food", "apple-watermelon-food"],
        "planner": {"name": "Fast Downward", "release": "release-26.6.0",
                    "commit": "7ea2755269ff9398279b30f5c848e32ba6047c9c",
                    "alias": "lama-first", "search_time_limit_s": 300},
    },
}


def plan_problem(fast_downward, problem, planner, work_dir):
    """The plan Fast Downward finds for `problem` with the spec's `planner` settings (alias, search time
    limit), as a list of PDDL steps; None if it finds none."""
    plan_file = Path(work_dir) / "sas_plan"
    plan_file.unlink(missing_ok=True)
    result = subprocess.run(
        [sys.executable, str(fast_downward), "--plan-file", str(plan_file), "--alias", planner["alias"],
         "--search-time-limit", str(planner["search_time_limit_s"]), str(DOMAIN_FILE), str(problem)],
        cwd=work_dir, capture_output=True, text=True)
    if result.returncode != 0 or not plan_file.is_file():
        return None
    return [line.strip() for line in plan_file.read_text().splitlines() if line.startswith("(")]


def candidates(spec):
    """(recipe, map id) per level slot: the balanced, shuffled recipe sequence, then fresh map ids per slot."""
    rng = random.Random(spec["pool_seed"])
    recipes = spec["recipes"] * (spec["num_levels"] // len(spec["recipes"]))
    assert len(recipes) == spec["num_levels"], "num_levels must be a multiple of the number of recipes"
    rng.shuffle(recipes)
    used = set()

    def fresh_map_id():
        while (map_id := rng.randrange(2 ** 32)) in used:
            pass
        used.add(map_id)
        return map_id

    return recipes, fresh_map_id


def build(name, fast_downward, out_dir):
    spec = POOL_SPECS[name]
    gen = spec["generator"]
    out_dir = Path(out_dir)
    (out_dir / "levels").mkdir(parents=True, exist_ok=True)
    (out_dir / "problems").mkdir(parents=True, exist_ok=True)
    recipes, fresh_map_id = candidates(spec)
    levels, rejected = [], []
    with tempfile.TemporaryDirectory() as work_dir:
        for index, recipe in enumerate(recipes):
            while True:
                if sum(r["slot"] == index for r in rejected) >= MAX_REJECTIONS_PER_LEVEL:
                    raise RuntimeError(f"level {index} ({recipe}): {MAX_REJECTIONS_PER_LEVEL} candidates rejected")
                map_id = fresh_map_id()
                stem = f"p{map_id}-overcooked"
                try:
                    generator = OvercookedJSONMapGenerator(
                        width=gen["width"], height=gen["height"], num_switch=gen["num_switch"],
                        num_block=gen["num_block"], goal_recipes=[recipe], map_id=map_id)
                    level = generator.generate()
                except RuntimeError as error:
                    rejected.append({"slot": index, "map_id": map_id, "recipe": recipe,
                                     "reason": f"generator: {error}"})
                    print(f"{index:2d} {stem} {recipe}: rejected, {rejected[-1]['reason']}", flush=True)
                    continue
                level_file = out_dir / "levels" / f"{stem}.json"
                generator.output_level_dict(level, level_file)
                problem_file = out_dir / "problems" / f"{stem}.pddl"
                problem_file.write_text(generate_overcooked_pddl(level, problem_name=stem, goal_clauses=[recipe]))
                plan = plan_problem(fast_downward, problem_file, spec["planner"], work_dir)
                if plan is None:
                    level_file.unlink()
                    problem_file.unlink()
                    rejected.append({"slot": index, "map_id": map_id, "recipe": recipe,
                                     "reason": "planner: no plan"})
                    print(f"{index:2d} {stem} {recipe}: rejected, {rejected[-1]['reason']}", flush=True)
                    continue
                break
            actions = plan_actions(plan)
            entry = {
                "index": index, "name": stem, "map_id": map_id, "recipe": recipe,
                "recipe_name": RECIPE_NAMES[recipe],
                "level": f"levels/{stem}.json", "level_sha256": sha256_file(level_file),
                "problem": f"problems/{stem}.pddl", "problem_sha256": sha256_file(problem_file),
                "plan": plan, "actions": actions, "plan_length": len(actions),
            }
            steps, terminated, truncated = replay(make_env(entry, out_dir), actions)
            if not (terminated and not truncated and steps == len(actions)):
                raise RuntimeError(f"plan of {stem} does not complete its recipe in the engine "
                                   f"(steps {steps}, terminated {terminated}, truncated {truncated})")
            levels.append(entry)
            print(f"{index:2d} {stem} {recipe}: plan {len(actions)} steps", flush=True)

    pool = {
        "name": name,
        "description": spec["description"],
        "num_levels": spec["num_levels"],
        "pool_seed": spec["pool_seed"],
        "generator": {**gen, "module": "cooking_zoo.utils.pddl_gen.overcooded_json_map_generator",
                      "max_carve_steps": OvercookedJSONMapGenerator.MAX_CARVE_STEPS},
        "recipes": spec["recipes"],
        "planner": {**spec["planner"], "domain": "cooking_zoo/utils/pddl_gen/overcooked.pddl",
                    "domain_sha256": sha256_file(DOMAIN_FILE)},
        "env_settings": ENV_SETTINGS,
        "levels": levels,
        "rejected": rejected,
    }
    (out_dir / "pool.json").write_text(json.dumps(pool, indent=1) + "\n")
    return pool


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m cooking_zoo.utils.pddl_gen.build_pool", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pool", default="pool50_7x7_v1", choices=sorted(POOL_SPECS))
    parser.add_argument("--fast-downward", type=Path, required=True, help="path to fast-downward.py")
    parser.add_argument("--check", action="store_true", help="rebuild into a temporary directory and compare")
    args = parser.parse_args(argv)
    if not args.check:
        build(args.pool, args.fast_downward.resolve(), pool_dir(args.pool))
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        build(args.pool, args.fast_downward.resolve(), tmp)
        committed, rebuilt = pool_dir(args.pool), Path(tmp)
        files = sorted(str(p.relative_to(rebuilt)) for p in rebuilt.rglob("*") if p.is_file())
        expected = sorted(str(p.relative_to(committed)) for p in committed.rglob("*") if p.is_file())
        differ = [f for f in files if f in expected and not filecmp.cmp(committed / f, rebuilt / f, shallow=False)]
        print(f"rebuilt {len(files)} files; missing in committed pool: {sorted(set(files) - set(expected))}; "
              f"extra in committed pool: {sorted(set(expected) - set(files))}; differ: {differ}")
        return 0 if files == expected and not differ else 1


if __name__ == "__main__":
    sys.exit(main())
