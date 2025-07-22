import argparse
import gymnasium as gym
import cooking_zoo
from cooking_zoo.environment import cooking_env
from cooking_zoo.cooking_agents.cooking_agent import CookingAgent
import time 
from cooking_zoo.environment.manual_policy import ManualPolicy
from pathlib import Path
import random
from glob import glob
import json
from termcolor import colored
import os 

manual_control = False 

RECIPE_DICT = {
    "tomato-salad-food" : "TomatoSalad",
    "tomato-lettuce-salad-food" : "TomatoLettuceSalad",
    "tomato-lettuce-onion-salad-food" : "TomatoLettuceOnionSalad",
    "carrot-banana-food" : "CarrotBanana",
    "mashed-carrot-banana-food" : "MashedCarrotBanana",
    "cucumber-onion-food" : "CucumberOnion",
    "apple-watermelon-food" : "AppleWatermelon",
}

ACTION_PARSING_DICT = {
    'dir-left': 1,
    'dir-right': 2,
    'dir-up': 4,
    'dir-down': 3,
    'no-op': 0,
}

def parse_action(action):
    for key, value in ACTION_PARSING_DICT.items():
        if key in action:
            return value
    raise ValueError(f"Action {action} not recognized. Available actions: {list(ACTION_PARSING_DICT.keys())}")

def map_recipe(recipes):
    return [RECIPE_DICT[recipe] for recipe in recipes]

max_steps = 400
render = True
obs_spaces = ["symbolic"]
action_scheme = "scheme3"
meta_file = "example"
end_condition_all_dishes = True
agent_visualization = ["human"]
reward_scheme = {"recipe_reward": 20, "max_time_penalty": -5, "recipe_penalty": -40, "recipe_node_reward": 0}

PDDL_PLAN_FOLDER = Path(__file__).parent / "cooking_zoo/utils/pddl_plans"
PDDL_PROBLEM_FOLDER = Path(__file__).parent / "cooking_zoo/utils/pddl_problems"
DEBUG_WIDTH = 7
DEBUG_HEIGHT = 7
DEBUG_NUM_SWITCH = 1
DEBUG_NUM_BLOCKS = 2
DEBUG_NUM_RECIPES = 2
DEBUG_NUM_OUTPUT = 5
PROBLEM_CLAUSE = f"{DEBUG_WIDTH}x{DEBUG_HEIGHT}_switch{DEBUG_NUM_SWITCH}_block{DEBUG_NUM_BLOCKS}_recipe{DEBUG_NUM_RECIPES}"
LEVEL_FOLDER = Path(__file__).parent / "cooking_zoo/utils/level"

DEBUG_RESET_FLAG = False # Set to True to regenerate levels
if DEBUG_RESET_FLAG:
    # rm the old level files
    level_files = glob(str(LEVEL_FOLDER / PROBLEM_CLAUSE) +  "/*.json")
    plans_files = glob(str(PDDL_PLAN_FOLDER / PROBLEM_CLAUSE) +  "/*.json")
    problems_files = glob(str(PDDL_PROBLEM_FOLDER / PROBLEM_CLAUSE) +  "/*.pddl")
    
    # assert len(level_files) == len(plans_files), f"Number of level files {len(level_files)} does not match number of plans files {len(plans_files)}"
    # assert len(level_files) == len(problems_files), f"Number of level files {len(level_files)} does not match number of problems files {len(problems_files)}"
    
    for file in level_files + plans_files + problems_files:
        file_path = Path(file)
        if file_path.exists():
            file_path.unlink()
            print(f"Deleted {file_path}")
        else:
            print(f"{file_path} does not exist, skipping deletion.")
    
    cmdline = f"python cooking_zoo/utils/pddl_gen/gen_and_plan.py --width {DEBUG_WIDTH} --height {DEBUG_HEIGHT} --num_switch {DEBUG_NUM_SWITCH} --num_blocks {DEBUG_NUM_BLOCKS} --num_recipes {DEBUG_NUM_RECIPES} --num_output {DEBUG_NUM_OUTPUT}"
    import subprocess
    print(f"Running command: {cmdline}")
    subprocess.run(cmdline, shell=True, check=True)

if __name__ == "__main__":
    random.seed(int(time.time()))
    level_files = glob(str(LEVEL_FOLDER / PROBLEM_CLAUSE) +  "/*.json")
    # randomly select a level file
    if not level_files:
        raise ValueError(f"No level files found in {LEVEL_FOLDER / PROBLEM_CLAUSE}")
    level_file = Path(random.choice(level_files))
    level = f"{level_file.parent.name}/{level_file.stem}"
    
    # get the associated PDDL plan file
    pddl_plan_info_json_filepath = PDDL_PLAN_FOLDER / f"{level_file.parent.name}/{level_file.stem}_plans.json"
    
    assert pddl_plan_info_json_filepath.exists(), f"PDDL plan file {pddl_plan_info_json_filepath} does not exist"
    
    with open(pddl_plan_info_json_filepath, 'r') as f:
        pddl_plan_info = json.load(f)
        
    recipes = pddl_plan_info["recipes_tasks"]
    recipes = map_recipe(recipes)

    plan = pddl_plan_info["plans"][0]  # take the first plan
    # parse the plan into actions
    actions = [parse_action(p) for p in plan]
    
    action_counter = 0 
    
    # Print the stats
    print(f"Level: {level}")
    print(f"Recipes: {recipes}")
    

    env = gym.envs.make(
        "cookingEnv-v1",
        level=level,
        meta_file=meta_file,
        max_steps=max_steps,
        recipes=recipes,
        agent_visualization=agent_visualization,
        obs_spaces=obs_spaces,
        end_condition_all_dishes=end_condition_all_dishes,
        action_scheme=action_scheme,
        render=render,
        reward_scheme=reward_scheme,
    )

    obs, info = env.reset()

 

    action_space = env.action_space
    
    for act in actions:
        assert act in action_space, f"Action {act} not in action space {action_space}"

    env.render()

    
    if manual_control: 
        manual_policy = ManualPolicy(env.unwrapped.zoo_env, agent_id="player_0")

    terminations = False
    truncations = False
    has_displayed_plan = False
    while not (terminations or truncations):
        if manual_control:
            action = manual_policy("player_0")  # Use manual policy for player_0
        else:
            if not manual_control:
                if not has_displayed_plan:
                    visual_plan = [
                        colored(step, attrs=["bold"]) if idx == action_counter else step
                        for idx, step in enumerate(plan)
                    ]

                    print("Plan:", ", ".join(visual_plan))
                    has_displayed_plan = True
                time.sleep(0.2)  # Sleep to debug the gameplay
            if action_counter < len(actions):
                action = actions[action_counter]
                action_counter += 1
            else:
                print("No more actions to take, ending game.")
        # alt: randomly get an action from the action space
        # action = action_space.sample()
        obs, rewards, terminations, truncations, infos = env.step(action)
        env.render()
        # print(f"Terminations: {terminations}, Rewards: {rewards}")
        # print(f"Step: {env.unwrapped.zoo_env.unwrapped.t}")
        
        
    print("Game Over")
