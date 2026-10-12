"""Engine fixes: success termination, per-environment seeding, rgb_array render, Cucumber."""
import json
import random

import numpy as np
import pytest

from cooking_zoo.environment.cooking_env import CookingEnvironment
from conftest import LEVELS, TOMATO_SALAD_SOLUTION, core, deadline, layout, make_env


def play(env, actions):
    steps = []
    for action in actions:
        with deadline(10):
            obs, reward, terminated, truncated, info = env.step(action)
        steps.append((reward, terminated, truncated))
        if terminated or truncated:
            break
    return steps


# --- success termination -------------------------------------------------------------------------

def test_success_terminates_and_returns():
    env = make_env(LEVELS / "tomato_salad.json", ["TomatoSalad"])
    env.reset(seed=0)
    steps = play(env, TOMATO_SALAD_SOLUTION)
    assert len(steps) == len(TOMATO_SALAD_SOLUTION)
    assert [s[1] for s in steps] == [False] * (len(steps) - 1) + [True]
    assert not any(s[2] for s in steps)
    assert steps[-1][0] == pytest.approx(20 - 5 / 400)
    assert core(env).recipe_graphs[0].completed()
    assert env.unwrapped.zoo_env.agents == []


def test_episode_after_success_resets_cleanly():
    env = make_env(LEVELS / "tomato_salad.json", ["TomatoSalad"])
    for _ in range(2):
        env.reset(seed=0)
        steps = play(env, TOMATO_SALAD_SOLUTION)
        assert steps[-1][1] and len(steps) == len(TOMATO_SALAD_SOLUTION)


# --- truncation ----------------------------------------------------------------------------------

def test_truncation_happens_exactly_at_max_steps():
    env = make_env(LEVELS / "tomato_salad.json", ["TomatoSalad"], max_steps=400)
    env.reset(seed=0)
    steps = play(env, [0] * 401)
    assert len(steps) == 400
    assert [s[2] for s in steps] == [False] * 399 + [True]
    assert not any(s[1] for s in steps)


def test_success_on_the_last_step_is_termination():
    solution = TOMATO_SALAD_SOLUTION
    env = make_env(LEVELS / "tomato_salad.json", ["TomatoSalad"], max_steps=len(solution))
    env.reset(seed=0)
    steps = play(env, solution)
    assert len(steps) == len(solution)
    assert steps[-1][1]


# --- seeding -------------------------------------------------------------------------------------

def layouts_for(seeds, level="stochastic.json"):
    env = make_env(LEVELS / level, ["TomatoSalad"])
    out = []
    for seed in seeds:
        env.reset(seed=seed)
        out.append(layout(env))
    return out


def test_same_seed_gives_the_same_layout():
    first = layouts_for(range(10))
    random.seed(12345)
    np.random.seed(12345)
    second = layouts_for(range(10))  # other env instance, other global RNG state
    assert first == second


def test_different_seeds_give_different_layouts():
    distinct = {repr(item) for item in layouts_for(range(20))}
    assert len(distinct) > 10


def test_seeding_leaves_the_global_rngs_alone():
    random.seed(7)
    np.random.seed(7)
    py_state, np_state = random.getstate(), np.random.get_state()
    layouts_for(range(3))
    np_after = np.random.get_state()
    assert random.getstate() == py_state
    assert np.array_equal(np_after[1], np_state[1]) and np_after[2] == np_state[2]


def test_unseeded_resets_continue_the_seeded_stream():
    env = make_env(LEVELS / "stochastic.json", ["TomatoSalad"])
    env.reset(seed=3)
    sequence = [layout(env)]
    for _ in range(4):
        env.reset()
        sequence.append(layout(env))
    again = make_env(LEVELS / "stochastic.json", ["TomatoSalad"])
    again.reset(seed=3)
    replay = [layout(again)]
    for _ in range(4):
        again.reset()
        replay.append(layout(again))
    assert sequence == replay
    assert len({repr(item) for item in sequence}) > 1


