import sqlite3, logging
import csv, os

log = logging.getLogger(__name__)

class ScriptException(Exception):
    """Custom exception class with message for this module."""

    def __init__(self, value):
        self.value = value
        super().__init__(value)

    def __repr__(self):
        return repr(self.value)


class databaseToCSV():
    def __init__(self, database_path) -> None:
        self.connection = sqlite3.connect(database_path)
        self.cursor = self.connection.cursor()
       

    def _closeConnection(self):                
        self.cursor.close()
        self.connection.close()

    def _getComputationTime(self, instance_name, objective, numVehicles, pNorm = 1, fc = 0.0):
        self.cursor.execute(f"""
            SELECT computationTimeInSec
            FROM {'vehi'+str(numVehicles)}
            WHERE instanceName = ? AND numVehicles = ? AND objective = ? AND pNorm = ? AND fairnessCoefficient = ?
        """, (instance_name, str(numVehicles), objective, str(pNorm), str(fc)))
        result = self.cursor.fetchone()
        return result[0] if result else None 
      
    def _getSumofTours(self, instance_name, objective, numVehicles, pNorm = 1, fc = 0.0):
        self.cursor.execute(f"""
            SELECT SumOfTours
            FROM {'vehi'+str(numVehicles)}
            WHERE instanceName = ? AND numVehicles = ? AND objective = ? AND pNorm = ? AND fairnessCoefficient = ?
        """, (instance_name, str(numVehicles), objective, str(pNorm), str(fc)))
        result = self.cursor.fetchone()
        return result[0] if result else None 

    def export_computation_time_to_csv(self, results_path, table_objective):

        csv_filename = os.path.join(results_path, table_objective+'.csv')

        with open(csv_filename, 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            if table_objective == 'p-norm':
                csv_writer.writerow(['Instance Name', 'Number of Vehicles', 'min (sec)', 'minmax ', 'pNorm 2', 'pNorm 3', 'pNorm 5', 'pNorm 10'])  # Write header
            if table_objective == 'eps-fair':
                csv_writer.writerow(['Instance Name', 'Number of Vehicles', 'min (sec)', 'minmax', 'epsFair 0.1', 'epsFair 0.3', 'epsFair 0.5', 'epsFair 0.7', 'epsFair 0.9'])  # Write header
            if table_objective == 'delta-fair':
                csv_writer.writerow(['Instance Name', 'Number of Vehicles', 'min (sec)', 'minmax', 'deltaFair 0.1', 'deltaFair 0.3', 'deltaFair 0.5', 'deltaFair 0.7', 'deltaFair 0.9'])  # Write header

            data = []
            for instance_name in ['burma14.tsp', 'bays29.tsp', 'eil51.tsp', 'eil76.tsp']:
                for numVehicle in [3,4,5]:
                    data = [instance_name, numVehicle]
                    min_time = 0
                    for objective in ['min', 'min-max', table_objective]:
                        if objective == 'min':
                            min_time = float(self._getComputationTime(instance_name=instance_name, objective=objective, numVehicles=numVehicle))
                            data.append(min_time)

                        if objective == 'min-max':
                            comp_time = float(self._getComputationTime(instance_name=instance_name, objective=objective, numVehicles=numVehicle))
                            data.append(round(comp_time/min_time, 2))

                        if objective == 'p-norm':
                            pNorm = [2,3,5,10]
                            for p in pNorm:
                                comp_time = float(self._getComputationTime(instance_name=instance_name, objective=objective, numVehicles=numVehicle, pNorm=p))
                                data.append(round(comp_time/min_time, 2))

                        if objective in ['eps-fair', 'delta-fair']:
                            fairnessCoefficient = [0.1,0.3,0.5,0.7,0.9] 
                            for fc in fairnessCoefficient:
                                comp_time = float(self._getComputationTime(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc))
                                data.append(round(comp_time/min_time, 2))
                        
                    csv_writer.writerow(data)

    def export_COF_to_csv(self, results_path):

        csv_filename = os.path.join(results_path, 'COF.csv')

        with open(csv_filename, 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
           
            csv_writer.writerow(['Instance Name', 'Number of Vehicles', 'min (cost)', 'minmax ', 'pNorm 2', 'pNorm 3', 'pNorm 5', 'pNorm 10',
                                'epsFair 0.1', 'epsFair 0.3', 'epsFair 0.5', 'epsFair 0.7', 'epsFair 0.9', 'deltaFair 0.1', 'deltaFair 0.3', 'deltaFair 0.5', 'deltaFair 0.7', 'deltaFair 0.9'])  # Write header
            
            data = []
            for instance_name in ['burma14.tsp', 'bays29.tsp', 'eil51.tsp', 'eil76.tsp']:
                for numVehicle in [3,4,5]:
                    data = [instance_name, numVehicle]
                    min_cost = 0
                    for objective in ['min', 'min-max', 'p-norm', 'eps-fair', 'delta-fair']:
                        if objective == 'min':
                            min_cost = float(self._getSumofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle))
                            data.append(min_cost)

                        if objective == 'min-max':
                            cost = float(self._getSumofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle))
                            data.append(round((cost-min_cost)/min_cost, 2))

                        if objective == 'p-norm':
                            pNorm = [2,3,5,10]
                            for p in pNorm:
                                cost = float(self._getSumofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle, pNorm=p))
                                data.append(round((cost-min_cost)/min_cost, 2))

                        if objective in ['eps-fair', 'delta-fair']:
                            fairnessCoefficient = [0.1,0.3,0.5,0.7,0.9] 
                            for fc in fairnessCoefficient:
                                cost = float(self._getSumofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc))
                                data.append(round((cost-min_cost)/min_cost, 2))
                        
                    csv_writer.writerow(data)



def main():
    logging.basicConfig(format='%(asctime)s %(levelname)s--: %(message)s',
                        level=logging.DEBUG)

    try:
        folder_path = os.path.dirname(os.path.realpath(__file__))
        base_path = os.path.abspath(os.path.join(folder_path, '..'))
        results_path = os.path.join(base_path, 'results')
        db_path = os.path.join(results_path, 'results.db')
        
        csv_filename = os.path.join(results_path,'table1.csv') 
        dataTransfer = databaseToCSV(db_path)
        # dataTransfer.export_computation_time_to_csv(results_path=results_path, table_objective='p-norm')
        # dataTransfer.export_computation_time_to_csv(results_path=results_path, table_objective='eps-fair')
        # dataTransfer.export_computation_time_to_csv(results_path=results_path, table_objective='delta-fair')
        dataTransfer.export_COF_to_csv(results_path=results_path)
        dataTransfer._closeConnection()
    
    
    except ScriptException as se:
        log.error(se)


if __name__ == '__main__':
    main()