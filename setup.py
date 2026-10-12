from setuptools import setup, find_packages

setup(name='cooking_zoo',
      version='1.0.1',
      description='Cooking gym with graphics and ideas based on: "Too Many Cooks: Overcooked environment"',
      author='David Rother',
      email='david.rother@tu-darmstadt.de',
      packages=find_packages(include=["cooking_zoo", "cooking_zoo.*"]),
      package_data={"cooking_zoo": ["environment/graphics/assets/*", "utils/meta_files/*.json",
                                    "utils/pddl_gen/*.pddl", "pools/*/pool.json", "pools/*/levels/*.json",
                                    "pools/*/problems/*.pddl"]},
      python_requires='>=3.10',
      install_requires=[
            'numpy',
            'pygame-ce',  # the maintained pygame fork (same `pygame` module); also what minigrid requires
            'pettingzoo>=1.24',
            'Pillow',
            'Gymnasium>=0.26'
      ],
      extras_require={
            # utils/pddl_gen/gen_and_plan.py and the gameplay test scripts; build_pool needs neither
            'scripts': ['tqdm', 'termcolor'],
      }
      )
