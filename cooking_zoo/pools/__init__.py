"""Versioned level pools: generated levels, their PDDL problems and plans, with content hashes.

A pool lives in ``cooking_zoo/pools/<name>/``:

- ``pool.json``: version, generator settings, pool seed, planner, and one entry per level (index, map id,
  recipe, level and problem files with their SHA-256, the PDDL plan and its scheme3 actions), plus the
  rejected candidates and why;
- ``levels/<stem>.json``: the level files (load with ``level=str(path)``);
- ``problems/<stem>.pddl``: the PDDL problem of each level (domain: ``utils/pddl_gen/overcooked.pddl``).

Build or check a pool: ``python -m cooking_zoo.utils.pddl_gen.build_pool --help``.
"""
import hashlib
import json
from pathlib import Path

import gymnasium as gym

POOLS_DIR = Path(__file__).parent
DEFAULT_POOL = "pool50_7x7_v1"
DOMAIN_FILE = POOLS_DIR.parent / "utils" / "pddl_gen" / "overcooked.pddl"

# PDDL food tag -> engine recipe name
RECIPE_NAMES = {
    "tomato-salad-food": "TomatoSalad",
    "tomato-lettuce-salad-food": "TomatoLettuceSalad",
    "tomato-lettuce-onion-salad-food": "TomatoLettuceOnionSalad",
    "carrot-banana-food": "CarrotBanana",
    "mashed-carrot-banana-food": "MashedCarrotBanana",
    "cucumber-onion-food": "CucumberOnion",
    "apple-watermelon-food": "AppleWatermelon",
}

# Plan action direction parameter -> scheme3 action (every domain action is one bump/move in a direction)
DIRECTION_ACTIONS = {"dir-left": 1, "dir-right": 2, "dir-down": 3, "dir-up": 4}

# Settings every pool level is played with (also used for plan replay when building a pool)
ENV_SETTINGS = {
    "meta_file": "example",
    "action_scheme": "scheme3",
    "max_steps": 400,
    "end_condition_all_dishes": True,
}


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pool_dir(name=DEFAULT_POOL):
    return POOLS_DIR / name


def load_pool(root=pool_dir()):
    """The parsed pool.json of the pool in directory `root` (default: DEFAULT_POOL)."""
    return json.loads((Path(root) / "pool.json").read_text())


def level_path(entry, root=pool_dir()):
    return Path(root) / entry["level"]


def verify_pool(root=pool_dir()):
    """One message per level/problem/domain file whose SHA-256 differs from pool.json; empty means verified."""
    pool = load_pool(root)
    failures = []
    if sha256_file(DOMAIN_FILE) != pool["planner"]["domain_sha256"]:
        failures.append(f"hash mismatch: {DOMAIN_FILE.name}")
    for entry in pool["levels"]:
        for key in ("level", "problem"):
            path = Path(root) / entry[key]
            if not path.is_file():
                failures.append(f"missing: {entry[key]}")
            elif sha256_file(path) != entry[f"{key}_sha256"]:
                failures.append(f"hash mismatch: {entry[key]}")
    return failures


def plan_actions(plan):
    """scheme3 actions of a PDDL plan (one action per plan step, from its direction parameter)."""
    actions = []
    for step in plan:
        directions = [token for token in step.strip("()").split() if token.startswith("dir-")]
        if len(directions) != 1:
            raise ValueError(f"plan step without exactly one direction: {step}")
        actions.append(DIRECTION_ACTIONS[directions[0]])
    return actions


def make_env(entry, root=pool_dir(), **kwargs):
    """`cookingEnv-v1` on one level of the pool in `root` with ENV_SETTINGS; keyword arguments add to or
    override them."""
    import cooking_zoo  # noqa: F401  (registers cookingEnv-v1)

    settings = {**ENV_SETTINGS, "obs_spaces": ["symbolic"], **kwargs}
    return gym.make("cookingEnv-v1", level=str(level_path(entry, root)), recipes=[entry["recipe_name"]],
                    disable_env_checker=True, **settings)


def replay(env, actions, seed=0):
    """Reset with `seed`, play `actions` until the episode ends; returns (steps taken, terminated, truncated)."""
    env.reset(seed=seed)
    terminated = truncated = False
    steps = 0
    for action in actions:
        _, _, terminated, truncated, _ = env.step(action)
        steps += 1
        if terminated or truncated:
            break
    return steps, terminated, truncated
