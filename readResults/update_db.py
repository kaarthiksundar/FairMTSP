import os, logging, json
import argparse, sqlite3

log = logging.getLogger(__name__)

class Config(object):
    """Class that holds global parameters."""

    def __init__(self):
        folder_path = os.path.dirname(os.path.realpath(__file__))
        self.base_path = os.path.abspath(os.path.join(folder_path, '..'))
        self.results_path = os.path.join(self.base_path, 'results')
        self.db_path = os.path.join(self.results_path, 'results.db')
        if os.path.exists(self.db_path):
            os.remove(self.db_path)


class ScriptException(Exception):
    """Custom exception class with message for this module."""

    def __init__(self, value):
        self.value = value
        super().__init__(value)

    def __repr__(self):
        return repr(self.value)
    
def table_exists(cursor, name):
    cmd = f"""
        SELECT count(name)
        FROM sqlite_master
        WHERE type='table'
        AND name='{name}'"""
    cursor.execute(cmd)
    return cursor.fetchone()[0] == 1

def create_table(cursor, name, fields):
    if not table_exists(cursor, name):
        field_str = ",".join(fields)
        cursor.execute(
            f"""CREATE TABLE {name} ({field_str})""")

class Controller:
    def __init__(self, config):
        self.config = config
        self._connection = None  # will point to a connection to a SQL database
        self._cursor = None

    def run(self):
        self._connection = sqlite3.connect(self.config.db_path)
        self._cursor = self._connection.cursor()

        self._write_result_table()

        self._connection.commit()
        self._cursor.close()
        self._connection.close()
        log.info("result addition completed")

    def _write_result_table(self):

        table_names = ['vehi3','vehi4','vehi5']
        objectiveList = ['min', 'minmax', 'pNorm', 'epsFair', 'deltaFair']
       
        for table_name in table_names:
            numVehicles = int(table_name[-1])
            col_names = ['instanceName', 'numTargets' , 'objective', 'pNorm', 'fairnessCoefficient'] + [f'l{i}' for i in range(1, numVehicles + 1)] + ['SumOfTours', 'GapToOpt', 'computationTimeInSec', 'GiniIndex', 'JainIndex', 'normIndex'] 
            create_table(self._cursor, table_name, col_names)
            

            for objective in objectiveList:
                objectiveDir = os.path.join(self.config.results_path, objective)
                for f in os.listdir(objectiveDir):
                    if not f.endswith(".json"):
                        continue
                    
                    with open(os.path.join(objectiveDir, f),'r') as fin:
                        result_dict = json.load(fin)
                        if result_dict['numVehicles'] != numVehicles:
                            continue
                
                        table_values = [result_dict['instanceName'], result_dict['numVertices']-1,  result_dict['objectiveType'], result_dict['pNorm'], result_dict['fairnessCoefficient']]+ result_dict['tourCost'] + [sum(result_dict['tourCost']), round(result_dict['optimalityGapPercent']/100, 2), result_dict['computationTimeInSec'], result_dict['giniIndex'], result_dict['jainIndex'], result_dict['normIndex']]
                        values = [f"'{v}'" for v in table_values]
                     
                        cmd = f"""
                            INSERT INTO {table_name}
                            VALUES ({",".join(values)})"""
                        self._cursor.execute(cmd)

                        log.info(f"added results for {f}")
                       



def main():
    logging.basicConfig(format='%(asctime)s %(levelname)s--: %(message)s',
                        level=logging.DEBUG)

    try:
        controller = Controller(Config())
        controller.run()
    except ScriptException as se:
        log.error(se)


if __name__ == '__main__':
    main()