from shapely.geometry import *
from descartes import PolygonPatch
from scipy.spatial import Delaunay
from shapely.ops import cascaded_union, polygonize
from statistics import mean
from pyproj import Transformer, CRS # for transformations
import fiona
import random
import datetime
import math
import uncertainties
import operator
import json

import numpy as np
import osmnx as ox
import networkx as nx
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.lines as plines
import matplotlib.patches as mpatches
import shapely.geometry as geometry

#ox.config(log_console=True, use_cache=True)

from uncertainties import ufloat
from uncertainties.umath import *
from uncertainties import unumpy

# Add surface and tracktype tag to attributes, which will be queried from osm by networkx library
useful_tags = ox.settings.useful_tags_way + ['surface','tracktype']
# Update config to add useful_tags
ox.config(use_cache=True, log_console=True, useful_tags_way=useful_tags)


class Isochrones():
    """class for calculating and visualizing isochrones with respect to uncertainties
    """
        
    
    def __init__(self, graph, starting_point):
        """
        @param graph: graph in UTM
        @param starting_point: node in graph
        """
        self.G = graph
        self.center_node = starting_point
        self.areatype = self.setAreaClassification()
        self.weightingDefault()
    
    
    @classmethod
    def fromGraph(cls, graph, starting_point):
        "Initialize graph by given graph in WGS84"
        """
        @param graph: graph in WGS84
        @param starting_point: Point coordinates in WGS84 (lat, lon)
        """        
        s_p = ox.get_nearest_node(graph, starting_point)
        print(str(datetime.datetime.now()) + "   Project the graph to UTM.....")
        gdf_nodes = ox.graph_to_gdfs(graph, edges=False)
        graph_proj = ox.project_graph(graph)
        print(str(datetime.datetime.now()) + "   Done!")
        
        return cls(graph_proj, s_p)
    
    
    @classmethod
    def fromGraphUTM(cls, graph, starting_point):
        "Initialize graph by given graph in UTM"
        """
        @param graph: graph in UTM
        @param starting_point: Point coordinates in WGS84 (lat, lon)
        """        
        transformer = Transformer.from_crs(CRS("EPSG:4326"), CRS("EPSG:25832"))
        lon, lat = transformer.transform(starting_point[1], starting_point[0])
        starting_point_proj = (lon, lat)

        s_p = ox.get_nearest_node(graph, starting_point_proj)

        return cls(graph, s_p)
    
    
    @classmethod
    def fromBbox(cls, bbox, starting_point):
        "Initialize graph by given bounding box"
        
        network_type = 'drive'
        north = bbox[0]
        south = bbox[1]
        east = bbox[2]
        west = bbox[3]
        graph = ox.graph_from_bbox(north, south, east, west, network_type=network_type, infrastructure =  ('way["highway"]'))

        print(str(datetime.datetime.now()) + "   Project the graph to UTM.....")
        gdf_nodes = ox.graph_to_gdfs(graph, edges=False)
        graph = ox.project_graph(graph)
        print(str(datetime.datetime.now()) + "   Done!")
        
        return cls(graph, starting_point)
        
    
    
    
    def alpha_shape(self, points, alpha):
        """
        Compute the alpha shape (concave hull) of a set
        of points.
        @param points: Iterable container of points.
        @param alpha: alpha value to influence the
            gooeyness of the border. Smaller numbers
            don't fall inward as much as larger numbers.
            Too large, and you lose everything!
        """
        #print(geometry.MultiPoint(list(points)).convex_hull)
        if len(points) < 4:
            # When you have a triangle, there is no sense
            # in computing an alpha shape.
            return geometry.MultiPoint(list(points)).convex_hull
        
        def add_edge(edges, edge_points, coords, i, j):
            """
            Add a line between the i-th and j-th points,
            if not in the list already
            """
            if (i, j) in edges or (j, i) in edges:
                    # already added
                return
            edges.add( (i, j) )
            edge_points.append(coords[ [i, j] ])
        coords = np.array([point.coords[0]
                           for point in points])
        #print(coords)
        tri = Delaunay(coords)
        edges = set()
        edge_points = []
        # loop over triangles:
        # ia, ib, ic = indices of corner points of the
        # triangle
        for ia, ib, ic in tri.vertices:
            pa = coords[ia]
            pb = coords[ib]
            pc = coords[ic]
            # Lengths of sides of triangle
            a = math.sqrt((pa[0]-pb[0])**2 + (pa[1]-pb[1])**2)
            b = math.sqrt((pb[0]-pc[0])**2 + (pb[1]-pc[1])**2)
            c = math.sqrt((pc[0]-pa[0])**2 + (pc[1]-pa[1])**2)
            # Semiperimeter of triangle
            s = (a + b + c)/2.0
            # Area of triangle by Heron's formula
            area = math.sqrt(s*(s-a)*(s-b)*(s-c))
            circum_r = a*b*c/(4.0*area)
            # Here's the radius filter.
            #print circum_r
            if circum_r < 1.0/alpha:
                add_edge(edges, edge_points, coords, ia, ib)
                add_edge(edges, edge_points, coords, ib, ic)
                add_edge(edges, edge_points, coords, ic, ia)
        m = geometry.MultiLineString(edge_points)
        triangles = list(polygonize(m))
        return cascaded_union(triangles), edge_points
        
        
    
    def setAttributeColumns(self):
        """ Function adds maxspeed, highway, surface and tracktype attributes if they don't exist in data
            and set value to None (corresponds to no data)
        """
        for u, v, k, data in self.G.edges(data=True, keys=True):
            if 'maxspeed' not in data:
                data['maxspeed'] = None
            if 'highway' not in data:
                data['highway'] = None
            if 'surface' not in data:
                data['surface'] = None
            if 'tracktype' not in data:
                data['tracktype'] = None
    
    
    
    def setMaxspeedNewColumn(self):
        """ Creates an updated new maxspeed column, which uses the max value if 'maxspeed' is a list 
            or -1 if 'maxspeed' is None or a String
        """
        for u, v, k, data in self.G.edges(data=True, keys=True):
            
            data['maxspeed_new'] = None
            try:
                if isinstance(data['maxspeed'],(list,)): # If maxspeed is a list iterate over all entries
                    maxspeed_list_int = []
                    for element in data['maxspeed']:
                        if element == 'none': # add max speed value if element is "none"
                            maxspeed_list_int.append(int(999))
                        elif element is None: # Don't add a speed value if element is None
                            pass
                        else:
                            maxspeed_list_int.append(int(element)) # Append single element to temp list
                    data['maxspeed_new'] = max(maxspeed_list_int) # Set the new value to the max value of the maxspeed list
                elif data['maxspeed'] == 'none':
                    data['maxspeed_new'] = 999
                elif data['maxspeed'] is None:
                    data['maxspeed_new'] = -1
                else: 
                    data['maxspeed_new'] = int(data['maxspeed'])

            except ValueError:
                data['maxspeed_new'] = -1
    
    
    
    def setHighwaySpeedColumn(self):
        """ Create column 'highway_speed' and set speed values based on highway speed dictionary.
            Source: https://github.com/GIScience/openrouteservice-docs/blob/master/README.md   
        """
        # Set waytype speeds (car)
        highway_dict = {'motorway' : 130,
                      'motorway_link' : 60,
                      'motorroad' : 90,
                      'trunk' : 85,
                      'trunk_link' : 60,
                      'primary' : 65,
                      'primary_link' : 50,
                      'secondary' : 60,
                      'secondary_link' : 50,
                      'tertiary' : 50,
                      'tertiary_link' : 40,
                      'unclassified' : 50,
                      'residential' : 30,
                      'living_street' : 10,
                      'service' : 20,
                      'road' : 20,
                      'track' : 15,
                      'path' : 0,
                      'footway' : 0,
                      'pedestrian' : 0,
                      'cycleway' : 0}
        
        highway = ['motorway', 'motorway_link', 'motorroad', 'trunk', 'trunk_link', 'primary', 'primary_link', 'secondary', 
                   'secondary_link', 'tertiary', 'tertiary_link', 'unclassified', 'residential', 'living_street', 'service', 
                   'road', 'track', 'path', 'footway', 'pedestrian', 'cycleway']
        
        for u, v, k, data in self.G.edges(data=True, keys=True):
            
            data['highway_speed'] = None
            try:
                
                if isinstance(data['highway'],(list,)): # If maxspeed is a list iterate over all entries
                    highway_speed_list = []
                    for highway_element in data['highway']:
                        if 'razed' in data['highway']: # If razed is in data['highway'], road is not accessible
                            data['highway_speed'] = 0
                        elif 'motorway' in data['highway']: # If motorway in highway use highway speed from dict
                            data['highway_speed'] = int(highway_dict['motorway'])
                        else: # Else calculate max value of list
                            highway_speed_list.append(highway_dict[highway_element]) 
                            # Calculate average speed of speed entries
                            data['highway_speed'] = max(highway_speed_list)
                                
                elif data['highway'] == None: # If none then -1
                    data['highway_speed'] = -1
                elif data['highway'] == 'razed': # If razed then road is not accessible
                    data['highway_speed'] = 0
                elif data['highway'] == 'motorway':
                    data['highway_speed'] = 999
                else:
                    data['highway_speed'] = int(highway_dict[data['highway']])

            except(KeyError):
                data['highway_speed'] = -1
    
    
    
    def setSurfaceSpeedColumn(self):
        """ Create column 'surface_speed' and set speed values based on surface speed dictionary.
            Source: https://github.com/GIScience/openrouteservice-docs/blob/master/README.md
        """
        surface_dict = {
                    'asphalt': 999,
                    'concrete': 999,
                    'concrete_plates': 999,
                    'concrete:lanes': 999,
                    'paved': 999,
                    'cement': 80,
                    'compacted': 80,
                    'fine_gravel': 60,
                    'paving_stones': 40,
                    'metal': 40,
                    'bricks': 40,
                    'grass': 30,
                    'wood': 30,
                    'sett': 30,
                    'grass_paver': 30, 
                    'gravel': 30,
                    'unpaved': 30,
                    'ground': 30,
                    'dirt': 30,
                    'pebblestone': 30,
                    'tartan': 30,
                    'unhewn_cobblestone': 20,
                    'cobblestone': 20,
                    'cobblestone:flattened': 20,
                    'clay': 20,
                    'earth': 15,
                    'stone': 15,
                    'rocky': 15,
                    'sand': 15,
                    'mud': 10,
                    'unknown': 30}
        
        surface = ['asphalt','concrete','concrete_plates','concrete:lanes',
                   'paved','cement','compacted','fine_gravel','paving_stones',
                   'metal','bricks','grass','wood','sett','grass_paver',
                   'gravel','unpaved','ground','dirt','pebblestone','tartan',
                   'unhewn_cobblestone','cobblestone','cobblestone:flattened',
                   'clay','earth','stone','rocky','sand','mud','unknown']
        
        for u, v, k, data in self.G.edges(data=True, keys=True):
            
            data['surface_speed'] = None
            try:
                
                if isinstance(data['surface'],(list,)): # Case 'surface' is list
                    surface_speed_list = []
                    for element in data['surface']: # If maxspeed is a list iterate over all entries
                        if ('asphalt' or 'concrete' or 'concrete_plates' or 
                            'concrete:lanes' or 'paved') in data['surface']: # If surface is one of those there's no speed limitation
                            data['surface_speed'] = -1
                        else: # Else use mean value of list
                            surface_speed_list.append(surface_dict[element])
                            data['surface_speed'] = mean(surface_speed_list)
                
                elif data['surface'] is None:
                    data['surface_speed'] = -1
                else:
                    data['surface_speed'] = int(surface_dict[data['surface']])
                
            except(KeyError):
                data['surface_speed'] = -1
    
    
    
    def setTracktypeSpeedColumn(self):
        """ Create column 'tracktype_speed' and set speed values based on tracktype speed dictionary.
            Source: https://github.com/GIScience/openrouteservice-docs/blob/master/README.md
        """
        tracktype_dict = {
            'grade1': 40,
            'grade2': 30,
            'grade3': 20,
            'grade4': 15,
            'grade5': 10        
        }
        
        tracktype = ['grade1', 'grade2', 'grade3', 'grade4', 'grade5']
        
        for u, v, k, data in self.G.edges(data=True, keys=True):
            
            data['tracktype_speed'] = None
            
            try:
                
                if isinstance(data['tracktype'],(list,)): # Case 'tracktype' is list
                    tracktype_speed_list = []
                    for element in data['tracktype']:
                        tracktype_speed_list.append(tracktype_dict[element])
                        data['tracktype_speed'] = mean(tracktype_speed_list) # Calculate average speed of speed entries     
                
                elif data['tracktype'] is None:
                    data['tracktype_speed'] = -1
                else:
                    data['tracktype_speed'] = tracktype_dict[data['tracktype']]
                
            except(KeyError):
                data['tracktype_speed'] = -1


    def setAreaClassification(self):
        """ Define area factor based on eurostat data
            https://ec.europa.eu/eurostat/de/web/rural-development/methodology 
            Data Source: https://ec.europa.eu/eurostat/de/web/gisco/geodata/reference-data/administrative-units-statistical-units/nuts
        """
        
        urban_rural_typology = {
            1: 'predominantly urban',
            2: 'intermediate',
            3: 'predominantly rural'
        }
        
        # Load GeoJSON
        with open('data/urban-rural-de.geojson') as geojson:
            classification = json.load(geojson)

        # Transform lon,lat from starting point to x,y (4326 to 3857)
        transformer = Transformer.from_crs(CRS("EPSG:4326"), CRS("EPSG:3857"))
        x, y = transformer.transform(self.G.nodes[self.center_node]['lon'], self.G.nodes[self.center_node]['lat'])
        start = Point(x, y)


        area_classification = ""
        # Check polygons if Point is inside one of them
        for feature in classification['features']:
            polygon = shape(feature['geometry'])
            if polygon.contains(start):
                area_classification = urban_rural_typology[int(feature['properties']['URB_RUR_CL'])]
                print('Area Type around starting point: ' + feature['properties']['NUTS_NAME'] + " is of type " + urban_rural_typology[int(feature['properties']['URB_RUR_CL'])])
        
        if area_classification == 'predominantly urban':
            return 1.55
        else:
            return 1.25
        
        
    
    def isochrone_points(self, trip_time, outputname):
        "Visualizes isochrone as a group of points, based on the level of uncertainty"
        """
        @param trip_time: trip_time in minutes
        @param outputname: output file
        """        
        
        print(str(datetime.datetime.now()) + "   Calculate Isochrone.....")

        subgraph = nx.ego_graph(self.G, self.center_node, radius=trip_time, distance='time')
        node_points = [Point((data['x'], data['y'])) for node, data in subgraph.nodes(data=True)]
        
        with open(outputname + "_iso-pts.wkt", "w") as target1:
            for p in node_points:
                target1.write(p.wkt + '\n')
        

        subgraphMin = nx.ego_graph(self.G, self.center_node, radius=trip_time, distance='timeMin')
        #node_pointsMin = [Point((data['x'], data['y'])) for node, data in subgraphMin.nodes(data=True)]
        subgraphMax = nx.ego_graph(self.G, self.center_node, radius=trip_time, distance='timeMax')
        #node_pointsMax = [Point((data['x'], data['y'])) for node, data in subgraphMax.nodes(data=True)]
        
        node_colors = {}
        for node in subgraphMin.nodes():
            node_colors[node] = '#CD6155'
        for node in subgraph.nodes():
            node_colors[node] = '#F7DC6F'
        for node in subgraphMax.nodes():
            node_colors[node] = '#7DCEA0'
                
        nc = [node_colors[node] if node in node_colors else 'none' for node in self.G.nodes()]
        ns = [20 if node in node_colors else 0 for node in self.G.nodes()]
        fig, ax = ox.plot_graph(self.G, figsize=[15,15], node_color=nc, node_size=ns, node_alpha=0.8, node_zorder=2,
                                save=True, show=False, close=False, edge_color='grey', edge_linewidth=0.5)
        
        ax.plot(self.G.nodes[self.center_node]['x'], self.G.nodes[self.center_node]['y'], 'ko', markersize=10)
        
        plt.savefig(outputname)
        plt.close(fig)
        
        print(str(datetime.datetime.now()) + "   Done!")
    
    
    def isochrone_poly(self, trip_time, outputname):
        "Visualizes isochrone with an uncertainty polygon"
        """
        @param trip_time: trip_time in minutes
        @param outputname: output file
        """   
        
        print(str(datetime.datetime.now()) + "   Calculate Isochrone.....")

        isochrone_polys = []
        subgraph = nx.ego_graph(self.G, self.center_node, radius=trip_time, distance='time')
        node_points = [Point((data['x'], data['y'])) for node, data in subgraph.nodes(data=True)]
        bounding_poly = self.alpha_shape(gpd.GeoSeries(node_points), alpha=0.001)[0]
        isochrone_polys.append(bounding_poly)
        #print(isochrone_polys[0])
        lines = []
        #print(type(bounding_poly))
        if type(bounding_poly) == geometry.multipolygon.MultiPolygon:
            for element in bounding_poly:
                xdata = []
                ydata = []
                for polygon in list(element.exterior.coords):
                    xdata.append(polygon[0])
                    ydata.append(polygon[1])
                lines.append(plines.Line2D(xdata, ydata, color='red'))

        elif type(bounding_poly) == geometry.polygon.Polygon:
            xdata = []
            ydata = []
            for element in list(bounding_poly.exterior.coords):
                xdata.append(element[0])
                ydata.append(element[1])
            lines.append(plines.Line2D(xdata, ydata, color='red'))
        
        
        with open(outputname + "_iso-poly.wkt", "w") as target1:
            target1.write(isochrone_polys[0].wkt)
        
        listOfPolys = []

        subgraph = nx.ego_graph(self.G, self.center_node, radius=trip_time, distance='timeMin')
        node_points = [Point((data['x'], data['y'])) for node, data in subgraph.nodes(data=True)]
        bounding_poly = self.alpha_shape(gpd.GeoSeries(node_points), alpha=0.001)[0]
        listOfPolys.append(bounding_poly)

        subgraph = nx.ego_graph(self.G, self.center_node, radius=trip_time, distance='timeMax')
        node_points = [Point((data['x'], data['y'])) for node, data in subgraph.nodes(data=True)]
        #bounding_poly = gpd.GeoSeries(node_points).unary_union.convex_hull
        bounding_poly = self.alpha_shape(gpd.GeoSeries(node_points), alpha=0.001)[0]
        listOfPolys.append(bounding_poly)

        union = Polygon()
        for poly in listOfPolys:
            union = union.union(poly)

        intersection = union.buffer(50)
        for poly in listOfPolys:
            intersection = intersection.intersection(poly)

        #print("__________________________________")
        #print(union.buffer(50).difference(intersection))
        
        with open(outputname + "_iso-poly-uncert.wkt", "w") as target2:
            target2.write(union.buffer(50).difference(intersection).wkt)
            
        patch = PolygonPatch(union.buffer(50).difference(intersection), fc='salmon', ec='none', alpha=0.6, zorder=-1)
        fig, ax = ox.plot_graph(self.G, figsize=[15,15], bgcolor='#ffffff', show=False, close=False, edge_color='grey', edge_alpha=0.2, node_color='none')
        for line in lines:
            ax.add_line(line)
        ax.plot(self.G.nodes[self.center_node]['x'], self.G.nodes[self.center_node]['y'], 'ro', markersize=10)
        ax.add_patch(patch)
        plt.savefig(outputname, dpi=300)
        #plt.savefig(outputname)
        plt.close(fig)
        print(str(datetime.datetime.now()) + "   Done!")



    def isochrone_network(self, trip_time, outputname):
        "Visualizes isochrone as a group of edges of the network, based on the level of uncertainty"
        """
        @param trip_time: trip_time in minutes
        @param outputname: output file
        """   
        
        print(str(datetime.datetime.now()) + "   Calculate Isochrone.....")        
    
        subgraph = nx.ego_graph(self.G, self.center_node, radius=trip_time, distance='time')   
        isochrone = ox.graph_to_gdfs(subgraph, nodes=False).geometry.unary_union
        #print(isochrone)

        with open(outputname + "_iso-network.wkt", "w") as target:
            target.write(isochrone.wkt)
            
        network = []
        for line in isochrone.geoms:
            xdata = []
            ydata = []
            for element in list(line.coords):
                xdata.append(element[0])
                ydata.append(element[1])
            network.append(plines.Line2D(xdata, ydata, color='darkgreen', linewidth=0.5))
        print(str(datetime.datetime.now()) + "   Done!")
        

        print(str(datetime.datetime.now()) + "   Calculate uncertainty threshold.....")

        subgraphMax = nx.ego_graph(self.G, self.center_node, radius=trip_time, distance='timeMin')
        maxGraph = ox.graph_to_gdfs(subgraphMax, nodes=False).geometry.unary_union

        subgraphMin = nx.ego_graph(self.G, self.center_node, radius=trip_time, distance='timeMax')
        minGraph = ox.graph_to_gdfs(subgraphMin, nodes=False).geometry.unary_union

        uncert = maxGraph.difference(minGraph)
        with open(outputname + "_iso-network-uncert.wkt", "w") as target2:
            target2.write(uncert.wkt)
            
        uncertlines = []
        for line in uncert.geoms:
            xdata = []
            ydata = []
            for element in list(line.coords):
                xdata.append(element[0])
                ydata.append(element[1])
            uncertlines.append(plines.Line2D(xdata, ydata, color='khaki', linewidth=1.5))  

        fig, ax = ox.plot_graph(self.G, figsize=[15,15], show=False, close=False, edge_color='grey', edge_alpha=0.2, node_color='none')
        for line2 in uncertlines:
            ax.add_line(line2)
        for line1 in network:
            ax.add_line(line1)
        ax.plot(self.G.nodes[self.center_node]['x'], self.G.nodes[self.center_node]['y'], 'ko', markersize=10)
        plt.savefig(outputname)    
        plt.close(fig)
        print(str(datetime.datetime.now()) + "   Done!")
        
        
    def isochrone_umap(self, outputname):
        "Visualizes network edges in the color of the source of the highest uncertainty"
        """
        @param outputname: output file
        """
        
        edge_colors = {}
        
        for u, v, k, data in self.G.edges(data=True, keys=True):
            if max(data['time'].error_components().items(), key=operator.itemgetter(1))[0].tag == 'length':
                edge_colors[(u, v)] = 'blue'
            elif max(data['time'].error_components().items(), key=operator.itemgetter(1))[0].tag == 'speed':
                edge_colors[(u, v)] = 'green'
            elif max(data['time'].error_components().items(), key=operator.itemgetter(1))[0].tag == 'no data':
                edge_colors[(u, v)] = 'red'
        nc = [edge_colors[(u, v)] if (u, v) in edge_colors else 'none' for u, v, k, data in self.G.edges(data=True, keys=True)]
        ns = [0.5 if edge in edge_colors else 0.1 for edge in self.G.edges()]
        fig, ax = ox.plot_graph(self.G, figsize=[15,15], edge_color=nc, edge_linewidth=ns, edge_alpha=0.8, node_color='none', save=True, show=False, close=False)
        
        blue_patch = mpatches.Patch(color='blue', label='length')
        green_patch = mpatches.Patch(color='green', label='speed')
        red_patch = mpatches.Patch(color='red', label='no data')
        ax.legend(title ="größter Unsicherheitsfaktor" , handles=[blue_patch, green_patch, red_patch])
        
        plt.savefig(outputname)    
        plt.close(fig)
        
        print(str(datetime.datetime.now()) + "   Done!")
        
    
    def setAttributes(self):
        """ Sets attributes of the network edges   
        """
        
        self.setAttributeColumns()
        self.setMaxspeedNewColumn()
        self.setHighwaySpeedColumn()
        self.setSurfaceSpeedColumn()
        self.setTracktypeSpeedColumn()
    
    
    def weightingDefault(self, speed_uncert=None, nolimit=None, nodata=None):
        "sets default weigthing for network edges based on their attributes"
        """
        @param speed_uncert: uncertainty of traffic congestion in percent of 
        @param nolimit: value of default speed if there is no speed limit
        @param nodata: value of default speed if there is speed limit in data
        """
        
        print(str(datetime.datetime.now()) + "   weightingDefault().....")
        
        self.setAttributes()
        
        if speed_uncert == None:
            speed_uncert = 0.1
        else:
            speed_uncert = speed_uncert / 100
        if nolimit == None:
            nolimit = ufloat(100, 30, "no limit")
        if nodata == None:
            nodata = ufloat(50, 20, "no data")
        
        malus = self.areatype

        for u, v, k, data in self.G.edges(data=True, keys=True):
            
            data['time'] = None
            data['timeMin'] = None
            data['timeMax'] = None
            
            if 1/data['length'].n < 0.3:
                short_uncert = 1/data['length'].n
            else:
                short_uncert = 0.6
            
            
            if 'maxspeed' in data:
                try:
                    if data['maxspeed'] == 'none':
                        data['time'] = data['length'] / (nolimit * 1000 / 60)
                    elif int(data['maxspeed']) >= 100:
                        data['time'] = data['length'] / (ufloat(int(data['maxspeed']), int(data['maxspeed'])*(speed_uncert+short_uncert), "speed")  * 1000 / 60)
                    else:
                        data['time'] = data['length'] / (ufloat(int(data['maxspeed']), int(data['maxspeed'])*(speed_uncert+short_uncert), "speed")  * 1000 / 60) * malus
                except (TypeError, ValueError, ZeroDivisionError):
                    data['time'] = data['length'] / (nodata * 1000 / 60) * malus            
            else:
                data['time'] = data['length'] / (nodata * 1000 / 60) * malus
            
            data['timeMin'] = data['time'].n - data['time'].s
            data['timeMax'] = data['time'].n + data['time'].s   
    
    
    
    def weightingExpand_drive(self, speed_uncert, nolimit, nodata):
        "sets expand weigthing (='Erweiterte Analyse') for network edges based on their attributes (driving mode)"
        """
        @param speed_uncert: uncertainty of traffic congestion in percent of 
        @param nolimit: value of default speed if there is no speed limit
        @param nodata: value of default speed if there is speed limit in data
        """
        
        print(str(datetime.datetime.now()) + "   weightingExpand_drive().....")
        
        self.setAttributes()

        malus = self.areatype
        speed_uncert = speed_uncert / 100
        
        speed_cols = ['maxspeed_new', 'highway_speed', 'surface_speed', 'tracktype_speed']
        
        for u, v, k, data in self.G.edges(data=True, keys=True):
            
            data['time'] = None
            data['timeMin'] = None
            data['timeMax'] = None
            
            if 1/data['length'].n < 0.3:
                short_uncert = 1/data['length'].n
            else:
                short_uncert = 0.6
            
            speed_cols_temp = []
                
            if data['highway'] == 'motorway': # If it's a motorway always use the min of highway_speed and maxspeed_new
                
                if data['maxspeed_new']==-1: 
                    data['final_speed'] = data['highway_speed']
                else:
                    data['final_speed'] = min(data['highway_speed'], data['maxspeed_new'])
                
                if data['final_speed'] == 999:
                    data['time'] = data['length'] / ( nolimit * 1000 / 60) * 1.25
                else:
                    data['time'] = data['length'] / ( ufloat(int(data['final_speed']), int(data['final_speed'])*(speed_uncert+short_uncert), "speed") * 1000 / 60) * 1.25
                data['timeMin'] = data['time'].n - data['time'].s
                
            else:
                for column in speed_cols: # Iterate over all speed columns
                    if data[column] != -1: # If column is not -1 append the speed value to dict
                        speed_cols_temp.append(data[column])
                        
                if len(speed_cols_temp) == 0: # If list is empty, data['time'] gets nodata value
                    data['final_speed'] = nodata
                    data['time'] = data['length'] / (data['final_speed'] * 1000 / 60) * malus
                    data['timeMin'] = data['time'].n - data['time'].s
                        
                else: # Else use smallest value of speed columns and calculate 'time'
                    data['final_speed'] = min(speed_cols_temp)
                        
                    if data['final_speed'] == 0: # If road is not accessible
                        data['time'] = ufloat(3600, 0) 
                        data['timeMin'] = data['time']
                        
                    elif data['final_speed'] < 0:
                        data['final_speed'] = nodata
                        data['time'] = data['length'] / (data['final_speed'] * 1000 / 60) * malus
                        data['timeMin'] = data['time']
                        
                    else:
                        data['time'] = data['length'] / (ufloat(int(data['final_speed']), int(data['final_speed'])*(speed_uncert+short_uncert), "speed") * 1000 / 60) * malus
                        data['timeMin'] = data['time']
            
            data['timeMax'] = data['time'].n + data['time'].s
                
    
    
    def weightingCautious_drive(self, speed_uncert, nolimit, nodata):
        "sets cautious weigthing (='Vorsichtige Analyse') for network edges based on their attributes (driving mode)"
        """
        @param speed_uncert: delay caused by traffic congestion in percent of normal travel time 
        @param nolimit: value of default speed if there is no speed limit
        @param nodata: value of default speed if there is speed limit in data
        """

        
        print(str(datetime.datetime.now()) + "   weightingCautious_drive().....")
        
        self.setAttributes()
        
        malus = self.areatype
        speed_uncert = speed_uncert / 100
        
        nolimit_central = ufloat(nolimit.n * (1-speed_uncert), nolimit.n - (nolimit.n * (1-speed_uncert)), "no limit")
        nodata_central = ufloat(nodata.n * (1-speed_uncert), nodata.n - (nodata.n * (1-speed_uncert)), "no data")
        
        for u, v, k, data in self.G.edges(data=True, keys=True):
            
            speed_cols = ['maxspeed_new', 'highway_speed', 'surface_speed', 'tracktype_speed']
            
            data['time'] = None
            data['timeMin'] = None
            data['timeMax'] = None
            
            if 1/data['length'].n < 0.3:
                short_uncert = 1/data['length'].n
            else:
                short_uncert = 0.6
            
            speed_cols_temp = []
            
            
            if data['highway'] == 'motorway': # If it's a motorway always use the min of highway_speed and maxspeed_new
                
                if data['maxspeed_new']==-1: 
                    data['final_speed'] = data['highway_speed']
                else:
                    data['final_speed'] = min(data['highway_speed'], data['maxspeed_new'])
                
                if data['final_speed'] == 999:
                    data['time'] = data['length'] / ( nolimit_central * 1000 / 60) * 1.25
                    data['timeMin'] = data['length'] / (nolimit * 1000 / 60)* 1.25
                else:
                    data['time'] = data['length'] / ( ufloat(int(data['final_speed']) * (1-speed_uncert), int(data['final_speed'])- (int(data['final_speed']) * (1-speed_uncert)), "speed") * 1000 / 60) * 1.25
                    data['timeMin'] = data['time'].n - data['time'].s
                
                if speed_uncert > .5:
                    data['timeMax'] = data['length'] / (1000 / 60)
                else:
                    data['timeMax'] = data['time'].n + data['time'].s
            
            
            else:
                for column in speed_cols: # Iterate over all speed columns
                    if data[column] != -1: # If column is not -1 append the speed value to dict
                        speed_cols_temp.append(data[column])
                        
                if len(speed_cols_temp) == 0: # If list is empty, data['time'] gets no data value
                    data['final_speed'] = nodata_central
                    data['time'] = data['length'] / ( nodata_central * 1000 / 60) * malus
                    data['timeMin'] = data['length'] / (nodata * 1000 / 60) * malus
                    
                    if speed_uncert > .5:
                        data['timeMax'] = data['length'] / (1000 / 60)
                    else:
                        data['timeMax'] = data['time'].n + data['time'].s
                        
                else: # Else use smallest value of speed columns and calculate 'time'
                    data['final_speed'] = min(speed_cols_temp)
                        
                    if data['final_speed'] == 0:
                        data['time'] = ufloat(3600, 0) 
                        data['timeMin'] = data['time']
                        
                    elif data['final_speed'] < 0:
                        data['final_speed'] = nodata_central
                        data['time'] = data['length'] / (data['final_speed'] * 1000 / 60) * malus
                        data['timeMin'] = data['length'] / (nodata * 1000 / 60) * malus
                        
                    else:
                        data['time'] = data['length'] / ( ufloat(int(data['final_speed']) * (1-speed_uncert), int(data['final_speed'])- (int(data['final_speed']) * (1-speed_uncert)), "speed") * 1000 / 60) * malus
                        data['timeMin'] = data['length'] / ( ufloat(int(data['final_speed']), (int(data['final_speed']) * (1-speed_uncert)), "speed") * 1000 / 60) * malus

                        
                    if speed_uncert > .5:
                        data['timeMax'] = data['length'] / (1000 / 60)
                    else:
                        data['timeMax'] = data['time'].n + data['time'].s
            
        
    
    def weightingExpand_walk(self, walking_speed):
        "sets expand weigthing (='Erweiterte Analyse') for network edges based on their attributes (walking mode)"
        """
        @param walking_speed: ufloat of walking speed 
        """
        
        print(str(datetime.datetime.now()) + "   weightingExpand_walk().....")
        
        for u, v, k, data in self.G.edges(data=True, keys=True):
            
            data['time'] = None
            data['timeMin'] = None
            data['timeMax'] = None
            
            data['time'] = data['length'] / (walking_speed  * 1000 / 60)
            
            data['timeMin'] = data['time'].n - data['time'].s
            data['timeMax'] = data['time'].n + data['time'].s
    
    
    
    def weightingCautious_walk(self, walking_speed):
        "sets expand weigthing (='Vorsichtige Analyse') for network edges based on their attributes (walking mode)"
        """
        @param walking_speed: ufloat of walking speed 
        """
        
        print(str(datetime.datetime.now()) + "   weightingCentral_walk().....")
        
        walking_speed_central = ufloat(walking_speed.n - walking_speed.s, (walking_speed.n - walking_speed.s)*(walking_speed.s/walking_speed.n), "central speed")
        
        for u, v, k, data in self.G.edges(data=True, keys=True):
            
            data['time'] = None
            data['timeMin'] = None
            data['timeMax'] = None
            
            data['time'] = data['length'] / (walking_speed_central  * 1000 / 60)
            
            data['timeMin'] = data['time'].n - data['time'].s
            data['timeMax'] = data['time'].n + data['time'].s
    

    def updateStartingPoint (self, new_point):
        "Update Starting Point"
        """
        @param new_point: Point coordinates in WGS84 (lat, lon)
        """
        transformer = Transformer.from_crs(CRS("EPSG:4326"), CRS("EPSG:25832"))
        lon, lat = transformer.transform(new_point[0], new_point[1])

        self.center_node = ox.get_nearest_node(self.G, (lat, lon))