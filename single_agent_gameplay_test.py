import argparse
import gymnasium as gym
import cooking_zoo
from cooking_zoo.environment import cooking_env
from cooking_zoo.cooking_agents.cooking_agent import CookingAgent
import time 

max_steps = 400
render = True
obs_spaces = ["symbolic"]
action_scheme = "scheme3"
meta_file = "example"
level = "larger_level_test" # "coexistence_test"
recipes = ["TomatoLettuceSalad", "CarrotBanana"]
recipes = ["CarrotBanana"]
end_condition_all_dishes = True
agent_visualization = ["robot"]
reward_scheme = {"recipe_reward": 20, "max_time_penalty": -5, "recipe_penalty": -40, "recipe_node_reward": 0}


if __name__ == "__main__":
    # env = parallel_env(level=level, meta_file=meta_file, num_agents=num_agents, max_steps=max_steps, recipes=recipes,
    #                 agent_visualization=agent_visualization, obs_spaces=obs_spaces,
    #                 end_condition_all_dishes=end_condition_all_dishes, action_scheme=action_scheme, render=render,
    #                 reward_scheme=reward_scheme)

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

    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", action='store_true', default=False,
                        help="run a benchmark of environment step speed")

    action_space = env.action_space
    args = parser.parse_args()

    env.render()

    agent_policy = CookingAgent(recipes[0], "agent-1")

    terminations = False
    truncations = False
    
    while not (terminations or truncations):
        print("Start step")
        action = agent_policy.step(obs)
        # alt: randomly get an action from the action space
        # action = action_space.sample()
        obs, rewards, terminations, truncations, infos = env.step(action)
        env.render()
        print(f"Terminations: {terminations}, Rewards: {rewards}")
        print(f"Step: {env.unwrapped.zoo_env.unwrapped.t}")
        time.sleep(0.1)
        
    print("Game Over")
