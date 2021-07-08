import osmnx as ox

# configure bbox & network type
north = 52.5533
south = 52.469
west = 13.291
east = 13.4618
network_type = 'drive' # 'drive' or 'walk'

# Add surface and tracktype tag to attributes, which will be queried from osm by networkx library
useful_tags = ox.settings.useful_tags_way + ['surface','tracktype']
ox.config(use_cache=True, log_console=True, useful_tags_way=useful_tags)

# Download Graph
G = ox.graph_from_bbox(north, south, east, west, network_type=network_type)

# Save Graph to file
ox.io.save_graphml(G, filepath='berlin_drive.graphml', gephi=False)
