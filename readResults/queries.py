import sqlite3, logging, argparse, ast, re
import csv, os, numpy as np
from math import ceil, floor
import sys

# Add the script_generator path to sys.path to import the function
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'app', 'src', 'main', 'postProcessing', 'runGenerator'))
from script_generator import get_all_instance_vehicle_pairs, get_data_path

log = logging.getLogger(__name__)

class ScriptException(Exception):
    """Custom exception class with message for this module."""

    def __init__(self, value):
        self.value = value
        super().__init__(value)

    def __repr__(self):
        return repr(self.value)


def _parse_runtime_cell(value):
    """
    Parse a single runtime cell from the exported CSVs.

    Returns:
        None: if missing / not applicable (e.g., '-')
        ("timeout", None): if value indicates timeout (e.g., 'TO (0.34)')
        ("solved", float_seconds): if solved within time limit
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return ("solved", float(value))

    s = str(value).strip()
    if s == "" or s == "-":
        return None
    if s.startswith("TO"):
        return ("timeout", None)

    try:
        return ("solved", float(s))
    except ValueError:
        # Unexpected string; treat as missing to avoid breaking aggregation.
        return None


def _read_runtime_entries(csv_path, logical_column_name):
    """
    Read a given logical column (name compared after .strip()) and return entries:
    - ("solved", t) for numeric t
    - ("timeout", None) for timeouts
    Missing values ('-') are skipped.
    """
    entries = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return entries

        # Map stripped header -> actual header (handles 'minmax ' vs 'minmax')
        header_map = {h.strip(): h for h in reader.fieldnames}
        if logical_column_name not in header_map:
            raise ValueError(
                f"Column '{logical_column_name}' not found in {csv_path}. "
                f"Available columns: {list(header_map.keys())}"
            )
        col = header_map[logical_column_name]

        for row in reader:
            parsed = _parse_runtime_cell(row.get(col))
            if parsed is None:
                continue
            entries.append(parsed)
    return entries


def _runtime_stats(entries, tmax_s=3600.0, par_k=1.0):
    """
    Compute runtime stats.

    - solved / timeout are counted over all valid entries (solved + timeout)
    - median/P25/P75 are computed on solved instances only
    - PAR-k uses penalty par_k * tmax_s for each timeout
    """
    n = len(entries)
    if n == 0:
        return {
            "solved": 0,
            "timeout_pct": 0.0,
            "median_s": None,
            "p25_s": None,
            "p75_s": None,
            "par_s": None,
            "n": 0,
            "timeouts": 0,
        }

    solved_times = [t for status, t in entries if status == "solved" and t is not None]
    timeouts = sum(1 for status, _ in entries if status == "timeout")

    solved = len(solved_times)
    timeout_pct = (timeouts / n) * 100.0

    if solved_times:
        median_s = float(np.median(solved_times))
        p25_s = float(np.percentile(solved_times, 25))
        p75_s = float(np.percentile(solved_times, 75))
    else:
        median_s = p25_s = p75_s = None

    par_total = sum(solved_times) + timeouts * (par_k * tmax_s)
    par_s = par_total / n

    return {
        "solved": solved,
        "timeout_pct": timeout_pct,
        "median_s": median_s,
        "p25_s": p25_s,
        "p75_s": p75_s,
        "par_s": par_s,
        "n": n,
        "timeouts": timeouts,
    }


def extract_runtime_stats_round2(
    results_round2_dir,
    tmax_s=3600.0,
    par_k=1.0,
    decimals=2,
):
    """
    Aggregate runtime stats across *all instances* (TSP + VRP) for Round-2 runtime CSVs.

    Inputs expected in `results_round2_dir`:
      - delta-fair-tsp.csv, delta-fair-vrp.csv
      - eps-fair-tsp.csv,   eps-fair-vrp.csv
      - p-norm-tsp.csv,     p-norm-vrp.csv

    Returns:
      (header, rows) where rows is a list of dicts with keys matching header.
    """
    p_norm_tsp = os.path.join(results_round2_dir, "p-norm-tsp.csv")
    p_norm_vrp = os.path.join(results_round2_dir, "p-norm-vrp.csv")
    eps_tsp = os.path.join(results_round2_dir, "eps-fair-tsp.csv")
    eps_vrp = os.path.join(results_round2_dir, "eps-fair-vrp.csv")
    delta_tsp = os.path.join(results_round2_dir, "delta-fair-tsp.csv")
    delta_vrp = os.path.join(results_round2_dir, "delta-fair-vrp.csv")

    def combined_entries(csv_a, csv_b, logical_col):
        return _read_runtime_entries(csv_a, logical_col) + _read_runtime_entries(csv_b, logical_col)

    # Row definitions (logical column names must match after stripping CSV headers)
    rows_spec = []
    rows_spec.append(("min", (p_norm_tsp, p_norm_vrp, "min (sec)")))
    rows_spec.append(("minmax", (p_norm_tsp, p_norm_vrp, "minmax")))
    for p in [2, 3, 5, 10]:
        rows_spec.append((f"pNorm {p}", (p_norm_tsp, p_norm_vrp, f"pNorm {p}")))
    for eps in [0.1, 0.3, 0.5, 0.7, 0.9]:
        rows_spec.append((f"epsFair {eps}", (eps_tsp, eps_vrp, f"epsFair {eps}")))
    for delta in [0.1, 0.3, 0.5, 0.7, 0.9]:
        rows_spec.append((f"deltaFair {delta}", (delta_tsp, delta_vrp, f"deltaFair {delta}")))

    header = ["formulation", "solved", "timeout", "median", "P25", "P75", "PAR1"]
    rows = []

    for formulation, (csv_a, csv_b, logical_col) in rows_spec:
        entries = combined_entries(csv_a, csv_b, logical_col)
        stats = _runtime_stats(entries, tmax_s=tmax_s, par_k=par_k)

        def fmt(x):
            if x is None:
                return "-"
            return round(float(x), decimals)

        rows.append(
            {
                "formulation": formulation,
                "solved": int(stats["solved"]),
                "timeout (%)": fmt(stats["timeout_pct"]),
                "median (s)": fmt(stats["median_s"]),
                "P25 (s)": fmt(stats["p25_s"]),
                "P75 (s)": fmt(stats["p75_s"]),
                "PAR-1 (s)": fmt(stats["par_s"]),
            }
        )

    return header, rows


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

    def _getGapToOpt(self, instance_name, objective, numVehicles, pNorm = 1, fc = 0.0):
        self.cursor.execute(f"""
            SELECT GapToOpt
            FROM {'vehi'+str(numVehicles)}
            WHERE instanceName = ? AND numVehicles = ? AND objective = ? AND pNorm = ? AND fairnessCoefficient = ?
        """, (instance_name, str(numVehicles), objective, str(pNorm), str(fc)))
        result = self.cursor.fetchone()
        if not result:
            return None
        try:
            return round(float(result[0]), 2)
        except (TypeError, ValueError):
            return result[0]

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

    def _getMaxTourLength(self, instance_name, objective, numVehicles, pNorm=1, fc=0.0):
        lengthOfTours = self._getLengthofTours(
            instance_name=instance_name,
            objective=objective,
            numVehicles=numVehicles,
            pNorm=pNorm,
            fc=fc,
        )
        if not lengthOfTours:
            return None
        return round(max(lengthOfTours), 1)

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

        csv_filename_tsp = os.path.join(self.results_path, table_objective + '-tsp.csv')
        csv_filename_vrp = os.path.join(self.results_path, table_objective + '-vrp.csv')

        header = None
        if table_objective == 'p-norm':
            header = ['Instance Name', 'Number of Vehicles', 'min (sec)', 'minmax ', 'pNorm 2', 'pNorm 3', 'pNorm 5', 'pNorm 10']
        elif table_objective == 'eps-fair':
            header = ['Instance Name', 'Number of Vehicles', 'min (sec)', 'minmax', 'epsFair 0.1', 'epsFair 0.3', 'epsFair 0.5', 'epsFair 0.7', 'epsFair 0.9']
        elif table_objective == 'delta-fair':
            header = ['Instance Name', 'Number of Vehicles', 'min (sec)', 'minmax', 'deltaFair 0.1', 'deltaFair 0.3', 'deltaFair 0.5', 'deltaFair 0.7', 'deltaFair 0.9']
        else:
            raise ValueError(f"Unsupported table_objective: {table_objective}")

        with (
            open(csv_filename_tsp, 'w', newline='') as tsp_csvfile,
            open(csv_filename_vrp, 'w', newline='') as vrp_csvfile,
        ):
            tsp_writer = csv.writer(tsp_csvfile)
            vrp_writer = csv.writer(vrp_csvfile)
            tsp_writer.writerow(header)
            vrp_writer.writerow(header)

            # Get all instance-vehicle pairs using the shared function
            data_path = get_data_path()
            instance_vehicle_pairs = get_all_instance_vehicle_pairs(data_path)

            for instance_name, numVehicle in instance_vehicle_pairs:
                is_tsp = instance_name.endswith('.tsp')
                is_vrp = instance_name.endswith('.vrp')
                if not (is_tsp or is_vrp):
                    continue

                data = [instance_name.split(".")[0], numVehicle]
                min_time = 0
                for objective in ['min', 'min-max', table_objective]:
                    if objective == 'min':
                        min_time_raw = self._getComputationTime(instance_name=instance_name, objective=objective, numVehicles=numVehicle)
                        min_time = float(min_time_raw) if min_time_raw is not None else None
                        data.append(min_time if min_time is not None else '-')

                    if objective == 'min-max':
                        comp_time_raw = self._getComputationTime(instance_name=instance_name, objective=objective, numVehicles=numVehicle)
                        if comp_time_raw is None:
                            data.append('-')
                        else:
                            comp_time = float(comp_time_raw)
                            if comp_time < 3600:
                                data.append(round(comp_time, 2))
                            else:
                                gap = self._getGapToOpt(instance_name=instance_name, objective=objective, numVehicles=numVehicle)
                                data.append(f"TO ({gap})" if gap is not None else "TO (-)")

                    if objective == 'p-norm':
                        pNorm = [2, 3, 5, 10]
                        for p in pNorm:
                            comp_time_raw = self._getComputationTime(instance_name=instance_name, objective=objective, numVehicles=numVehicle, pNorm=p)
                            if comp_time_raw is None:
                                data.append('-')
                            else:
                                comp_time = float(comp_time_raw)
                                if comp_time < 3600:
                                    data.append(round(comp_time, 2))
                                else:
                                    gap = self._getGapToOpt(instance_name=instance_name, objective=objective, numVehicles=numVehicle, pNorm=p)
                                    data.append(f"TO ({gap})" if gap is not None else "TO (-)")

                    if objective in ['eps-fair', 'delta-fair']:
                        fairnessCoefficient = [0.1, 0.3, 0.5, 0.7, 0.9]
                        for fc in fairnessCoefficient:
                            comp_time_raw = self._getComputationTime(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                            if comp_time_raw is None:
                                data.append('-')
                            else:
                                comp_time = float(comp_time_raw)
                                if comp_time < 3600:
                                    data.append(round(comp_time, 2))
                                else:
                                    gap = self._getGapToOpt(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                                    data.append(f"TO ({gap})" if gap is not None else "TO (-)")

                (tsp_writer if is_tsp else vrp_writer).writerow(data)

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
            csv_writer.writerow(['Instance Name', 'Number of Vehicles', 'minmax cost', 'minmaxCOF', 'minmax eps', 'minmax delta', 'max_tour_min_max',
                                 'epsFair cost', 'epsFair COF', 'max_tour_epsFair', 'deltaFair cost', 'deltaFair COF', 'max_tour_deltaFair' ])

            data = []
            data_path = get_data_path()
            instance_vehicle_pairs = get_all_instance_vehicle_pairs(data_path)

            for instance_name, numVehicle in instance_vehicle_pairs:

                min_cost = self._getSumofTours(instance_name=instance_name, objective='min', numVehicles=numVehicle)

                min_max_comp_time = self._getComputationTime(instance_name=instance_name, objective='min-max', numVehicles=numVehicle)
                if float(min_max_comp_time) > 3600:
                    continue
                minmax_cost = self._getSumofTours(instance_name=instance_name, objective='min-max', numVehicles=numVehicle)
                minmax_fairnessIndex = self._getFairnessIndex(instance_name=instance_name, objective='min-max', numVehicles=numVehicle)
                max_tour_min_max = self._getMaxTourLength(
                    instance_name=instance_name,
                    objective='min-max',
                    numVehicles=numVehicle,
                )
                data = [
                    instance_name.split(".")[0],
                    numVehicle,
                    minmax_cost,
                    round((minmax_cost - min_cost) / min_cost, 3),
                    round(minmax_fairnessIndex['normIndex'], 5),
                    round(minmax_fairnessIndex['giniIndex'], 5),
                    max_tour_min_max
                ]

                max_tour_epsFair = None
                max_tour_deltaFair = None

                for objective in ['eps-fair', 'delta-fair']:
                    if objective == 'eps-fair':
                        fc = round(floor(float(minmax_fairnessIndex['normIndex'])*10000)/10000,4)
                        eps_comp_time = self._getComputationTime(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                        cost = self._getSumofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                        max_tour_epsFair = self._getMaxTourLength(
                            instance_name=instance_name,
                            objective=objective,
                            numVehicles=numVehicle,
                            fc=fc,
                        )
                        if float(eps_comp_time) > 3600:
                            data.extend(['-', '-', '-'])
                        else:
                            data.extend([cost, round((cost-min_cost)/min_cost, 3), max_tour_epsFair])
                    if objective == 'delta-fair':
                        fc = round(ceil(float(minmax_fairnessIndex['giniIndex'])*10000)/10000,4)
                        delta_comp_time = self._getComputationTime(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                        cost = self._getSumofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                        max_tour_deltaFair = self._getMaxTourLength(
                            instance_name=instance_name,
                            objective=objective,
                            numVehicles=numVehicle,
                            fc=fc,
                        )
                        if float(delta_comp_time) > 3600:
                            data.extend(['-', '-', '-'])
                        else:
                            data.extend([cost, round((cost-min_cost)/min_cost, 3), max_tour_deltaFair] )
                
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
            csv_writer.writerow(['Instance Name', 'Number of Vehicles', 'min-max cov', 'p-norm 2 cov', 'p-norm 3 cov', 'p-norm 5 cov', 'p-norm 10 cov', 'eps-fair 0.1 cov', 'eps-fair 0.3 cov', 'eps-fair 0.5 cov', 'eps-fair 0.7 cov', 'eps-fair 0.9 cov', 'eps-fair min-max cov', 'delta-fair min-max cov', 'delta-fair 0.1 cov', 'delta-fair 0.3 cov', 'delta-fair 0.5 cov', 'delta-fair 0.7 cov', 'delta-fair 0.9 cov'])

            data_path = get_data_path()
            instance_vehicle_pairs = get_all_instance_vehicle_pairs(data_path)
            for instance_name, numVehicle in instance_vehicle_pairs:
                min_max_comp_time = self._getComputationTime(instance_name=instance_name, objective='min-max', numVehicles=numVehicle)
                if float(min_max_comp_time) > 3600:
                    continue
                data = [instance_name.split(".")[0], numVehicle]
                for objective in ['min-max', 'p-norm', 'eps-fair', 'delta-fair']:

                    if objective == 'min-max':
                        lengthOfTours = self._getLengthofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle)
                        data.append(self._getCoefficientOfVariation(lengthOfTours))

                    if objective == 'p-norm':
                        for p in [2,3,5,10]:
                            lengthOfTours = self._getLengthofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle, pNorm=p)
                            data.append(self._getCoefficientOfVariation(lengthOfTours))

                    if objective in ['eps-fair', 'delta-fair']:
                        minmax_fairnessIndex = self._getFairnessIndex(instance_name=instance_name, objective='min-max', numVehicles=numVehicle)
                        if objective == 'eps-fair':
                            min_max_eps = round(floor(float(minmax_fairnessIndex['normIndex'])*10000)/10000,4) 
                            fairnessCoefficient = [0.1,0.3,0.5,0.7,0.9, min_max_eps]
                        if objective == 'delta-fair':
                            min_max_delta = round(ceil(float(minmax_fairnessIndex['giniIndex'])*10000)/10000,4)
                            fairnessCoefficient = [min_max_delta,0.1,0.3,0.5,0.7,0.9]

                        for fc in fairnessCoefficient: 
                            lengthOfTours = self._getLengthofTours(instance_name=instance_name, objective=objective, numVehicles=numVehicle, fc=fc)
                            print(fc, self._getCoefficientOfVariation(lengthOfTours))
                            data.append(self._getCoefficientOfVariation(lengthOfTours))

                csv_writer.writerow(data)
    
    def export_runtime_stats_to_csv(self):
        header, rows = extract_runtime_stats_round2(self.results_path)
        out_path = os.path.join(self.results_path, "runtime_stats.csv")

        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

        return out_path


def handle_command_line():
    parser = argparse.ArgumentParser()

    parser.add_argument("-t", "--tableName", choices=['runtime_pNorm', 'runtime_epsFair', 'runtime_deltaFair', 'runtime_stats', 'COF', 'minmaxFair', 'pNormFair', 'ParetoFront', 'COV'],
                        help="give the table name", type=str)

    args = parser.parse_args()

    return args.tableName

def main():
    logging.basicConfig(format='%(asctime)s %(levelname)s--: %(message)s',
                        level=logging.DEBUG)

    try:
        folder_path = os.path.dirname(os.path.realpath(__file__))
        base_path = os.path.abspath(os.path.join(folder_path, '..'))
        results_path = os.path.join(base_path, 'results/round-2')
        db_path = os.path.join(results_path, 'results.db')

        tableName = handle_command_line()
        dataTransfer = databaseToCSV(db_path, results_path)

        if tableName == 'runtime_pNorm':
            dataTransfer.export_computation_time_to_csv(table_objective='p-norm')
        elif tableName == 'runtime_epsFair':
            dataTransfer.export_computation_time_to_csv(table_objective='eps-fair')
        elif tableName == 'runtime_deltaFair':
            dataTransfer.export_computation_time_to_csv(table_objective='delta-fair')
        elif tableName == 'runtime_stats':
            dataTransfer.export_runtime_stats_to_csv()
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
