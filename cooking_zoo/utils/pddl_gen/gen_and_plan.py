import time
import numpy as np
from cooking_zoo.utils.pddl_gen.overcooded_json_map_generator import OvercookedJSONMapGenerator
from cooking_zoo.utils.pddl_gen.pddl_problem_gen import generate_overcooked_pddl
from pathlib import Path
import subprocess
import os
import tempfile
import random
import numpy as np
from tqdm.auto import tqdm
import json
from glob import glob

INSTALL_CMD = "pip install kstar-planner"
ACTION_PARSING_DICT = {
    'dir-left': 1,
    'dir-right': 2,
    'dir-up': 4,
    'dir-down': 3,
    'no-op': 0,
}

class KSTAR():
    """KStar planner. (multiple plans)
    """
    def __init__(self, quality_bound=0.9, number_of_plans_bound=10, search_heuristic="ipdb(transform=undo_to_origin())"):
        super().__init__()
        self.quality_bound = quality_bound
        self.number_of_plans_bound = number_of_plans_bound
        self.search_heuristic = search_heuristic
        self._statistics = {}

        # Check if kstar-planner is installed in pip packages
        check_output = subprocess.getoutput("pip show kstar-planner")
        if "Name: kstar-planner" not in check_output:
            self._install_kstar()
        else:
            print("kstar-planner is already installed.")
            
    def plan_from_pddl(self, dom_file, prob_file, horizon=np.inf, timeout=10,
                       remove_files=False):
        """PDDL-specific planning method.
        """
        start_time = time.time()
        
        from kstar_planner import planners as kstar_planners
        
        output = kstar_planners.plan_unordered_topq(
            domain_file=Path(dom_file),
            problem_file=Path(prob_file),
            quality_bound=self.quality_bound,
            number_of_plans_bound=self.number_of_plans_bound,
            timeout=timeout,
            search_heuristic=self.search_heuristic
        )
        if remove_files:
            os.remove(dom_file)
            os.remove(prob_file)
        if time.time()-start_time > timeout:
            raise RuntimeError("Planning took too long, timeout reached: {} seconds".format(timeout))

        pddl_plan_lst = self._output_to_plan_list(output)

        pddl_plan_lst = [x for x in pddl_plan_lst if len(x) <= horizon]
        if len(pddl_plan_lst) == 0:
            raise ValueError("No valid plans found within the horizon limit: {}".format(horizon))
        return pddl_plan_lst

    def _output_to_plan_list(self, output):
        if output.get('plans') is None:
            raise ValueError("No plans found in the output. Check if the planner was installed correctly or if the input PDDL files are valid.")
        else:
            self._statistics['num_plans'] = len(output['plans'])
            cost_dict = {}
            cost_id_dict = {}
            for i, plan in enumerate(output['plans']):
                cost = plan['cost']
                if cost not in cost_dict:
                    cost_dict[cost] = 0
                cost_dict[cost] += 1
                if cost not in cost_id_dict:
                    cost_id_dict[cost] = []
                cost_id_dict[cost].append(i)
            # calculate cost distribution
            total_plans = sum(cost_dict.values())
            cost_dict = {k: v / total_plans for k, v in cost_dict.items()}
            self._statistics['cost_distribution'] = cost_dict
            pddl_plan_lst = [] # sorted by lower cost first
            sorted_costs = sorted(cost_dict.keys())
            self._statistics['sorted_costs'] = sorted_costs
            for cost in sorted_costs:
                for plan_id in cost_id_dict[cost]:
                    pddl_plan = output['plans'][plan_id]['actions']
                    pddl_plan_lst.append(pddl_plan)

            return pddl_plan_lst
        
    def _parse_action(self, action_str):
        for action, action_id in ACTION_PARSING_DICT.items():
            if action in action_str:
                return action_id
        raise ValueError(f"Action string '{action_str}' does not match any known action.")
        
    def __call__(self, domain_file, problem_file, horizon=np.inf, timeout=30,
                 return_files=False, parse_actions=False):

        dom_file = tempfile.NamedTemporaryFile(delete=False).name
        prob_file = tempfile.NamedTemporaryFile(delete=False).name
        # copy the domain and problem files to temporary files
        with open(domain_file, 'r') as f:
            with open(dom_file, 'w') as temp_f:
                temp_f.write(f.read())
        with open(problem_file, 'r') as f:
            with open(prob_file, 'w') as temp_f:
                temp_f.write(f.read())
        
        pddl_plan = self.plan_from_pddl(
            dom_file, prob_file, horizon=horizon,
            timeout=timeout, remove_files=(not return_files))

        plan = []
        if parse_actions:
            for pddl_single_plan in pddl_plan:
                parsed_plan = [
                    self._parse_action(plan_step)
                    for plan_step in pddl_single_plan
                ]
                plan.append(parsed_plan)
        else:
            plan = pddl_plan

        if return_files:
            return plan, dom_file, prob_file
        return plan
            
    def _install_kstar(self):
        # Install and compile FD.
        os.system(INSTALL_CMD)
        
        
