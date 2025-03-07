import sqlite3, logging, argparse, ast
import csv, os, numpy as np
from math import ceil, floor

log = logging.getLogger(__name__)

class ScriptException(Exception):
    """Custom exception class with message for this module."""

    def __init__(self, value):
        self.value = value
        super().__init__(value)

    def __repr__(self):
        return repr(self.value)


class databaseToCSV():
    def __init__(self, database_path, results_path) -> None:
        self.connection = sqlite3.connect(database_path)
        self.cursor = self.connection.cursor()
        self.results_path = results_path

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
        return round(float(result[0]),1) if result else None 
    
    def _getLengthofTours(self, instance_name, objective, numVehicles, pNorm = 1, fc = 0.0):
        self.cursor.execute(f"""
            SELECT LengthOfTours
            FROM {'vehi'+str(numVehicles)}
            WHERE instanceName = ? AND numVehicles = ? AND objective = ? AND pNorm = ? AND fairnessCoefficient = ?
        """, (instance_name, str(numVehicles), objective, str(pNorm), str(fc)))
        result = self.cursor.fetchone()
        if result:
            result = ast.literal_eval(result[0])
        return [round(abs(len),1) for len in result] if result else None 

    def _getFairnessIndex(self, instance_name, numVehicles, objective, pNorm = 1, fc = 0.0):
        # returns jainIndex, giniIndex and normIndex corresponding to given instance 
        self.cursor.execute(f"""
                SELECT GiniIndex, JainIndex, normIndex
                FROM {'vehi'+str(numVehicles)}
                WHERE instanceName = ? AND numVehicles = ? AND objective = ? AND pNorm = ? AND fairnessCoefficient = ?
                """,  (instance_name, str(numVehicles), objective, str(pNorm), str(fc)))
        result = self.cursor.fetchone()
        fairIndex = {'giniIndex': float(result[0]), 'jainIndex':float(result[1]), 'normIndex':float(result[2])} if result else None 
        return fairIndex
    
    def _getMinParam(self, instance_name, numVehicles, objective):
        self.cursor.execute(f"""
            SELECT MIN(fairnessCoefficient)
            FROM {'vehi'+str(numVehicles)}
            WHERE instanceName = ? AND numVehicles = ? AND objective = ?
        """, (instance_name, str(numVehicles), objective))
        result = self.cursor.fetchone()
        return round(float(result[0]),4) if result else None
    
    def _getMaxParam(self, instance_name, numVehicles, objective):
        self.cursor.execute(f"""
            SELECT MAX(fairnessCoefficient)
            FROM {'vehi'+str(numVehicles)}
            WHERE instanceName = ? AND numVehicles = ? AND objective = ?
        """, (instance_name, str(numVehicles), objective))
        result = self.cursor.fetchone()
        return round(float(result[0]),4) if result else None
    
    def _getCoefficientOfVariation(self, lengthOfTours):
        mean = np.mean(lengthOfTours)
        std = np.std(lengthOfTours)
        return round(std/mean, 3)

    def export_computation_time_to_csv(self, table_objective):

        csv_filename = os.path.join(self.results_path, table_objective+'.csv')

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
                    data = [instance_name.split(".")[0], numVehicle]
                    min_time = 0
                    for objective in ['min', 'min-max', table_objective]:
                        if objective == 'min':
                            min_time = float(self._getComputationTime(instance_name=instance_name, objective=objective, numVehicles=numVehicle))
                            data.append(min_time)

                        if objective == 'min-max':
                            comp_time = float(self._getComputationTime(instance_name=instance_name, objective=objective, numVehicles=numVehicle))
                            # data.append(round(comp_time/min_time, 2)) if comp_time<3600 else data.append('-')
                            data.append(round(comp_time,2)) if comp_time<3600 else data.append('-')


                        if objective == 'p-norm':
                            pNorm = [2,3,5,10]
                            for p in pNorm:
                                comp_time = float(self._getComputationTime(instance_name=instance_name, objective=objective, numVehicles=numVehicle, pNorm=p))
                                # data.append(round(comp_time/min_time, 2)) if comp_time<3600 else data.append('-')
                                data.append(round(comp_time,2)) if comp_time<3600 else data.append('-')

                        if objective in ['eps-fair', 'delta-fair']:
                            fairnessCoefficient = [0.1,0.3,0.5,0.7,0.9] 
                            for fc in fairnessCoefficient:
                                comp_time = float(self._getComputationTime(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc))
                                # data.append(round(comp_time/min_time, 2)) if comp_time<3600 else data.append('-')
                                data.append(round(comp_time,2)) if comp_time<3600 else data.append('-')
                        
                    csv_writer.writerow(data)

    def export_all_COF_to_csv(self):
        '''Not used in the paper'''
        csv_filename = os.path.join(self.results_path, 'allCOF.csv')

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
    
    def export_COF_plotdata(self):

        csv_filename = os.path.join(self.results_path, 'COF_plotdata.csv')

        with open(csv_filename, 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            instance_name = 'eil51.tsp'
            numVehicle = 5
            min_cost = self._getSumofTours(instance_name=instance_name, objective='min', numVehicles=numVehicle)
            minmax_cost = self._getSumofTours(instance_name=instance_name, objective='min-max', numVehicles=numVehicle)
            minmax_COF = round((minmax_cost-min_cost)/min_cost, 2)
            csv_writer.writerows([['instanceName', instance_name], ['numVehicles', numVehicle ], 
                                  ['minmaxCOF', minmax_COF],['fairnessCoefficient', 'epsCOF', 'deltaCOF']])

            fairnessCoefficient = [round(x,2) for x in np.arange(0,1,0.05)]

            for fc in fairnessCoefficient:
                data = [fc]
                for objective in ['eps-fair', 'delta-fair']:   
                    cost = self._getSumofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                    data.append(round((cost-min_cost)/min_cost, 2))
                csv_writer.writerow(data)
        
            csv_writer.writerow([1.0, 0.28, 0.0])

    def export_ParetoFront_plotdata(self):

        csv_filename = os.path.join(self.results_path, 'ParetoFront_plotdata.csv')

        with open(csv_filename, 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            instance_name = 'eil51.tsp'
            numVehicle = 5
            min_cost = self._getSumofTours(instance_name=instance_name, objective='min', numVehicles=numVehicle)
            minmax_cost = self._getSumofTours(instance_name=instance_name, objective='min-max', numVehicles=numVehicle)
            csv_writer.writerows([['instanceName', instance_name], ['numVehicles', numVehicle ], ['minCost', min_cost],
                                  ['minmaxCost', minmax_cost],['fairnessCoefficient', 'epsCost', 'deltaCost']])

            fairnessCoefficient = [round(x,2) for x in np.arange(0,1,0.05)]

            for fc in fairnessCoefficient:
                data = [fc]
                for objective in ['eps-fair', 'delta-fair']:   
                    cost = self._getSumofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                    data.append(round(cost, 2))
                csv_writer.writerow(data)

            csv_writer.writerow([1.0, minmax_cost, min_cost])

    def export_minmaxFair_to_csv(self):
        '''Not used in the paper'''
        csv_filename = os.path.join(self.results_path, 'minmaxFair.csv')

        with open (csv_filename, 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(['Instance Name', 'Number of Vehicles', 'minmax time', 'minmax cost', 'minmax eps', 'minmax delta', 
                                 'epsFair time', 'epsFair cost', 'epsFair fc', 'epsFair eps', 'deltaFair time', 'deltaFair cost', 'deltaFair fc', 'deltaFair delta' ])
            
            data = []
            for instance_name in ['bays29.tsp', 'eil51.tsp', 'eil76.tsp']:
                for numVehicle in [3,4,5]:
                    data = [instance_name, numVehicle]

                    comp_time = self._getComputationTime(instance_name=instance_name, objective='min-max', numVehicles=numVehicle)
                    if float(comp_time) > 3600:
                        continue
                    cost = self._getSumofTours(instance_name=instance_name, objective='min-max', numVehicles=numVehicle)
                    minmax_fairnessIndex = self._getFairnessIndex(instance_name=instance_name, objective='min-max', numVehicles=numVehicle)
                    data = [instance_name, numVehicle, comp_time, cost, round(minmax_fairnessIndex['normIndex'],5), round(minmax_fairnessIndex['giniIndex'],5)]

                    for objective in ['eps-fair', 'delta-fair']:
                        if objective == 'eps-fair':
                            fc = round(floor(float(minmax_fairnessIndex['normIndex'])*10000)/10000,4)
                            comp_time = self._getComputationTime(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                            cost = self._getSumofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                            fairnessIndex = self._getFairnessIndex(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                            data.extend([comp_time, cost, fc, round(fairnessIndex['normIndex'],5)])
                        if objective == 'delta-fair':
                            fc = round(ceil(float(minmax_fairnessIndex['giniIndex'])*10000)/10000,4)
                            comp_time = self._getComputationTime(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                            cost = self._getSumofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                            fairnessIndex = self._getFairnessIndex(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                            data.extend([comp_time, cost, fc, round(fairnessIndex['giniIndex'],5)])

                    csv_writer.writerow(data)

    def export_minmaxFair_final(self):
        csv_filename = os.path.join(self.results_path, 'minmaxFair_final.csv')

        with open (csv_filename, 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(['Instance Name', 'Number of Vehicles', 'minmax cost', 'minmaxCOF', 'minmax eps', 'minmax delta', 
                                 'epsFair cost', 'epsFair COF', 'deltaFair cost', 'deltaFair COF' ])
            
            data = []
            for instance_name in ['burma14.tsp','bays29.tsp', 'eil51.tsp']:
                for numVehicle in [3,4,5]:
                    
                    min_cost = self._getSumofTours(instance_name=instance_name, objective='min', numVehicles=numVehicle)

                    comp_time = self._getComputationTime(instance_name=instance_name, objective='min-max', numVehicles=numVehicle)
                    if float(comp_time) > 3600:
                        continue
                    minmax_cost = self._getSumofTours(instance_name=instance_name, objective='min-max', numVehicles=numVehicle)
                    minmax_fairnessIndex = self._getFairnessIndex(instance_name=instance_name, objective='min-max', numVehicles=numVehicle)
                    data = [instance_name.split(".")[0], numVehicle, minmax_cost, round((minmax_cost-min_cost)/min_cost, 3) ,round(minmax_fairnessIndex['normIndex'],5), round(minmax_fairnessIndex['giniIndex'],5)]

                    for objective in ['eps-fair', 'delta-fair']:
                        if objective == 'eps-fair':
                            fc = round(floor(float(minmax_fairnessIndex['normIndex'])*10000)/10000,4)
                            cost = self._getSumofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                            data.extend([cost, round((cost-min_cost)/min_cost, 3)])
                        if objective == 'delta-fair':
                            fc = round(ceil(float(minmax_fairnessIndex['giniIndex'])*10000)/10000,4)
                            cost = self._getSumofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                            data.extend([cost, round((cost-min_cost)/min_cost, 3)])

                    csv_writer.writerow(data)

    def export_pNormFair_to_csv(self):
        '''Not used in the paper'''
        csv_filename = os.path.join(self.results_path, 'pNormFair.csv')

        with open (csv_filename, 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(['Instance Name', 'Number of Vehicles', '2Norm time', '2Norm cost', '2Norm eps', '2Norm delta', 
                                 'epsFair time', 'epsFair cost', 'epsFair fc', 'epsFair eps', 'deltaFair time', 'deltaFair cost', 'deltaFair fc', 'deltaFair delta' ])
            
            data = []
            for instance_name in ['bays29.tsp', 'eil51.tsp', 'eil76.tsp']:
                for numVehicle in [3,4,5]:

                    comp_time = self._getComputationTime(instance_name=instance_name, objective='p-norm', numVehicles=numVehicle, pNorm=2)
                    if float(comp_time) > 3600:
                        continue
                    cost = self._getSumofTours(instance_name=instance_name, objective='p-norm', numVehicles=numVehicle, pNorm=2)
                    pnorm_fairnessIndex = self._getFairnessIndex(instance_name=instance_name, objective='p-norm', numVehicles=numVehicle, pNorm=2)
                    data = [instance_name, numVehicle, comp_time, cost, round(pnorm_fairnessIndex['normIndex'],5), round(pnorm_fairnessIndex['giniIndex'],5)]

                    for objective in ['eps-fair', 'delta-fair']:
                        if objective == 'eps-fair':
                            fc = round(floor(pnorm_fairnessIndex['normIndex']*10000)/10000,4)
                            comp_time = self._getComputationTime(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                            cost = self._getSumofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                            fairnessIndex = self._getFairnessIndex(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                            data.extend([comp_time, cost, fc, round(fairnessIndex['normIndex'],5)])
                        if objective == 'delta-fair':
                            fc = round(ceil(float(pnorm_fairnessIndex['giniIndex'])*10000)/10000,4)
                            comp_time = self._getComputationTime(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                            cost = self._getSumofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                            fairnessIndex = self._getFairnessIndex(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                            data.extend([comp_time, cost, fc, round(fairnessIndex['giniIndex'],5)])

                    csv_writer.writerow(data)

    def export_coeff_variation(self):
        csv_filename = os.path.join(self.results_path, 'coeffVariation.csv')

        with open (csv_filename, 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(['Instance Name', 'Number of Vehicles', 'objective', 'parameter', 'l1', 'l2', 'l3', 'l4', 'Coeff Variation'])
            
            data = []
            for instance_name in ['burma14.tsp', 'bays29.tsp', 'eil51.tsp']:
                numVehicle = 4
                for objective in ['min', 'min-max', 'p-norm', 'eps-fair', 'delta-fair']:
                    
                    if objective in ['min', 'min-max']:
                        data = [instance_name.split(".")[0], numVehicle]
                        data.extend([objective, '-'])
                        lengthOfTours = self._getLengthofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle)
                        data.extend(lengthOfTours)
                        data.append(self._getCoefficientOfVariation(lengthOfTours))
                        csv_writer.writerow(data)

                    if objective == 'p-norm':
                        pNorm = [2,3,5,10]
                        for p in pNorm:
                            data = [instance_name.split(".")[0], numVehicle]
                            data.extend([objective, p])
                            lengthOfTours = self._getLengthofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle, pNorm=p)
                            data.extend(lengthOfTours)
                            data.append(self._getCoefficientOfVariation(lengthOfTours))
                            csv_writer.writerow(data)

                    if objective in ['eps-fair', 'delta-fair']:
                        if objective == 'eps-fair':
                            fairnessCoefficient = [0.1,0.3,0.5,0.7,0.9, self._getMaxParam(instance_name, numVehicle, objective)]
                        if objective == 'delta-fair':
                            fairnessCoefficient = [self._getMinParam(instance_name, numVehicle, objective) , 0.1,0.3,0.5,0.7,0.9] 
                        
                        for fc in fairnessCoefficient:
                            data = [instance_name.split(".")[0], numVehicle, objective, fc]        
                            lengthOfTours = self._getLengthofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                            data.extend(lengthOfTours)
                            data.append(self._getCoefficientOfVariation(lengthOfTours))
                    
                            csv_writer.writerow(data)




def handle_command_line():
    parser = argparse.ArgumentParser()

    parser.add_argument("-tableName", "--tableName", choices=['runtime_pNorm', 'runtime_epsFair', 'runtime_deltaFair', 'COF', 'minmaxFair', 'pNormFair', 'ParetoFront', 'COV'],
                        help="give the table name", type=str)
    
    args = parser.parse_args()

    return args.tableName

def main():
    logging.basicConfig(format='%(asctime)s %(levelname)s--: %(message)s',
                        level=logging.DEBUG)

    try:
        folder_path = os.path.dirname(os.path.realpath(__file__))
        base_path = os.path.abspath(os.path.join(folder_path, '..'))
        results_path = os.path.join(base_path, 'results')
        db_path = os.path.join(results_path, 'results.db')
        
        tableName = handle_command_line()
        dataTransfer = databaseToCSV(db_path, results_path)
        
        if tableName == 'runtime_pNorm':
            dataTransfer.export_computation_time_to_csv(table_objective='p-norm')
        elif tableName == 'runtime_epsFair':
            dataTransfer.export_computation_time_to_csv(table_objective='eps-fair')
        elif tableName == 'runtime_deltaFair':
            dataTransfer.export_computation_time_to_csv(table_objective='delta-fair')
        elif tableName == 'COF':
            dataTransfer.export_COF_plotdata()
        elif tableName == 'minmaxFair':
            dataTransfer.export_minmaxFair_final()
        elif tableName == 'pNormFair':
            dataTransfer.export_pNormFair_to_csv()
        elif tableName == 'ParetoFront':    
            dataTransfer.export_ParetoFront_plotdata()
        elif tableName == 'COV':
            dataTransfer.export_coeff_variation()
        
        dataTransfer._closeConnection()
    
    
    except ScriptException as se:
        log.error(se)


if __name__ == '__main__':
    main()
