from cooking_zoo.environment import cooking_env
import gymnasium as gym


class GymCookingEnvironment(gym.Env):
    """Environment object for Overcooked."""

    metadata = {'render_modes': ['human', 'rgb_array'], 'name': "multi_agent_cooking_zoo"}

    def __init__(self, level, meta_file, num_agents, max_steps, recipes, agent_visualization=None, obs_spaces=None,
                 end_condition_all_dishes=False, action_scheme="scheme1", render=False, reward_scheme=None,
                 render_mode=None, tile_size=80):
        super().__init__()
        self.zoo_env = cooking_env.parallel_env(level=level, meta_file=meta_file, num_agents=num_agents,
                                                max_steps=max_steps, recipes=recipes,
                                                agent_visualization=agent_visualization, obs_spaces=obs_spaces,
                                                end_condition_all_dishes=end_condition_all_dishes,
                                                action_scheme=action_scheme, render=render, reward_scheme=reward_scheme,
                                                render_mode=render_mode, tile_size=tile_size)
        self.render_mode = render_mode
        self.observation_space = self.zoo_env.observation_space("player_0")
        self.action_space = self.zoo_env.action_space("player_0")

    def step(self, actions):
        action_dict = {f"player_{i}": actions[i] for i in range(len(actions))}
        obs, reward, termination, truncation, info = self.zoo_env.step(action_dict)
        return [obs[f"player_{i}"] for i in range(len(obs))], [reward[f"player_{i}"] for i in range(len(reward))], \
               [termination[f"player_{i}"] for i in range(len(termination))], \
               [truncation[f"player_{i}"] for i in range(len(truncation))], \
               [info[f"player_{i}"] for i in range(len(info))]

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        obs, info = self.zoo_env.reset(seed=seed, options=options)
        return [obs[f"player_{i}"] for i in range(len(obs))], [info[f"player_{i}"] for i in range(len(info))]

    def render(self):
        return self.zoo_env.render()