class FastDownward():
    """FastDownward planner. (multiple plans)
    """
    def __init__(self,fast_downward_path =None, quality_bound=0.9, number_of_plans_bound=10):
        super().__init__()
        if fast_downward_path is not None:
            self.fast_downward_path = fast_downward_path
        else:
            self.fast_downward_path = os.path.join(os.path.dirname(__file__), "fast-downward.py")
        self.quality_bound = quality_bound
        self.number_of_plans_bound = number_of_plans_bound
        self._statistics = {}
 
    def get_statistics(self):
        """Get statistics of the planner.
        """
        return self._statistics
            
    def plan_from_pddl(self, dom_file, prob_file, horizon=np.inf, timeout=10,
                       remove_files=False, optimal=False):
        """PDDL-specific planning method.
        """
        start_time = time.time()
        
        fast_downward_path = self.fast_downward_path
        if not os.path.exists(fast_downward_path):
            raise FileNotFoundError(f"Fast Downward script not found at {fast_downward_path}. Please ensure it is in the correct directory.")
        if not optimal:
            output = subprocess.run([
                str(fast_downward_path),
                '--alias',
                'lama-first',
                '--search-time-limit',
                str(timeout),
                dom_file,
                prob_file,
            ],
                                    capture_output=True, text=True, check=True)
            plan_raw_output = output.stdout
        else:
            try:
                output = subprocess.run([
                    str(fast_downward_path),
                    '--alias',
                    'lama',
                    '--search-time-limit',
                    str(timeout),
                    '--overall-time-limit',
                    str(timeout),
                    dom_file,
                    prob_file,
                ],
                                        capture_output=True, text=True, check=True)
                plan_raw_output = output.stdout
                
            except subprocess.CalledProcessError as e:
                stdout_text = e.stdout
                stderr_text = e.stderr
                plan_raw_output = stdout_text + stderr_text
        
        # pick lines after Actual search time and before Plan length
        plan_group = []
        plan_lines = []
        start_collecting = False 
        for line in plan_raw_output.splitlines():
            if "Actual search time" in line:
                start_collecting = True
                continue
            if "Plan length" in line:
                start_collecting = False
                plan_group.append(plan_lines)
                plan_lines = []
            if start_collecting:
                plan_lines.append(line.strip())
            else:
                continue
        
        # sort the plan_group
        plan_group.sort(key=lambda x: len(x))  # sort by length of plan
        
        output = {'plans': []}
        for each_plan in plan_group:
            output['plans'].append({
                'actions': each_plan,
                'cost': len(each_plan)  # assuming cost is the length of the plan
            })
        if remove_files:
            os.remove(dom_file)
            os.remove(prob_file)
            

        pddl_plan_lst = self._output_to_plan_list(output)

        pddl_plan_lst = [x for x in pddl_plan_lst if len(x) <= horizon]
        if len(pddl_plan_lst) == 0:
            raise ValueError("No valid plans found within the horizon limit: {}".format(horizon))
        return pddl_plan_lst

    def _output_to_plan_list(self, output):
        if output.get('plans') is None:
            raise ValueError("No plans found in the output. Check if the planner was installed correctly or if the input PDDL files are valid.")
        else:
            self._statistics['num_plans'] = len(output['plans'])
            cost_dict = {}
            cost_id_dict = {}
            for i, plan in enumerate(output['plans']):
                cost = plan['cost']
                if cost not in cost_dict:
                    cost_dict[cost] = 0
                cost_dict[cost] += 1
                if cost not in cost_id_dict:
                    cost_id_dict[cost] = []
                cost_id_dict[cost].append(i)
            # calculate cost distribution
            total_plans = sum(cost_dict.values())
            cost_dict = {k: v / total_plans for k, v in cost_dict.items()}
            self._statistics['cost_distribution'] = cost_dict
            pddl_plan_lst = [] # sorted by lower cost first
            sorted_costs = sorted(cost_dict.keys())
            self._statistics['sorted_costs'] = sorted_costs
            for cost in sorted_costs:
                for plan_id in cost_id_dict[cost]:
                    pddl_plan = output['plans'][plan_id]['actions']
                    pddl_plan_lst.append(pddl_plan)

            return pddl_plan_lst
        
    def _parse_action(self, action_str):
        for action, action_id in ACTION_PARSING_DICT.items():
            if action_str.startswith(action):
                return action_id
        raise ValueError(f"Action string '{action_str}' does not match any known action.")
        
    def __call__(self, domain_file, problem_file, horizon=np.inf, timeout=30,
                 return_files=False, parse_actions=False, optimal=False):

        dom_file = tempfile.NamedTemporaryFile(delete=False).name
        prob_file = tempfile.NamedTemporaryFile(delete=False).name
        # copy the domain and problem files to temporary files
        with open(domain_file, 'r') as f:
            with open(dom_file, 'w') as temp_f:
                temp_f.write(f.read())
        with open(problem_file, 'r') as f:
            with open(prob_file, 'w') as temp_f:
                temp_f.write(f.read())
        
        pddl_plan = self.plan_from_pddl(
            dom_file, prob_file, horizon=horizon,
            timeout=timeout, remove_files=(not return_files), optimal=optimal)

        plan = []
        
        if parse_actions:
            for pddl_single_plan in pddl_plan:
                parsed_plan = [
                    self._parse_action(plan_step)
                    for plan_step in pddl_single_plan
                ]
                plan.append(parsed_plan)
        else:
            plan = pddl_plan

        if return_files:
            return plan, dom_file, prob_file
        return plan
    
        
