
import argparse
import csv, sqlite3
import logging
import os
import shutil
import subprocess
import numpy as np
from math import floor, ceil

log = logging.getLogger(__name__)

class ScriptException(Exception):
    """Custom exception class with message for this module."""

    def __init__(self, value):
        self.value = value
        super().__init__(value)

    def __repr__(self):
        return repr(self.value)

class Config:

    def __init__(self) -> None:
        self.script_folder_path = os.path.dirname(os.path.realpath(__file__))
        self.base_path = os.path.abspath(os.path.join(self.script_folder_path, '../../../../..'))
        self.cplex_lib_path = guess_cplex_library_path()
        self.data_path = get_data_path()
        self.jar_path = os.path.join(
            self.base_path, 'app', 'build', 'libs', 'uber.jar')

        self.min_runs = False
        self.minmax_runs = False
        self.pNorm_runs = False
        self.epsFair_runs = False
        self.deltaFair_runs = False
        self.seattle_runs = False
        self.COF_runs = False
        self.minmaxFair = False
        self.pNormFair = False

def get_base_path() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..'))

def get_data_path() -> str:
    return os.path.join(get_base_path(), 'app', 'data')

def guess_cplex_library_path():
    gp_path = os.path.join(os.path.expanduser(
        "~"), ".gradle", "gradle.properties")
    if not os.path.isfile(gp_path):
        raise ScriptException(
            "gradle.properties not available at {}".format(gp_path))

    with open(gp_path, 'r') as fin:
        for line in fin:
            line = line.strip()
            if line.startswith('cplexLibPath='):
                return line.split('=')[-1].strip()

    raise ScriptException("unable to read value of cplexLibPath ")

