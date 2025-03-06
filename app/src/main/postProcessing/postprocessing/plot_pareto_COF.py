import csv, os
import matplotlib
import matplotlib.pyplot as plt
import argparse, logging, subprocess


log = logging.getLogger(__name__)

class PlotException(Exception):
    """Custom exception class with message for this module."""

    def __init__(self, value):
        self.value = value
        super().__init__(value)

    def __repr__(self):
        return repr(self.value)


def handle_command_line():
    """function to manage command line arguments """
    parser = argparse.ArgumentParser() 
    parser.add_argument('-t', '--target', choices=['paper', 'presentation'], 
                        help='paper/presentation', type=str, default='paper')
    parser.add_argument('-g', '--plotgrid', action='store_true',
                        help='generate the grid plot')
    parser.add_argument('-c', '--pdfcrop', action='store_true', 
                        help='crop figures after generating them')
    parser.add_argument('-o', '--option', choices=['all', 'COF', 'paretoFront'],
                        help='plot all/COF/paretoFront')
    config = parser.parse_args()
    return config


class Controller: 
    """class that manages the functionality of the entire plotting script"""
    
    def __init__(self, config):
        self.config = config

    @staticmethod
    def get_plot_params(target):
        if target == 'paper':
            return {
                'fig_size': (4, 3)
            }
        else: 
            return {
                'fig_size': (4, 3)
            }
        

    @staticmethod
    def get_base_path():
        return os.path.abspath(os.path.join(os.path.dirname(__file__) , '../../../../..'))
    
    @staticmethod
    def get_data_file_path(basepath):
        return os.path.join(basepath, 'results', 'COF_plotdata.csv')
    
    @staticmethod 
    def crop(file): 
        log.info(f'cropping figure {file}')
        subprocess.run(['pdfcrop', f'{file}.pdf'])
        subprocess.run(['rm', '-rf', f'{file}.pdf'])
        subprocess.run(['mv', f'{file}-crop.pdf', f'{file}.pdf'])
        log.info(f'cropping figure {file} complete')
    
    def _set_rc_params(self):
        if self.config.target == 'paper':
            matplotlib.rcParams.update({
                'text.usetex': True,
                'font.family': 'serif',
                'text.latex.preamble': r'\usepackage[scaled=0.9]{newpxtext}\usepackage[scaled=0.9]{newpxmath}\usepackage{bm}',
                'font.size' : 10,
                'pgf.rcfonts': False,
                })
        else: 
            matplotlib.rcParams.update({
                'text.usetex': True,
                'font.family': 'sans-serif',
                'text.latex.preamble': r'\usepackage{sourcesanspro,eulervm}',
                'font.size' : 11,
                'pgf.rcfonts': False,
                })

    def plot(self):
        if self.config.option == 'COF':
            self.plot_cof()
        elif self.config.option == 'paretoFront':
            self.plot_pareto_front()
        else:    
            self.plot_cof()
            self.plot_pareto_front()

    def get_cof_data(self):
        COF_filepath = self.get_data_file_path(self.get_base_path())
        fairness_coefficient = []
        eps_cof = []
        delta_cof = []
        minmax_cof = None

        with open(COF_filepath, 'r') as file:
            reader = csv.reader(file, delimiter=',')
            for row in reader:
                if row[0] == 'minmaxCOF':
                    minmax_cof = float(row[1])
                
                elif row[0][0] in ['0','1'] :
                    fairness_coefficient.append(float(row[0]))
                    eps_cof.append(float(row[1]))
                    delta_cof.append(float(row[2]))
        eps_cof[-1] = minmax_cof
        delta_cof[0] = minmax_cof

        return fairness_coefficient, eps_cof, delta_cof, minmax_cof
        
    def plot_cof(self):
        fairness_coefficient, eps_cof, delta_cof, minmax_cof = self.get_cof_data()
        fig, ax = plt.subplots()
        params = self.get_plot_params(self.config.target)
        fs=params['fig_size']
        fig.set_size_inches(fs[0], fs[1])
        fig.set_size_inches(3,3)
        ax.grid(alpha=0.1)
        ax.grid(alpha=0.1)
        ax.plot(fairness_coefficient, eps_cof, color = 'xkcd:green', 
                linestyle='-', marker = '.', markersize = 1.8, linewidth = 1, 
                label=r'COF$(\mathcal{F}^{\varepsilon})$')
        ax.plot(fairness_coefficient, delta_cof, color = 'xkcd:rose', 
                linestyle='dashdot', marker = '.', markersize = 1.8, linewidth = 1, 
                label=r'COF$(\mathcal{F}^{\Delta})$')

        # Plot the constant line for minmax_cof
        ax.axhline(y=minmax_cof, color='xkcd:orange', linestyle='--', linewidth = 1, label=r'COF$(\mathcal{F}_{\infty})$')

        plt.xlabel(r'$\varepsilon, \Delta$')
        plt.ylabel('Cost of Fairness')
        if self.config.target == 'presentation':
            plt.legend(loc='best', frameon=False, bbox_to_anchor=(0.55, 0.9))
        else:
            plt.legend(loc='best', frameon=False, fontsize=9, bbox_to_anchor=(0.55, 0.5))
        plt.tight_layout()       
        plt.grid(True)
        filename = f'../plots/{self.config.target}/COF'
        plt.savefig(f'{filename}.pdf', format='pdf')
        self.crop(filename)
    
    def get_pareto_front_data(self):
        pareto_front_filepath = os.path.join(self.get_base_path(), 'results', 'ParetoFront_plotdata.csv') 
        fairness_coefficient = []
        eps_cost = []
        delta_cost = []
        minmax_cost = None
        min_cost = None

        with open(pareto_front_filepath, 'r') as file:
            reader = csv.reader(file, delimiter=',')
            for row in reader:
                if row[0] == 'minmaxCost':
                    minmax_cost = float(row[1])
                
                elif row[0] == 'minCost':
                    min_cost = float(row[1])

                elif row[0][0] in ['0','1'] :
                    fairness_coefficient.append(float(row[0]))
                    eps_cost.append(float(row[1]))
                    delta_cost.append(float(row[2]))
        
        delta_cost[0] = minmax_cost
        eps_cost[-1] = minmax_cost

        return fairness_coefficient, eps_cost, delta_cost, minmax_cost, min_cost
    
    def plot_pareto_front(self):
        fairness_coefficient, eps_cost, delta_cost, minmax_cost, min_cost = self.get_pareto_front_data()
        fig, ax = plt.subplots()
        params = self.get_plot_params(self.config.target)
        fs = params['fig_size']
        fig.set_size_inches(fs[0], fs[1])
        # fig.set_size_inches(6,4)
        ax.grid(alpha=0.1)
        ax.plot(fairness_coefficient, eps_cost, color = 'xkcd:green', 
                linestyle='-', marker = '.', markersize = 1.8, linewidth = 1, 
                label=r'$\left(\mathcal{F}^{\varepsilon}_{\mathrm{bi-obj}}\right)$')
        ax.plot(fairness_coefficient, delta_cost, color = 'xkcd:rose', 
                linestyle='dashdot', marker = '.', markersize = 1.8, linewidth = 1, 
                label=r'$\left(\mathcal{F}^{\Delta}_{\mathrm{bi-obj}}\right)$')
        # where = 'post')

        # Plot the constant line for minmax_cof
        ax.axhline(y=minmax_cost, color='xkcd:orange', linestyle=':', linewidth = 1, label=r'$(\mathcal{F}_{\infty})$')
        ax.axhline(y=min_cost, color='xkcd:bright red', linestyle='--', linewidth = 1, label=r'$(\mathcal{F}_1)$')

        plt.xlabel(r'$\varepsilon\mathrm{FI}(\bm l), \mathrm{GC}(\bm l)$', fontsize = 12)
        plt.ylabel(r'$$\left(\sum_{1 \leqslant v \leqslant m} l_v\right)$$', fontsize = 12, rotation=0)
        ax.yaxis.set_label_coords(-0.3, 0.4)
        plt.legend(loc='upper center', bbox_to_anchor=(0.55, 0.99), frameon=False)
        plt.tight_layout()       
        plt.grid(True)
        
        filename = f'../plots/{self.config.target}/paretoFront'
        plt.savefig(f'{filename}.pdf', format='pdf')
        self.crop(filename)


def main():
    logging.basicConfig(format='%(asctime)s %(levelname)s--: %(message)s',
                        level=logging.INFO)
    
    try:
        config = handle_command_line()
        controller = Controller(config)
        controller._set_rc_params()
        controller.plot()
    except PlotException as pe:
        log.error(pe)

if __name__ == "__main__":
    main()