# Code for CookingZoo

Contents:
- [Introduction](#introduction)
- [Installation](#installation)
- [Usage](#usage)
- [Extending The Environment](#extending-the-environment)

## Introduction

CookingZoo is a derived work and reuse part of the visual assets.
It is a flexible cooking environment with a lot of different cooking tools and ingredients to test
generalization abilities. It offers multi-agent support with the PettingZoo library and the gymnasium library. 
Furthermore, one agent may be controlled by a human.

The advantages of using this environment are listed below:

```
- Extensive Library of existing recipes and room with extensibility to add more
- Different Observation spaces (Feature Vector, symbolic)
- Customizable Level design
- Observation spaces can be same size for different levels with fixed object location
- Variable number of agents
- Cover Competing, Collaborating and Coexisting Environments
- Multi-agent support with PettingZoo and gymnasium latest versions
- Human controllable agent
```

Please cite this paper when using this environment using bibtex:

```
@inproceedings{rother2023disentangling,
  title={Disentangling Interaction using MaximumEntropy Reinforcement Learning in Multi-Agent Systems},
  author={Rother, David and Weisswange, Thomas and Peters, Jan},
  booktitle={European Conference on Artificial Intelligence},
  year={2023}
}
```

You can use this bibtex if you would like to cite the original paper this work is derived from (Wu and Wang et al., 2021):
```
@article{wu_wang2021too,
  author = {Wu, Sarah A. and Wang, Rose E. and Evans, James A. and Tenenbaum, Joshua B. and Parkes, David C. and Kleiman-Weiner, Max},
  title = {Too many cooks: Coordinating multi-agent collaboration through inverse planning},
  journal = {Topics in Cognitive Science},
  year = {2021},
  volume = {n/a},
  number = {n/a},
  keywords = {Coordination, Social learning, Inverse planning, Bayesian inference, Multi-agent reinforcement learning},
  doi = {https://doi.org/10.1111/tops.12525},
  url = {https://onlinelibrary.wiley.com/doi/abs/10.1111/tops.12525},
}
```

## Installation

```
git clone https://github.com/Sino-Huang/cooking_zoo.git
cd cooking_zoo
pip3 install -e .
```

The environment needs Python 3.10 or higher. It uses `pygame-ce` (the maintained pygame fork; same `pygame`
module). The generation scripts `gen_and_plan.py` and `single_agent_gameplay_test.py` also need
`pip3 install -e .[scripts]` (tqdm, termcolor). Tests: `python -m pytest tests`.

## Usage 

```python
# Example Parameters for two agents
num_agents = 2
max_steps = 400
render = True
obs_spaces = ["feature_vector", "feature_vector"]
action_scheme = "scheme3"
meta_file = "example"
level = "coop_test"
recipes = ["TomatoLettuceSalad", "CarrotBanana"]
end_condition_all_dishes = True
agent_visualization = ["human", "robot"]
reward_scheme = {"recipe_reward": 20, "max_time_penalty": -5, "recipe_penalty": -40, "recipe_node_reward": 0}


# Single Agent gym environment
env = gym.envs.make("cooking_zoo:cookingEnvMA-v1", level=level, meta_file=meta_file, num_agents=num_agents,
                    max_steps=max_steps, recipes=recipes, agent_visualization=agent_visualization,
                    obs_spaces=obs_spaces, end_condition_all_dishes=end_condition_all_dishes,
                    action_scheme=action_scheme, render=render, reward_scheme=reward_scheme)

# Multi Agent gym environment
env = gym.envs.make("cooking_zoo:cookingEnv-v1", level=level, meta_file=meta_file,
                    max_steps=max_steps, recipes=recipes, agent_visualization=agent_visualization,
                    obs_spaces=obs_spaces, end_condition_all_dishes=end_condition_all_dishes,
                    action_scheme=action_scheme, render=render, reward_scheme=reward_scheme)

# Multi Agent PettingZoo environment
env = parallel_env(level=level, meta_file=meta_file, num_agents=num_agents, max_steps=max_steps, recipes=recipes,
                   agent_visualization=agent_visualization, obs_spaces=obs_spaces,
                   end_condition_all_dishes=end_condition_all_dishes, action_scheme=action_scheme, render=render,
                   reward_scheme=reward_scheme)
```

The environment can be used as a gym environment and as a PettingZoo environment. PettingZoo is 
a multi-agent environment library and is compatible with big frameworks such as 
[RLLib](https://docs.ray.io/en/latest/rllib/index.html), [StableBaselines3](https://stable-baselines3.readthedocs.io/en/master/),
[PettingZoo](https://www.pettingzoo.ml/), [EPyMARL](https://github.com/uoe-agents/epymarl), 
[MushroomRL](https://github.com/MushroomRL/mushroom-rl), and others that support the gym single-agent interface, 
the gym multi-agent convention as found in EPyMARL or the more general PettingZoo interface.

Please note that we use the updated gym conventions of version 0.26.1 and upwards, where done is replaced with 
termination and truncation variables. During test a small wrapper was necessary with EPyMARL for 
compatibility reasons.

A single-agent usage example is shown in the main.py file.
To get a playable demo in a single agent environment view the demo_gameplay.py file
and for a playable multi-agent demo, where another agent is controlled by a random movement AI view 
the demo_multiplayer_gameplay.py file.

### Seeding, termination and pixels

- `reset(seed=s)` seeds a per-environment `random.Random` that every stochastic part of the engine draws from
  (random object and agent placement from candidate positions, OPTIONAL objects, agent respawn/despawn); the
  global `random`/`np.random` are not used. The same seed gives the same layout; an unseeded reset continues
  the environment's stream.
- An episode ends with `terminated=True` on the step that completes the recipe (all recipes with
  `end_condition_all_dishes=True`), and with `truncated=True` on step `max_steps`. Completion on the last step
  is a termination.
- `render_mode="rgb_array"` (with `tile_size`, pixels per tile, default 80) makes `render()` return an
  (H, W, 3) uint8 frame of the current state drawn off-screen; `CookingEnvironment.render_rgb(tile_size)` draws
  one at any tile size. The default `render_mode=None` keeps the window/hidden-surface rendering.

```python
env = gym.make("cookingEnv-v1", level=level, meta_file="example", max_steps=400, recipes=["TomatoSalad"],
               obs_spaces=["symbolic"], action_scheme="scheme3", render_mode="rgb_array", tile_size=16)
obs, info = env.reset(seed=0)
frame = env.render()  # (16 * height, 16 * width, 3) uint8
```

## Observation Spaces

# Feature Vector
a numpy vector containing a feature representation of all objects in the world

# Symbolic
A copy of all objects in the world for reasoning purposes

## Extending the environment

In this section it is described how to add additional objects and make changes 
to the code to fit the simulation to your needs.

### Adding Objects

Look up the file world_objects.py in the folder cooking_world.
In this file add a new class of your object and let it inherit from the desired classes in abstract_classes.py.
To get specific implementation details you can look at another inherited objects. 


### Recipes

A recipe is a graph in this game. Everything related to recipes is found in the folder cooking_book.
A recipe node describes a state in the world that is desired and is fulfilled when it is reached. 
More concrete a node takes as input an object type, the conditions for the attributes of that object and
what should be on/in the object (if applicable). If an object of the correct object type then fulfills all 
specified conditions and holds all specified objects (described as nodes), then the node is considered done.

By chaining different nodes now in the contains section you get a graph that the game can check if it is fulfilled 
or not and hand out rewards for each node.

To add a new recipe add the node call the register_recipe function in the recipe_book.py file.
If you want to add to the default recipe book directly add the recipe in the files.



## Level pools

`cooking_zoo/pools/<name>/` holds versioned, hashed level pools: `pool.json` (generator settings, pool seed,
planner, and per level the map id, recipe, level/problem files with SHA-256, the PDDL plan and its scheme3
actions), `levels/*.json` and `problems/*.pddl`. Load one with `cooking_zoo.pools.load_pool()`, verify its
hashes with `verify_pool()`, and play a level with `make_env(entry)`.

`pool50_7x7_v1`: 50 generated 7×7 levels without switches or blocks, one recipe each, 10 each of TomatoSalad,
TomatoLettuceSalad, TomatoLettuceOnionSalad, CarrotBanana and AppleWatermelon. Every plan completes its recipe
in the engine within 400 steps (`tests/test_pool.py`).

Build a pool, or check that a rebuild reproduces the committed files byte for byte (Fast Downward
`release-26.6.0`, built with `python3 build.py` in its checkout):

```
python -m cooking_zoo.utils.pddl_gen.build_pool --fast-downward <downward>/fast-downward.py [--check]
```

## Generating Problem Instances 

```python
python cooking_zoo/utils/pddl_gen/gen_and_plan.py --width 7 --height 7 --num_switch 0 --num_blocks 0 --num_recipes 1 --num_output 50

python cooking_zoo/utils/pddl_gen/gen_and_plan.py --width 7 --height 7 --num_switch 0 --num_blocks 0 --num_recipes 2 --num_output 10
```

The associated PDDL problems files and PDDL plans will be in `cooking_zoo/utils/pddl_problems` and `cooking_zoo/utils/pddl_plans` respectively.

## PDDL Generation 

The PDDL generation folder is in `cooking_zoo/utils/pddl_gen`. `cooking_zoo/utils/pddl_gen/overcooked.pddl` is the domain PDDL file. `cooking_zoo/utils/pddl_gen/fast-downward.py` is a soft link to the Fast Downward planner (you have to download your own copy (soft link) of Fast Downward and place it in the `cooking_zoo/utils/pddl_gen` directory).

`cooking_zoo/utils/pddl_gen/overcooded_json_map_generator.py` is a script to procedurally generate maps in JSON format for the Overcooked domain. (JSON files are used for this cooking zoo environment.)

`cooking_zoo/utils/pddl_gen/pddl_problem_gen.py` is a script to generate PDDL problem files based on the Overcooked domain and the JSON maps generated by `overcooded_json_map_generator.py`.

`cooking_zoo/utils/pddl_gen/gen_and_plan.py` is the all-in-one script to generate JSON files, associated PDDL problems and plans. 

Finally, you can run the script `single_agent_gameplay_test.py` to test the generated task instances and plans with a single agent in the Overcooked environment.