def spawn_trace(level, seed):
    """Agent despawn/respawn decisions and respawn locations over 30 world ticks."""
    env = CookingEnvironment(str(level), "example", 2, 50, ["TomatoSalad", "TomatoSalad"],
                             obs_spaces=["symbolic", "symbolic"], action_scheme="scheme3",
                             agent_respawn_rate=0.5, agent_despawn_rate=0.5, grace_period=0)
    env.reset(seed=seed)
    trace = []
    for _ in range(30):
        env.world.status_changed = [False, False]
        env.world.handle_agent_spawn()
        trace.append((tuple(env.world.active_agents), tuple(agent.location for agent in env.world.agents)))
    return trace


def test_agent_spawning_follows_the_seed(tmp_level):
    level = json.loads((LEVELS / "stochastic.json").read_text())
    level["AGENTS"][0]["MAX_COUNT"] = 2
    path = tmp_level(level)
    first = spawn_trace(path, 5)
    random.seed(99)
    np.random.seed(99)
    assert spawn_trace(path, 5) == first
    assert len(set(first)) > 3
    assert spawn_trace(path, 6) != first


# --- rgb_array render ----------------------------------------------------------------------------

@pytest.mark.parametrize("tile_size", [16, 32, 80])
def test_rgb_array_render_has_the_tile_size(tile_size):
    env = make_env(LEVELS / "tomato_salad.json", ["TomatoSalad"], render_mode="rgb_array", tile_size=tile_size)
    env.reset(seed=0)
    frame = env.render()
    assert isinstance(frame, np.ndarray)
    assert frame.dtype == np.uint8
    assert frame.shape == (7 * tile_size, 7 * tile_size, 3)
    assert core(env).render_rgb(tile_size=24).shape == (7 * 24, 7 * 24, 3)


def test_render_is_a_function_of_the_state():
    env = make_env(LEVELS / "tomato_salad.json", ["TomatoSalad"], render_mode="rgb_array", tile_size=16)
    env.reset(seed=0)
    start = env.render()
    assert np.array_equal(start, env.render())
    play(env, TOMATO_SALAD_SOLUTION[:3])  # tomato picked up
    held = env.render()
    assert not np.array_equal(start, held)
    env.reset(seed=0)  # rebuilds the world; the render must show the new one
    assert np.array_equal(start, env.render())


def test_render_rows_and_columns_follow_the_map():
    env = make_env(LEVELS / "tomato_salad.json", ["TomatoSalad"], render_mode="rgb_array", tile_size=16)
    env.reset(seed=0)
    frame = env.render().astype(int)
    before = frame.copy()
    play(env, [2])  # agent walks from (3, 3) to (4, 3): column 4, row 3 changes
    after = env.render().astype(int)
    changed = np.abs(after - before).sum(axis=2) > 0
    rows, cols = np.nonzero(changed)
    assert set(rows // 16) == {3}
    assert set(cols // 16) == {3, 4}


# --- Cucumber ------------------------------------------------------------------------------------

@pytest.mark.parametrize("tile_size", [16, 80])
def test_cucumber_levels_load_and_render(tile_size):
    env = make_env(LEVELS / "cucumber_onion.json", ["CucumberOnion"], render_mode="rgb_array", tile_size=tile_size)
    env.reset(seed=0)
    env.render()
    play(env, [2, 2, 2, 1, 1, 1, 1, 1])  # fetch the cucumber and put it on the cutboard
    cucumber = core(env).world.world_objects["Cucumber"][0]
    assert not cucumber.done()
    fresh = env.render()
    play(env, [1])  # chop it
    assert cucumber.done()
    chopped = env.render()
    tile = slice(3 * tile_size, 4 * tile_size), slice(0, tile_size)  # the cutboard at (0, 3)
    assert not np.array_equal(fresh[tile], chopped[tile])  # the label shows the chop state
