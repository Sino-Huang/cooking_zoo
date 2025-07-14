import argparse
import gymnasium as gym
import cooking_zoo
from cooking_zoo.environment.manual_policy import ManualPolicy
from cooking_zoo.environment.cooking_env import parallel_env

num_agents = 2
max_steps = 400
render = True
obs_spaces = ["feature_vector", "feature_vector"]
action_scheme = "scheme3"
meta_file = "example"
level = "larger_level_test" # "coexistence_test"
recipes = ["TomatoLettuceSalad", "CarrotBanana"]
end_condition_all_dishes = True
agent_visualization = ["human", "robot"]
reward_scheme = {"recipe_reward": 20, "max_time_penalty": -5, "recipe_penalty": -40, "recipe_node_reward": 0}


# env = gym.envs.make(
#     "cookingEnv-v1",
#     level=level,
#     meta_file=meta_file,
#     max_steps=max_steps,
#     recipes=recipes,
#     agent_visualization=agent_visualization,
#     obs_spaces=obs_spaces,
#     end_condition_all_dishes=end_condition_all_dishes,
#     action_scheme=action_scheme,
#     render=render,
#     reward_scheme=reward_scheme,
# )

# print(env.reset())
# print(env.step(env.action_space.sample()))  # take a random action

if __name__ == "__main__":
    env = parallel_env(level=level, meta_file=meta_file, num_agents=num_agents, max_steps=max_steps, recipes=recipes,
                    agent_visualization=agent_visualization, obs_spaces=obs_spaces,
                    end_condition_all_dishes=end_condition_all_dishes, action_scheme=action_scheme, render=render,
                    reward_scheme=reward_scheme)

    obs, info = env.reset()
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", action='store_true', default=False,
                        help="run a benchmark of environment step speed")
    
    action_space = env.action_space("player_0")
    args = parser.parse_args()
    if args.benchmark:
        import time
        start_time = time.time()
        for _ in range(1000):
            action = {"player_0": action_space.sample(), "player_1": action_space.sample()}
            obs, rewards, terminations, truncations, infos = env.step(action)
        end_time = time.time()
        print(f"Total time: {end_time - start_time:.4f} s")
        print(f"Avg step time: {(end_time - start_time) / 1000:.4f} s")
        print(f"Steps per second: {1000 / (end_time - start_time):.2f}")
        exit()

    env.render()

   

    manual_policy = ManualPolicy(env, agent_id="player_0")

    terminations = {"player_0": False}

    while not all(terminations.values()):
        action = {"player_0": manual_policy("player_0"), "player_1": action_space.sample()}
        observations, rewards, terminations, truncations, infos = env.step(action)
        env.render()