RECIPE_DICT = {
    "tomato-salad-food" : "TomatoSalad",
    "tomato-lettuce-salad-food" : "TomatoLettuceSalad",
    "tomato-lettuce-onion-salad-food" : "TomatoLettuceOnionSalad",
    "carrot-banana-food" : "CarrotBanana",
    "mashed-carrot-banana-food" : "MashedCarrotBanana",
    "cucumber-onion-food" : "CucumberOnion",
    "apple-watermelon-food" : "AppleWatermelon",
}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate Tasks and Plans for Overcooked.")
    parser.add_argument("--width", type=int, default=7, help="Width of the map.")
    parser.add_argument("--height", type=int, default=7, help="Height of the map.")
    parser.add_argument("--map_id", type=int, help="Map ID to generate.")
    parser.add_argument("--num_switch", type=int, default=1, help="Number of switches in the map.")
    parser.add_argument("--num_blocks", type=int, default=2, help="Number of blocks in the map.")
    parser.add_argument("--num_recipes", type=int, default=2, help="Number of recipes required to complete.")
    parser.add_argument("--num_output", type=int, default=1, help="Number of problems instnaces to generate.")
    parser.add_argument("--timeout", type=str, default='30', help="Timeout for planner")
    parser.add_argument("--optimal", action='store_true', help="Use optimal planning (default: False).")
    
    args = parser.parse_args()
    
    num_recipes = args.num_recipes
    map_width = args.width
    map_height = args.height
    raw_map_id = args.map_id 
    num_switch = args.num_switch
    num_blocks = args.num_blocks
    num_recipes = args.num_recipes
    num_output = args.num_output
    timeout = args.timeout
    optimal = args.optimal
    
    pbar = tqdm(total=num_output)
    
    if raw_map_id is not None and num_output > 1:
        raise ValueError("If map_id is provided, num_output must be 1.")
    
    actual_count = 0 
    
    current_time = time.time()
    random.seed(int(current_time))
    np.random.seed(int(current_time))
    
    already_ids = set()
    while actual_count < num_output:
        # select num_recipes from RECIPE_DICT
        recipes_tasks = np.random.choice(list(RECIPE_DICT.keys()), size=num_recipes, replace=True)
        recipes_tasks = recipes_tasks.tolist()
        if raw_map_id is None: 
            # check map_id 
            map_id = random.randint(0, 2**32 - 1)
            while map_id in already_ids:
                map_id = random.randint(0, 2**32 - 1)
            already_ids.add(map_id)
        else:
            map_id = raw_map_id
            
        pbar.set_description(f"Generating task {actual_count+1}/{num_output}, id={map_id}, recipes={recipes_tasks}")
        
        random.seed(map_id)
        np.random.seed(map_id)
        
        clause_name = f"{map_width}x{map_height}_switch{num_switch}_block{num_blocks}_recipe{num_recipes}"
        
        # ! step 2: generate the json map file
        try:
            map_generator = OvercookedJSONMapGenerator(
                width = map_width,  
                height = map_height,  
                num_switch = num_switch,  
                num_block = num_blocks,  
                goal_recipes = recipes_tasks,  
                map_id = map_id,  
            )
            
            level_dict = map_generator.generate()
        except Exception as e:
            print(f"Error generating map: {e}, seed ={map_id}")
            continue
        # ! we may delete json_output_path if no plan can be found 
        json_output_path = Path(os.path.join(os.path.dirname(__file__), f"../level/{clause_name}/p{map_id}-overcooked.json"))
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        map_generator.output_level_dict(level_dict, json_output_path)
        
        # ! step 3: generate the pddl problem file 
        
        problem_name = json_output_path.stem
        pddl_problem = generate_overcooked_pddl(
            level_dict,
            problem_name=problem_name,
            goal_clauses= recipes_tasks,
        )
        
        pddl_problem_filename = json_output_path.name.replace(".json", ".pddl")
        # ! we may delete pddl_problem_file_path if no plan can be found
        pddl_problem_file_path = Path(os.path.join(os.path.dirname(__file__), f"../pddl_problems/{clause_name}/{pddl_problem_filename}"))
        pddl_problem_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        pddl_problem_file_path.write_text(pddl_problem)
        
        # ! step 4: generate the pddl plan
        
        my_planner = FastDownward()
        domain_file = os.path.join(os.path.dirname(__file__), "overcooked.pddl")
        
        try:
            plans = my_planner(domain_file, pddl_problem_file_path, timeout=timeout, optimal=optimal)
            assert len(plans) > 0, "No plans found."
            # save the plans and the recipes_tasks into a json file 
            plan_info_dict = {
                "map_id": map_id,
                "map_width": map_width,
                "map_height": map_height,
                "num_switch": num_switch,
                "num_blocks": num_blocks,
                "num_recipes": num_recipes,
                "recipes_tasks": recipes_tasks,
                "plans": plans,
            }
            plan_filename = json_output_path.name.replace(".json", "_plans.json")
            plan_file_path = Path(os.path.join(os.path.dirname(__file__), f"../pddl_plans/{clause_name}/{plan_filename}"))
            plan_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(plan_file_path, 'w') as f:
                json.dump(plan_info_dict, f, indent=2)
            
            actual_count += 1
            pbar.update(1)
            
            
            existing_json_files = glob(str(json_output_path.parent) + "/*.json")
            if len(existing_json_files) != actual_count:
                print(f"Warning: {len(existing_json_files)} JSON files found, expected {actual_count}.")
            
        except Exception as e:
            print(f"Error generating plan: {e}, seed ={map_id}, Deleting files...")
            json_output_path.unlink(missing_ok=False)
            pddl_problem_file_path.unlink(missing_ok=False)
            continue
        
        