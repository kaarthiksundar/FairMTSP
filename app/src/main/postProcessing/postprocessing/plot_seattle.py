import argparse 
import osmnx as ox
import matplotlib
import matplotlib.pyplot as plt
import networkx as nx
import logging
import subprocess
import json

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
    parser.add_argument('-f', '--fairnesstype', choices=['eps', 'delta'], 
                        help='eps/delta', type=str)
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
        self.G = None 
        self.targets = None 
        self.depot = None
        self.coordinates = None
        
    @staticmethod
    def get_plot_params(target):
        if target == 'paper':
            return {
                'fig_size': (2.5, 2.5),
                'node_color': 'black',
                'node_size': 1,
                'edge_color': 'gray',
                'bgcolor': 'white', 
                'edge_linewidth': 0.5,
                'node_alpha': 0.3, 
                'edge_alpha': 0.4,
                'scatter_s': 0.5,
                'node_size_with_path': 0.1, 
                'orig_dest_size': 0.0, 
                'route_linewidth': 1.5
            }
        else: 
            return {
                'fig_size': (4, 3),
                'node_color': 'black',
                'node_size': 2,
                'edge_color': 'gray',
                'bgcolor': 'white', 
                'edge_linewidth': 0.8,
                'node_alpha': 0.3, 
                'edge_alpha': 0.4,
                'scatter_s': 2.5, 
                'node_size_with_path': 0.2, 
                'orig_dest_size': 0.0, 
                'route_linewidth': 2.4
            }

    @staticmethod 
    def crop(file): 
        log.info(f'cropping figure {file}')
        subprocess.run(['pdfcrop', f'{file}.pdf'])
        subprocess.run(['rm', '-rf', f'{file}.pdf'])
        subprocess.run(['mv', f'{file}-crop.pdf', f'{file}.pdf'])
        log.info(f'cropping figure {file} complete')
        
    @staticmethod
    def get_fair_filename(num_vehicles, obj_type, fc): 
        return f'../../../../../results/seattle/seattle-v-{num_vehicles}-{obj_type}-p-2-fc-{fc}.json'
    
    @staticmethod 
    def get_filename(num_vehicles, obj_type): 
        return f'../../../../../results/seattle/seattle-v-{num_vehicles}-{obj_type}-p-2-fc-50.json'
        
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
    
    def _populate_graph(self):
        bbox = {'Seattle': (47.619, 47.604, -122.320, -122.355)}
        city = 'Seattle'
        G_ = ox.graph_from_bbox(bbox=bbox[city], network_type='drive', simplify=True).to_undirected()
        if self.config.plotgrid == True: 
            log.info('generating grid plot')
            params = self.get_plot_params(self.config.target) 
            fig, ax = plt.subplots()
            ox.plot_graph(G_, ax = ax,
                          node_color = params.get('node_color', 'black'), 
                          edge_color = params.get('edge_color', 'gray'), 
                          node_size = params.get('node_size', 1),
                          bgcolor = params.get('bgcolor', 'white'),
                          edge_linewidth = params.get('edge_linewidth', 1.0),
                          node_alpha = params.get('node_alpha', 0.3), 
                          edge_alpha = params.get('edge_alpha', 0.4),
                          show = False
                          )
            fig.set_tight_layout(True)
            fs = params['fig_size']
            log.info(f'setting grid fig size: {fs} sq. inches')
            fig.set_size_inches(fs[0], fs[1])
            plt.savefig(f'../plots/{self.config.target}/seattle_network.pdf', format='pdf')
            if self.config.pdfcrop == True:
                self.crop(f'../plots/{self.config.target}/seattle_network')
        f = open('seattle.json')
        json_data = json.load(f)
        node_data = json_data['node_data']
        original_to_new_node = json_data['original_to_new_node_labels']
        f.close()
        relabel_map = {}
        for node, data in G_.nodes(data = True):
            x, y = data['x'], data['y']
            matched_node_data = tuple(filter(lambda it: it[1]['x'] == x and it[1]['y'] == y, node_data.items()))[0]
            relabel_map[node] = original_to_new_node[matched_node_data[0]]
        self.G = nx.relabel_nodes(G_, relabel_map)
        self.coordinates = {node: [data['x'], data['y']] for node, data in self.G.nodes(data = True)}
        self.depot = json_data['depot_on_new_node_labels']
        self.targets = json_data['targets_on_new_node_labels']

        
    def _plot_graph_with_targets(self): 
        log.info('generating target plot')
        params = self.get_plot_params(self.config.target)
        fig, ax = plt.subplots() 
        ox.plot_graph(self.G, ax = ax,
                      node_color = params.get('node_color', 'black'), 
                      edge_color = params.get('edge_color', 'gray'), 
                      node_size = params.get('node_size', 1),
                      bgcolor = params.get('bgcolor', 'white'),
                      edge_linewidth = params.get('edge_linewidth', 1.0),
                      node_alpha = params.get('node_alpha', 0.3), 
                      edge_alpha = params.get('edge_alpha', 0.4),
                      show = False)
        # Plot the depot with a different color
        depot_x, depot_y = self.coordinates[self.depot]
        ax.scatter(depot_x, depot_y, 
                   c = 'red', 
                   s = params['scatter_s'], 
                   zorder = 5, 
                   alpha=0.8)
        # Plot the targets with a different color
        target_x, target_y = zip(*[self.coordinates[target] for target in self.targets])
        ax.scatter(target_x, target_y, 
                   c = 'blue', 
                   s = params['scatter_s'], 
                   zorder = 5, 
                   alpha = 0.8)
        fig.set_tight_layout(True)
        fs = params['fig_size']
        log.info(f'setting grid fig size: {fs} sq. inches')
        fig.set_size_inches(fs[0], fs[1])
        plt.savefig(f'../plots/{self.config.target}/seattle_graph.pdf', format='pdf')
        if self.config.pdfcrop == True:
            self.crop(f'../plots/{self.config.target}/seattle_graph')
            
    def _add_graph(self, axes):
        params = self.get_plot_params(self.config.target) 
        ox.plot_graph(self.G, ax = axes,
                      node_color = params.get('node_color', 'black'), 
                      edge_color = params.get('edge_color', 'gray'), 
                      node_size = params.get('node_size', 1),
                      bgcolor = params.get('bgcolor', 'white'),
                      edge_linewidth = params.get('edge_linewidth', 1.0),
                      node_alpha = params.get('node_alpha', 0.3), 
                      edge_alpha = params.get('edge_alpha', 0.4),
                      show = False, close = False
                      )
        # Plot the depot with a different color
        depot_x, depot_y = self.coordinates[self.depot]
        axes.scatter(depot_x, depot_y, 
                   c = 'red', 
                   s = params['scatter_s'], 
                   zorder = 5, 
                   alpha = 0.5)
        # Plot the targets with a different color
        target_x, target_y = zip(*[self.coordinates[target] for target in self.targets])
        axes.scatter(target_x, target_y, 
                   c = 'blue', 
                   s = params['scatter_s'], 
                   zorder = 5, 
                   alpha = 0.5)

    def _add_route(self, axes, routes, color):
        params = self.get_plot_params(self.config.target) 
        for (i, j) in zip(routes[:-1], routes[1:]):
            ox.plot_graph_route(self.G, [i, j], 
                                ax = axes, 
                                route_color = color, 
                                orig_dest_size = params.get('orig_dest_size', 0.0), 
                                route_linewidth = params.get('route_linewidth', 1.5), 
                                edge_alpha = None,
                                show = False,
                                close = False
                                )

            
    def _plot_fair_solutions(self, fc, obj_type): 
        num_vehicles = 4
        colors = ['xkcd:green', 'xkcd:magenta', 'xkcd:orange red', 'xkcd:brown']
        for (_, c) in enumerate(fc): 
            file = self.get_fair_filename(num_vehicles, obj_type, c)
            fig, ax = plt.subplots() 
            self._add_graph(ax)
            data = {} 
            with open(file, 'r') as jsonfile: 
                data = json.load(jsonfile)
            tours = data['tours']
            for vehicle in range(num_vehicles):
                path = [] 
                tour = tours[vehicle]
                for i in range(len(tour)-1):
                    s = tour[i] 
                    t = tour[i+1]
                    path.extend(nx.shortest_path(self.G, source=s, target=t, weight='length')[:-1])
                path.extend([tour[0]])
                self._add_route(ax, path, colors[vehicle])
            params = self.get_plot_params(self.config.target) 
            fig.set_tight_layout(True)
            fs = params['fig_size']
            log.info(f'setting {obj_type} with {c} fig size: {fs} sq. inches')
            fig.set_size_inches(fs[0], fs[1])
            plt.savefig(f'../plots/{self.config.target}/seattle_{obj_type}_{c}.pdf', format='pdf')
            if self.config.pdfcrop == True:
                self.crop(f'../plots/{self.config.target}/seattle_{obj_type}_{c}')
    
    def _plot_other_solutions(self):
        num_vehicles = 4
        colors = ['xkcd:green', 'xkcd:magenta', 'xkcd:orange red', 'xkcd:brown']
        obj_types = ['min-max', 'min', 'p-norm']
        for obj_type in obj_types:
            file = self.get_filename(num_vehicles, obj_type) 
            fig, ax = plt.subplots() 
            self._add_graph(ax)
            data = {} 
            with open(file, 'r') as jsonfile: 
                data = json.load(jsonfile)
            tours = data['tours']
            for vehicle in range(num_vehicles):
                path = [] 
                tour = tours[vehicle]
                for i in range(len(tour)-1):
                    s = tour[i] 
                    t = tour[i+1]
                    path.extend(nx.shortest_path(self.G, source=s, target=t, weight='length')[:-1])
                path.extend([tour[0]])
                self._add_route(ax, path, colors[vehicle])
            params = self.get_plot_params(self.config.target) 
            fig.set_tight_layout(True)
            fs = params['fig_size']
            log.info(f'setting {obj_type} fig size: {fs} sq. inches')
            fig.set_size_inches(fs[0], fs[1])
            plt.savefig(f'../plots/{self.config.target}/seattle_{obj_type}.pdf', format='pdf')
            if self.config.pdfcrop == True:
                self.crop(f'../plots/{self.config.target}/seattle_{obj_type}')
    
            
    def run(self): 
        self._set_rc_params()
        self._populate_graph()
        self._plot_graph_with_targets()
        fc = [10, 50, 90]
        self._plot_fair_solutions(fc,'delta-fair') 
        self._plot_fair_solutions(fc, 'eps-fair')
        self._plot_other_solutions()
        

def main():
    logging.basicConfig(format='%(asctime)s %(levelname)s--: %(message)s',
                        level=logging.INFO)
    
    try:
        config = handle_command_line()
        controller = Controller(config)
        controller.run()
    except PlotException as pe:
        log.error(pe)


if __name__ == "__main__":
    main()
