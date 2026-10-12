"""Shared helpers for the cooking_zoo engine tests (run: python -m pytest tests from the repo root)."""
import contextlib
import json
import signal
from pathlib import Path

import gymnasium as gym
import pytest

import cooking_zoo  # noqa: F401  (registers cookingEnv-v1)

LEVELS = Path(__file__).parent / "levels"
REWARD_SCHEME = {"recipe_reward": 20, "max_time_penalty": -5, "recipe_penalty": -40, "recipe_node_reward": 0}

# Scripted scheme3 solution of tests/levels/tomato_salad.json (TomatoSalad): fetch the tomato, chop it,
# collect it, put it on the plate, pick the plate up and deliver it.
TOMATO_SALAD_SOLUTION = (
    [2, 2, 2]  # walk right twice, bump the tomato counter: pick up the tomato
    + [1, 1, 1, 1, 1]  # walk left four times, bump the cutboard: put the tomato down
    + [1]  # bump the cutboard again: chop
    + [1]  # bump once more: pick up the chopped tomato
    + [2, 2, 4, 4, 4]  # walk to (3, 1), bump the plate counter: tomato onto the plate
    + [4]  # bump again: pick up the plate
    + [3, 3, 3, 3, 3]  # walk down to (3, 5), bump the delivery square: deliver
)


def make_env(level, recipes, max_steps=400, **kwargs):
    return gym.make(
        "cookingEnv-v1",
        level=str(level),
        meta_file="example",
        max_steps=max_steps,
        recipes=recipes,
        obs_spaces=["symbolic"],
        action_scheme="scheme3",
        reward_scheme=REWARD_SCHEME,
        disable_env_checker=True,
        **kwargs,
    )


def core(env):
    """The PettingZoo CookingEnvironment behind the gym wrapper."""
    return env.unwrapped.zoo_env.unwrapped


def layout(env):
    """Engine layout: every object's type and location plus each agent's location and orientation."""
    world = core(env).world
    objects = sorted((type(obj).__name__, tuple(obj.location)) for obj in world.get_object_list())
    agents = [(tuple(agent.location), agent.orientation) for agent in world.agents]
    return objects, agents


@contextlib.contextmanager
def deadline(seconds):
    """Fail instead of hanging: raise TimeoutError if the block runs longer than `seconds`."""
    def _raise(signum, frame):
        raise TimeoutError(f"no return within {seconds} s")

    previous = signal.signal(signal.SIGALRM, _raise)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


@pytest.fixture
def tmp_level(tmp_path):
    def write(level_dict, name="level.json"):
        path = tmp_path / name
        path.write_text(json.dumps(level_dict))
        return path
    return write