class Controller:
    def __init__(self, config) -> None:
        self.config = config
        self._base_cmd = None
        self.objective = None

    def run(self):
        self._base_cmd = [
            "java", "-Xms32m", "-Xmx32g",
            "-Djava.library.path={}".format(self.config.cplex_lib_path),
            "-jar", "./uber.jar",
        ]
        self._prepare_uberjar()

        if self.config.seattle_runs:
            self._seattle_runs()
        elif self.config.COF_runs:
            self._COF_runs()
        elif self.config.minmaxFair:
            self.minmaxFair_runs()
        elif self.config.pNormFair:
            self.pNormFair_runs()
        else:
            config_to_objective = {"min_runs": "min","minmax_runs": "min-max","pNorm_runs": "p-norm",
                                "epsFair_runs": "eps-fair", "deltaFair_runs": "delta-fair"}

            for config, objective in config_to_objective.items():
                if getattr(self.config, config):
                    self.objective = objective
                    break

            self._setup_runs()


    def _setup_runs(self):
        cases = self._collect_cases()
        self._generate_setup(cases)

    def _generate_setup(self, cases):
        runs_file_path = os.path.join(
            self.config.script_folder_path, self.objective+'_runs.txt')

        with open(runs_file_path, 'w') as f_out:
            for instance, vehicle, fc, p in cases:
                cmd = [c for c in self._base_cmd]
                cmd.extend([
                    "-n", instance,
                    "-path", "./data/ "
                    "-r", "./results/ "
                    "-v", str(vehicle),
                    "-obj", self.objective,
                    "-fc", str(fc),
                    "-p", str(p),
                    "-t", str(3600)
                ])
                f_out.write(' '.join(cmd))
                f_out.write('\n')

        self._prepare_test_folder(cases)

    def _prepare_test_folder(self, cases):
        rt_path = os.path.join(self.config.base_path, 'runs', self.objective)
        os.makedirs(rt_path, exist_ok=True)
        shutil.copy(self.config.jar_path, os.path.join(rt_path, 'uber.jar'))
        runs_file_name = '{}_runs.txt'.format(self.objective)
        for f in [runs_file_name, 'submit-batch.sh', 'slurm-batch-job.sh']:
            src_path = os.path.join(self.config.script_folder_path, f)
            dst_path = os.path.join(rt_path, f)
            shutil.copy(src_path, dst_path)

        os.remove(os.path.join(self.config.script_folder_path, runs_file_name))
        log.info('copied runs file and shell scripts to {}'.format(rt_path))

        test_data_path = os.path.join(rt_path, 'data')
        os.makedirs(test_data_path, exist_ok=True)
        for instance,_,_,_ in cases:
            src = os.path.join(self.config.data_path, instance)
            dst = os.path.join(test_data_path, instance)
            shutil.copy(src, dst)


        for name in ['results', 'logs', 'output']:
            folder_path = os.path.join(rt_path, name)
            os.makedirs(folder_path, exist_ok=True)

        log.info('Test folder completed')

    def _collect_cases(self):
        instance_names = ['burma14.tsp', 'bays29.tsp', 'eil51.tsp', 'eil76.tsp']
        vehicles_count = [3,4,5]

        instance_names = ['eil51.tsp']
        vehicles_count = [5]

        pNorm = [2,3,5,10] if self.objective == "p-norm" else [1]
        fairnessCoefficient = np.arange(0,1,0.05) if self.objective in ["eps-fair", "delta-fair"] else [0.0]
        fairnessCoefficient = [round(x,2) for x in fairnessCoefficient]
        return [(instance, vehicle, fc, p) for instance in instance_names for vehicle in vehicles_count
                                            for fc in fairnessCoefficient for p in pNorm]
    
    def _COF_runs(self):
        cases = self._COF_cases()
        runs_file_path = os.path.join(
        self.config.script_folder_path, 'COF_runs.txt')

        with open(runs_file_path, 'w') as f_out:
            for instance, vehicle, objective, fc, p in cases:
                cmd = [c for c in self._base_cmd]
                cmd.extend([
                    "-n", instance,
                    "-path", "./data/ "
                    "-r", "./results/ "
                    "-v", str(vehicle),
                    "-obj", objective,
                    "-fc", str(fc),
                    "-p", str(p),
                    "-t", str(3600)
                ])
                f_out.write(' '.join(cmd))
                f_out.write('\n')

        rt_path = os.path.join(self.config.base_path, 'runs', 'COF')
        os.makedirs(rt_path, exist_ok=True)
        shutil.copy(self.config.jar_path, os.path.join(rt_path, 'uber.jar'))
        runs_file_name = 'COF_runs.txt'
        for f in [runs_file_name, 'submit-batch.sh', 'slurm-batch-job.sh']:
            src_path = os.path.join(self.config.script_folder_path, f)
            dst_path = os.path.join(rt_path, f)
            shutil.copy(src_path, dst_path)

        os.remove(os.path.join(self.config.script_folder_path, runs_file_name))
        log.info('copied runs file and shell scripts to {}'.format(rt_path))

        test_data_path = os.path.join(rt_path, 'data')
        os.makedirs(test_data_path, exist_ok=True)
        for instance,_,_,_,_ in cases:
            src = os.path.join(self.config.data_path, instance)
            dst = os.path.join(test_data_path, instance)
            shutil.copy(src, dst)


        for name in ['results', 'logs', 'output']:
            folder_path = os.path.join(rt_path, name)
            os.makedirs(folder_path, exist_ok=True)

        log.info('Test folder completed')

    def _COF_cases(self):
        instance_names = ['eil51.tsp']
        vehicles_count = [5]
        pNorm = [1]
        fairnessCoefficient = np.arange(0,1,0.05) 
        self.objective = ["eps-fair", "delta-fair"]
        fairnessCoefficient = [round(x,2) for x in fairnessCoefficient]
        return [(instance, vehicle, obj, fc, p) for instance in instance_names for vehicle in vehicles_count
                                            for obj in self.objective for fc in fairnessCoefficient for p in pNorm]

    def minmaxFair_runs(self):
        # generate eps/delta fair runs corresponding to minmax fairness coefficient
        
        runs_file_path = os.path.join(
        self.config.script_folder_path, 'minmaxFair_runs.txt')

        with open(runs_file_path, 'w') as f_out:
            for instance in ['burma14.tsp', 'bays29.tsp', 'eil51.tsp', 'eil76.tsp']:
                for objective in ['eps-fair', 'delta-fair']:
                    for numVehicle in [3,4,5]:
                        fairnessCoefficients = self.getFairnessIndex(instance, numVehicle, 'min-max')
                        if objective == 'eps-fair':
                            fc = round(floor(float(fairnessCoefficients['normIndex'])*10000)/10000,4)
                        elif objective == 'delta-fair':
                            fc = round(ceil(float(fairnessCoefficients['giniIndex'])*10000)/10000,4)
                   
                        cmd = [c for c in self._base_cmd]
                        cmd.extend([
                            "-n", instance,
                            "-path", "./data/ "
                            "-r", "./results/ "
                            "-v", str(numVehicle),
                            "-obj", objective,
                            "-fc", str(fc),
                            "-p", str(1),
                            "-t", str(3600)
                        ])
                        f_out.write(' '.join(cmd))
                        f_out.write('\n')

        rt_path = os.path.join(self.config.base_path, 'runs', 'minmaxFair')
        os.makedirs(rt_path, exist_ok=True)
        shutil.copy(self.config.jar_path, os.path.join(rt_path, 'uber.jar'))
        runs_file_name = 'minmaxFair_runs.txt'
        for f in [runs_file_name, 'submit-batch.sh', 'slurm-batch-job.sh']:
            src_path = os.path.join(self.config.script_folder_path, f)
            dst_path = os.path.join(rt_path, f)
            shutil.copy(src_path, dst_path)

        os.remove(os.path.join(self.config.script_folder_path, runs_file_name))
        log.info('copied runs file and shell scripts to {}'.format(rt_path))

        test_data_path = os.path.join(rt_path, 'data')
        os.makedirs(test_data_path, exist_ok=True)
        for instance in ['burma14.tsp', 'bays29.tsp', 'eil51.tsp', 'eil76.tsp']:
            src = os.path.join(self.config.data_path, instance)
            dst = os.path.join(test_data_path, instance)
            shutil.copy(src, dst)


        for name in ['results', 'logs', 'output']:
            folder_path = os.path.join(rt_path, name)
            os.makedirs(folder_path, exist_ok=True)

        log.info('Test folder completed')

    def pNormFair_runs(self):
         # generate eps/delta fair runs corresponding to p-norm fairness coefficient with p=2
        runs_file_path = os.path.join(
        self.config.script_folder_path, 'pNormFair_runs.txt')

        with open(runs_file_path, 'w') as f_out:
            for instance in ['burma14.tsp', 'bays29.tsp', 'eil51.tsp', 'eil76.tsp']:
                for objective in ['eps-fair', 'delta-fair']:
                    for numVehicle in [3,4,5]:
                        fairnessCoefficients = self.getFairnessIndex(instance, numVehicle, 'p-norm', pNorm=2)
                        if objective == 'eps-fair':
                            fc = round(floor(float(fairnessCoefficients['normIndex'])*10000)/10000,4)
                        elif objective == 'delta-fair':
                            fc = round(ceil(float(fairnessCoefficients['giniIndex'])*10000)/10000,4)
                   
                        cmd = [c for c in self._base_cmd]
                        cmd.extend([
                            "-n", instance,
                            "-path", "./data/ "
                            "-r", "./results/ "
                            "-v", str(numVehicle),
                            "-obj", objective,
                            "-fc", str(fc),
                            "-p", str(1),
                            "-t", str(3600)
                        ])
                        f_out.write(' '.join(cmd))
                        f_out.write('\n')

        rt_path = os.path.join(self.config.base_path, 'runs', 'pNormFair')
        os.makedirs(rt_path, exist_ok=True)
        shutil.copy(self.config.jar_path, os.path.join(rt_path, 'uber.jar'))
        runs_file_name = 'pNormFair_runs.txt'
        for f in [runs_file_name, 'submit-batch.sh', 'slurm-batch-job.sh']:
            src_path = os.path.join(self.config.script_folder_path, f)
            dst_path = os.path.join(rt_path, f)
            shutil.copy(src_path, dst_path)

        os.remove(os.path.join(self.config.script_folder_path, runs_file_name))
        log.info('copied runs file and shell scripts to {}'.format(rt_path))

        test_data_path = os.path.join(rt_path, 'data')
        os.makedirs(test_data_path, exist_ok=True)
        for instance in ['burma14.tsp', 'bays29.tsp', 'eil51.tsp', 'eil76.tsp']:
            src = os.path.join(self.config.data_path, instance)
            dst = os.path.join(test_data_path, instance)
            shutil.copy(src, dst)


        for name in ['results', 'logs', 'output']:
            folder_path = os.path.join(rt_path, name)
            os.makedirs(folder_path, exist_ok=True)

        log.info('Test folder completed')
    
    def getFairnessIndex(self, instance_name, numVehicles, objective, pNorm = 1, fc = 0.0):
        # returns jainIndex, giniIndex and normIndex corresponding to given instance 
        connection = sqlite3.connect(os.path.join(get_base_path(), 'results', 'results.db'))
        cursor = connection.cursor()
     
        cursor.execute(f"""
                SELECT GiniIndex, JainIndex, normIndex
                FROM {'vehi'+str(numVehicles)}
                WHERE instanceName = ? AND numVehicles = ? AND objective = ? AND pNorm = ? AND fairnessCoefficient = ?
                """,  (instance_name, str(numVehicles), objective, str(pNorm), str(fc)))
        result = cursor.fetchone()
        fairIndex = {'giniIndex': result[0], 'jainIndex':result[1], 'normIndex':result[2]} if result else None 
        return fairIndex


    def _seattle_runs(self):
        self.objective = ['eps-fair','delta-fair']
        fairnessCoefficient = [0.1, 0.3, 0.5, 0.7, 0.9]
        vehicle = 4
        cases =  [('seattle.tsp', vehicle, obj, fc) for obj in self.objective for fc in fairnessCoefficient]

        runs_file_path = os.path.join(
            self.config.script_folder_path, 'seattle_runs.txt')

        with open(runs_file_path, 'w') as f_out:
            for instance, vehicle, obj, fc in cases:
                cmd = [c for c in self._base_cmd]
                cmd.extend([
                    "-n", instance,
                    "-path", "./data/ "
                    "-r", "./results/ "
                    "-v", str(vehicle),
                    "-obj", obj,
                    "-fc", str(fc),
                    "-p", str(0),
                    "-t", str(3600)
                ])
                f_out.write(' '.join(cmd))
                f_out.write('\n')

        rt_path = os.path.join(self.config.base_path, 'runs', 'seattle')
        os.makedirs(rt_path, exist_ok=True)
        shutil.copy(self.config.jar_path, os.path.join(rt_path, 'uber.jar'))
        runs_file_name = 'seattle_runs.txt'
        for f in [runs_file_name, 'submit-batch.sh', 'slurm-batch-job.sh']:
            src_path = os.path.join(self.config.script_folder_path, f)
            dst_path = os.path.join(rt_path, f)
            shutil.copy(src_path, dst_path)

        os.remove(os.path.join(self.config.script_folder_path, runs_file_name))
        log.info('copied runs file and shell scripts to {}'.format(rt_path))

        test_data_path = os.path.join(rt_path, 'data')
        os.makedirs(test_data_path, exist_ok=True)
        for instance,_,_,_ in cases:
            src = os.path.join(self.config.data_path, instance)
            dst = os.path.join(test_data_path, instance)
            shutil.copy(src, dst)


        for name in ['results', 'logs', 'output']:
            folder_path = os.path.join(rt_path, name)
            os.makedirs(folder_path, exist_ok=True)

        log.info('Test folder completed')

    def _prepare_uberjar(self):
        os.chdir(self.config.base_path)
        subprocess.check_call(['gradle', 'clean', 'cleanlogs', 'uberjar'])
        if not os.path.isfile(self.config.jar_path):
            raise ScriptException("uberjar build failed")
        log.info("prepared uberjar")


