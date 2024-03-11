
import argparse
import csv
import logging
import os
import shutil
import subprocess

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
        self.base_path = os.path.abspath(os.path.join(self.script_folder_path, '../../../..'))
        self.cplex_lib_path = guess_cplex_library_path()
        self.data_path = os.path.join(self.base_path, 'data')
        self.jar_path = os.path.join(
            self.base_path, 'build', 'libs', 'uber.jar')
        self.instance_file_path = os.path.join(self.base_path, "final-results", "instances.csv")

        self.min_runs = True
        self.minmax_runs = False
        self.pNorm_runs = False
        self.espFair_runs = False
        self.deltaFair_runs = False
        
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

    def run(self):
        self._base_cmd = [
            "java", "-Xms32m", "-Xmx32g",
            "-Djava.library.path={}".format(self.config.cplex_lib_path),
            "-jar", "./uber.jar",
        ]
        self._prepare_uberjar()

        if self.config.min_runs:
            self._setup_min_runs()
            
        
    def _setup_min_runs(self):
        cases = self._collect_cases()
        self._generate_setup(cases)
        

    def _generate_setup(self, cases):
        runs_file_path = os.path.join(
            self.config.script_folder_path, '_runs.txt')
        
        with open(runs_file_path, 'w') as f_out:
            for instance, vehicle in cases:
                cmd = [c for c in self._base_cmd]
                cmd.extend([
                    "-n", instance,
                    "-v", str(vehicle),
                    "-obj", "min",
                    "-t", str(3600)
                ])
                f_out.write(' '.join(cmd))
                f_out.write('\n')



    def _collect_cases(self):
        cases = []
        instance_names = ['burma14.tsp', 'bay29.tsp', 'eil51.tsp', 'eil76.tsp']
        vehicles_count = [3,4,5]

        for instance in instance_names:
            for vehicle in vehicles_count:
                cases.append((instance, vehicle))

        return cases

    
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
    parser.add_argument("-i", "--instancefilepath", type=str,
                        help="path to csv file with instances to run")
    
    args = parser.parse_args()
    config = Config()

    config.min_runs = args.min
    config.minmax_runs = args.minmax
    config.pNorm_runs = args.pNorm
    config.espFair_runs = args.epsFair
    config.deltaFair_runs = args.deltaFair
    if args.instancefilepath:
        config.instance_file_path = args.instancefilepath

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