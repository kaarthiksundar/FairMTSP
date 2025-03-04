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
                        help='paper/presentation', type=str)
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
                'fig_size': (3.5, 2.5)
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
            self.plotCOF()
        elif self.config.option == 'paretoFront':
            self.plotParetoFront()
        else:    
            self.plotCOF()
            self.plotParetoFront()

    def getCOFData(self):
        COF_filepath = self.getDataFilepath(self.getbasepath())
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
                    epsCOF.append(float(row[1]))
                    deltaCOF.append(float(row[2]))
        epsCOF[-1] = minmaxCOF
        deltaCOF[0] = minmaxCOF

        return fairness_coefficient, epsCOF, deltaCOF, minmaxCOF
        
    def plotCOF(self):

        fairness_coefficient, epsCOF, deltaCOF, minmaxCOF = self.getCOFData()
        fig, ax = plt.subplots()
        params = self.get_plot_params(self.config.target)
        fs=params['fig_size']
        # fig.set_size_inches(fs[0], fs[1])
        fig.set_size_inches(6,4)
        ax.step(fairness_coefficient, epsCOF, color='g', linestyle='-', marker = 'o', label=r'COF$(\mathcal{F}^{\varepsilon})$')
        ax.step(fairness_coefficient, deltaCOF, color='r', linestyle='dashdot', marker = 'o', label=r'COF$(\mathcal{F}^{\Delta})$', where = 'post')

        # Plot the constant line for minmaxCOF
        ax.axhline(y=minmaxCOF, color='b', linestyle='--', label=r'COF$(\mathcal{F}_{\infty})$')

        plt.xlabel(r'$\varepsilon, \Delta$')
        plt.ylabel('Cost of Fairness')
        if self.config.target == 'presentation':
            plt.legend(loc='best', frameon=False, bbox_to_anchor=(0.55, 0.9))
        else:
            plt.legend(loc='best', frameon=False, fontsize=9, bbox_to_anchor=(0.55, 0.5))
        plt.tight_layout()       
        plt.grid(True)
        
        plt.savefig(f'../plots/{self.config.target}/COF.pdf', format='pdf')
    
    def getParetoFrontData(self):
        ParetoFront_filepath = os.path.join(self.getbasepath(), 'results', 'ParetoFront_plotdata.csv') 
        fairness_coefficient = []
        epsCost = []
        deltaCost = []
        minmaxCost = None
        minCost = None

        with open(ParetoFront_filepath, 'r') as file:
            reader = csv.reader(file, delimiter=',')
            for row in reader:
                if row[0] == 'minmaxCost':
                    minmaxCost = float(row[1])
                
                elif row[0] == 'minCost':
                    minCost = float(row[1])

                elif row[0][0] in ['0','1'] :
                    fairness_coefficient.append(float(row[0]))
                    epsCost.append(float(row[1]))
                    deltaCost.append(float(row[2]))
        
        deltaCost[0] = minmaxCost
        epsCost[-1] = minmaxCost

        return fairness_coefficient, epsCost, deltaCost, minmaxCost, minCost
    
    def plotParetoFront(self):

        fairness_coefficient, epsCost, deltaCost, minmaxCost, minCost = self.getParetoFrontData()
        fig, ax = plt.subplots()
        params = self.get_plot_params(self.config.target)
        fs=params['fig_size']
        # fig.set_size_inches(fs[0], fs[1])
        fig.set_size_inches(6,4)
        ax.step(fairness_coefficient, epsCost, color = 'g', linestyle='-', marker = 'o', label=r'Cost$(\mathcal{F}^{\varepsilon})$')
        ax.step(fairness_coefficient, deltaCost, color = 'r', linestyle='dashdot', marker = 'o', label=r'Cost$(\mathcal{F}^{\Delta})$', where = 'post')

        # Plot the constant line for minmaxCOF
        ax.axhline(y=minmaxCost, color='b', linestyle='--', label=r'Cost$(\mathcal{F}_{\infty})$')
        ax.axhline(y=minCost, color='c', linestyle='--', label=r'Cost$(\mathcal{F}_1)$')

        plt.xlabel(r'$\varepsilon, \Delta$', fontsize = 12)
        plt.ylabel('Cost', fontsize = 12)
        plt.legend(loc='upper center', bbox_to_anchor=(0.55, 0.9))
        plt.tight_layout()       
        plt.grid(True)
        
        # plt.show()
        plt.savefig(f'../plots/{self.config.target}/paretoFront.pdf', format='pdf')


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