def handle_command_line():
    parser = argparse.ArgumentParser()

    parser.add_argument("-min", "--min", action="store_true",
                        help="generate runs for min objective")
    parser.add_argument("-minmax", "--minmax", action="store_true",
                        help="generate runs for min-max objective")
    parser.add_argument("-pNorm", "--pNorm", action="store_true",
                        help="generate runs for p-Norm objective")
    parser.add_argument("-epsFair", "--epsFair", action="store_true",
                        help="generate runs for eps-fair objective")
    parser.add_argument("-deltaFair", "--deltaFair", action="store_true",
                        help="generate runs for delta-fair objective")
    parser.add_argument("-seattle", "--seattle", action="store_true",
                        help="generate runs for Seattle instance")
    parser.add_argument("-COF", "--COF", action="store_true",
                        help="generate COF instance of eps/delta Fair")
    parser.add_argument("-minmaxFair", "--minmaxFair", action="store_true",
                        help="generate eps/delta fair instances for corresponding min-max fairness")
    parser.add_argument("-pNormFair", "--pNormFair", action="store_true",
                        help="generate eps/delta fair instances for corresponding p-norm fairness for p=2")

    args = parser.parse_args()
    config = Config()

    config.min_runs = args.min
    config.minmax_runs = args.minmax
    config.pNorm_runs = args.pNorm
    config.epsFair_runs = args.epsFair
    config.deltaFair_runs = args.deltaFair
    config.seattle_runs = args.seattle
    config.COF_runs = args.COF
    config.minmaxFair = args.minmaxFair
    config.pNormFair = args.pNormFair

    return config


def main():
    logging.basicConfig(format='%(asctime)s %(levelname)s--: %(message)s',
                        level=logging.DEBUG)

    try:
        config = handle_command_line()
        controller = Controller(config)
        controller.run()
    except ScriptException as se:
        log.error(se)


if __name__ == '__main__':
    main()
