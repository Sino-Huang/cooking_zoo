"""The shipped pool (cooking_zoo/pools/pool50_7x7_v1): contents, hashes, reproducibility and V12 (engine part)."""
import json
from collections import Counter

import pytest

from cooking_zoo.pools import (DEFAULT_POOL, ENV_SETTINGS, RECIPE_NAMES, level_path, load_pool, make_env,
                               plan_actions, pool_dir, replay, verify_pool)
from cooking_zoo.utils.pddl_gen.overcooded_json_map_generator import OvercookedJSONMapGenerator
from cooking_zoo.utils.pddl_gen.pddl_problem_gen import generate_overcooked_pddl
from conftest import layout

POOL = load_pool()
LEVELS = POOL["levels"]
ALLOWED_RECIPES = {"tomato-salad-food", "tomato-lettuce-salad-food", "tomato-lettuce-onion-salad-food",
                   "carrot-banana-food", "apple-watermelon-food"}
STEP_LIMIT = 400


def test_pool_files_match_their_recorded_hashes():
    assert verify_pool() == []
    files = {p.relative_to(pool_dir()).as_posix() for p in pool_dir().rglob("*") if p.is_file()}
    assert files == {"pool.json"} | {e["level"] for e in LEVELS} | {e["problem"] for e in LEVELS}


def test_pool_has_fifty_7x7_levels_without_switches_or_blocks():
    assert POOL["name"] == DEFAULT_POOL and len(LEVELS) == POOL["num_levels"] == 50
    assert [e["index"] for e in LEVELS] == list(range(50))
    assert len({e["map_id"] for e in LEVELS}) == 50
    assert POOL["generator"]["num_switch"] == 0 and POOL["generator"]["num_block"] == 0
    for entry in LEVELS:
        level = json.loads(level_path(entry).read_text())
        rows = level["LEVEL_LAYOUT"].splitlines()
        assert len(rows) == 7 and all(len(row) == 7 for row in rows)
        names = {list(obj)[0] for obj in level["STATIC_OBJECTS"] + level["DYNAMIC_OBJECTS"]}
        assert not names & {"Switch", "Block"}
        assert len(level["AGENTS"]) == 1


def test_each_level_has_one_allowed_recipe_and_the_recipes_are_balanced():
    assert set(POOL["recipes"]) == ALLOWED_RECIPES
    assert Counter(e["recipe"] for e in LEVELS) == {recipe: 10 for recipe in ALLOWED_RECIPES}
    assert all(e["recipe_name"] == RECIPE_NAMES[e["recipe"]] for e in LEVELS)


def test_levels_and_problems_regenerate_from_the_recorded_settings_and_seeds(tmp_path):
    gen = POOL["generator"]
    assert gen["max_carve_steps"] == OvercookedJSONMapGenerator.MAX_CARVE_STEPS
    for entry in LEVELS:
        generator = OvercookedJSONMapGenerator(width=gen["width"], height=gen["height"],
                                               num_switch=gen["num_switch"], num_block=gen["num_block"],
                                               goal_recipes=[entry["recipe"]], map_id=entry["map_id"])
        level = generator.generate()
        generator.output_level_dict(level, tmp_path / "level.json")
        assert (tmp_path / "level.json").read_bytes() == level_path(entry).read_bytes()
        problem = generate_overcooked_pddl(level, problem_name=entry["name"], goal_clauses=[entry["recipe"]])
        assert problem == (pool_dir() / entry["problem"]).read_text()


def test_recorded_actions_are_the_plans_directions():
    for entry in LEVELS:
        assert entry["actions"] == plan_actions(entry["plan"])
        assert entry["plan_length"] == len(entry["plan"]) <= STEP_LIMIT
        assert entry["plan"][-1].startswith("(serve-food ")


def test_pool_env_settings_are_the_study_settings():
    assert POOL["env_settings"] == ENV_SETTINGS
    assert ENV_SETTINGS["max_steps"] == STEP_LIMIT and ENV_SETTINGS["action_scheme"] == "scheme3"


# --- V12, engine part -----------------------------------------------------------------------------

@pytest.mark.parametrize("entry", LEVELS, ids=[e["name"] for e in LEVELS])
def test_v12_every_pddl_plan_reaches_success_within_400_steps(entry):
    env = make_env(entry)
    steps, terminated, truncated = replay(env, entry["actions"])
    recipe = env.unwrapped.zoo_env.unwrapped.recipe_graphs[0]
    assert terminated and not truncated and recipe.completed()
    assert steps == entry["plan_length"] <= STEP_LIMIT


@pytest.mark.parametrize("entry", LEVELS, ids=[e["name"] for e in LEVELS])
def test_v12_truncation_happens_at_400_steps(entry):
    env = make_env(entry)
    env.reset(seed=0)
    for t in range(1, STEP_LIMIT + 1):
        _, _, terminated, truncated, _ = env.step(0)
        assert not terminated
        assert truncated == (t == STEP_LIMIT)


def test_v12_same_seed_gives_the_same_layout_on_every_level():
    for entry in LEVELS:
        env = make_env(entry)
        env.reset(seed=1)
        first = layout(env)
        env.reset(seed=1)
        assert layout(env) == first
        env.reset(seed=2)  # generated levels place every object at one position
        assert layout(env) == first



def test_every_level_renders_at_16_px_per_tile():
    for entry in LEVELS:
        env = make_env(entry, render_mode="rgb_array", tile_size=16)
        env.reset(seed=0)
        assert env.render().shape == (112, 112, 3)