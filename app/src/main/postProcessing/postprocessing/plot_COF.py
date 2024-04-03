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
                'fig_size': (2.5, 2.5)
            }
        else: 
            return {
                'fig_size': (4, 3)
            }
        

    @staticmethod
    def getbasepath():
        return os.path.abspath(os.path.join(os.path.dirname(__file__) , '../../../../..'))
    
    @staticmethod
    def getDataFilepath(basepath):
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
                'text.usetex': False,
                'font.family': 'serif',
                'font.size' : 10,
                'pgf.rcfonts': False,
                })
        else: 
            matplotlib.rcParams.update({
                'text.usetex': False,
                'font.family': 'sans-serif',
                'text.latex.preamble': r'\usepackage{sourcesanspro,eulervm}',
                'font.size' : 11,
                'pgf.rcfonts': False,
                })

    def getData(self):
        COF_filepath = self.getDataFilepath(self.getbasepath())
        fairness_coefficient = []
        epsCOF = []
        deltaCOF = []
        minmaxCOF = None

        with open(COF_filepath, 'r') as file:
            reader = csv.reader(file, delimiter=',')
            for row in reader:
                if row[0] == 'minmaxCOF':
                    minmaxCOF = float(row[1])
                
                elif row[0][0] in ['0','1'] :
                    fairness_coefficient.append(float(row[0]))
                    epsCOF.append(float(row[1]))
                    deltaCOF.append(float(row[2]))
        epsCOF[-1] = 0.28
        deltaCOF[0] = 0.28

        return fairness_coefficient, epsCOF, deltaCOF, minmaxCOF

    def plotData(self):

        fairness_coefficient, epsCOF, deltaCOF, minmaxCOF = self.getData()
        fig, ax = plt.subplots()
        params = self.get_plot_params(self.config.target)
        fs=params['fig_size']
        # fig.set_size_inches(fs[0], fs[1])
        fig.set_size_inches(6,4)
        ax.step(fairness_coefficient, epsCOF, linestyle='-', marker = 'o', label=r'$\varepsilon$-F-MTSP')
        ax.step(fairness_coefficient, deltaCOF, linestyle='-', marker = 'o', label=r'$\Delta$-F-MTSP', where = 'post')

        # Plot the constant line for minmaxCOF
        ax.axhline(y=minmaxCOF, color='r', linestyle='--', label='min-max MTSP')

        plt.xlabel(r'$\varepsilon, \Delta$', fontsize = 12)
        plt.ylabel('Cost of Fairness', fontsize = 12)
        plt.legend(loc='upper center', bbox_to_anchor=(0.55, 0.9))
        plt.tight_layout()       
        plt.grid(True)
        
        # plt.show()
        plt.savefig(f'../plots/{self.config.target}/COF.pdf', format='pdf')
 


def main():
    logging.basicConfig(format='%(asctime)s %(levelname)s--: %(message)s',
                        level=logging.INFO)
    
    try:
        config = handle_command_line()
        controller = Controller(config)
        controller._set_rc_params()
        controller.plotData()
    except PlotException as pe:
        log.error(pe)

if __name__ == "__main__":
    main()