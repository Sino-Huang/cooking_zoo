from cooking_zoo.environment import cooking_env
import gymnasium as gym


class GymCookingEnvironment(gym.Env):
    """Environment object for Overcooked."""

    metadata = {'render_modes': ['human', 'rgb_array'], 'name': "cooking_zoo"}

    def __init__(self, level, meta_file, max_steps, recipes, agent_visualization=None, obs_spaces=None,
                 end_condition_all_dishes=False, action_scheme="scheme1", render=False, reward_scheme=None,
                 render_mode=None, tile_size=80):
        super().__init__()
        self.zoo_env = cooking_env.parallel_env(level=level, meta_file=meta_file, num_agents=1, max_steps=max_steps,
                                                recipes=recipes, agent_visualization=agent_visualization,
                                                obs_spaces=obs_spaces,
                                                end_condition_all_dishes=end_condition_all_dishes,
                                                action_scheme=action_scheme, render=render, reward_scheme=reward_scheme,
                                                render_mode=render_mode, tile_size=tile_size)
        self.render_mode = render_mode
        self.observation_space = self.zoo_env.observation_space("player_0")
        self.action_space = self.zoo_env.action_space("player_0")

    def step(self, action):
        converted_action = {"player_0": action}
        obs, reward, termination, truncation, info = self.zoo_env.step(converted_action)
        return obs["player_0"], reward["player_0"], termination["player_0"], truncation["player_0"], info["player_0"]

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        obs, info = self.zoo_env.reset(seed=seed, options=options)
        return obs["player_0"], info["player_0"]

    def render(self):
        return self.zoo_env.render()
