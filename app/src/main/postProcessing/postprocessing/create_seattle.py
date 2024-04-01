import osmnx as ox
import networkx as nx
import logging
import random
import numpy as np
import json
import os 

random.seed(2024)

log = logging.getLogger(__name__)
logging.basicConfig(
    format = '%(asctime)s %(levelname)s--: %(message)s',
    level = logging.INFO)


bbox = {'Seattle': (47.619, 47.604, -122.320, -122.355)}
city = 'Seattle'
G_ = ox.graph_from_bbox(bbox = bbox[city], 
                        network_type = 'drive', 
                        simplify = True).to_undirected()
relabel_map = {value: index for index, value in enumerate(G_.nodes())}
back_relabel_map = {index: value for index, value in enumerate(G_.nodes())}

node_data = {}
for (node, data) in G_.nodes(data = True): 
    node_data[node] = data 
original_to_new_node_labels = relabel_map 
new_to_original_node_labels = back_relabel_map 

G = nx.relabel_nodes(G_, relabel_map)
coordinates = {node: [data['x'], data['y']] for node, data in G.nodes(data = True)}
centroid = np.mean([ value for key, value in coordinates.items() ], axis=0)
distances_to_centroid = {
    node: np.linalg.norm(coord - centroid) for node, coord in coordinates.items()
    }
sorted_nodes = [node for node, _ in dict(
    sorted(distances_to_centroid.items(), key = lambda item: item[1])
    ).items()]
depot = sorted_nodes[0]
targets = random.sample(sorted_nodes, k = 50)

data = {
    'node_data' : node_data, 
    'original_to_new_node_labels' : relabel_map, 
    'new_to_original_node_labels' : back_relabel_map, 
    'targets_on_new_node_labels': targets, 
    'depot_on_new_node_labels': depot
}

log.info('storing relabel data in seattle.json')
with open('seattle.json', 'w') as outfile: 
    json.dump(data, outfile)
    
all_nodes = [depot] + targets
distance_matrix = {} 
for i in range(len(all_nodes)-1):
    for j in range(i+1, len(all_nodes)):
        distance_matrix[(all_nodes[i],all_nodes[j])] = nx.shortest_path_length(G, source=all_nodes[i], target=all_nodes[j], weight='length')
        
output_directory = '../../../../data/'

os.makedirs(output_directory, exist_ok=True)

node_coordinates = {node: coordinates[node] for node in all_nodes}

log.info('writing seattle.tsp file')
with open(os.path.join(output_directory, 'seattle.tsp'), 'w') as graph_file:
    graph_file.write("NAME: seattle50\n")
    graph_file.write("DEPOT : 1\n")
    graph_file.write("COMMENT: Depot and 50 random targets in Seattle \n")
    graph_file.write(f"DIMENSION: {len(node_coordinates)}\n")
    graph_file.write("EDGE_WEIGHT_TYPE : GIVEN\n")
    graph_file.write("NODE_COORD_SECTION\n")

    for node, coord in node_coordinates.items():
        graph_file.write(f"{node} {coord[0]} {coord[1]}\n")

    graph_file.write("EDGE COSTS\n")

    for edge, dist in distance_matrix.items():
        graph_file.write(f"{edge[0]} {edge[1]} {dist}\n")

    graph_file.write("EOF\n")


