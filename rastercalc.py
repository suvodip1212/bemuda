import fiona
import datetime

from osgeo import gdal, ogr
from shapely.geometry import *
from shapely.ops import unary_union
from geovoronoi import voronoi_regions_from_coords
from scipy.spatial import KDTree

import numpy as np

import os

class UncertRasterCalculator():
    """
    Class for calculating and visualizing uncertainties with respect to uncertainties
    """

    def __init__(self, points, area, output_path, attribute):
        """
        @param points: Points as Shapefile
        @param area: Area as Shapefile
        @param output_path: Path for Outputfile
        @param attribute: Attribute name as string
        """
        self.points = points
        self.area = area
        self.path = output_path
        self.output_raster = output_path + "/raster.tiff"
        self.attribute = attribute
    
    def pixel2world(self, geoMatrix, x, y):
        ulX = geoMatrix[0]
        ulY = geoMatrix[3]
        xDist = geoMatrix[1]
        yDist = geoMatrix[5]
        coorX = (ulX + (x * xDist))
        coorY = (ulY + (y * yDist))
        return (coorX, coorY)

    def writeRaster(self, InputRaster, InputArray, OutputFile):
        driver = gdal.GetDriverByName("GTiff")
        dataset = driver.Create(OutputFile, len(InputArray[0]), len(InputArray[1]), 1, gdal.GDT_Float32 )
        dataset.SetGeoTransform(InputRaster.GetGeoTransform())
        dataset.SetProjection(InputRaster.GetProjection())
        dataset.GetRasterBand(1).WriteArray(InputArray)
        dataset.FlushCache()
        
    def exportGrid(self, openRaster, gridArray, filename):

        print(f"Export {filename}")

        grid = np.zeros(shape=(openRaster.RasterYSize, openRaster.RasterXSize))
        x = 0
        for i in range(0, 180):
            for j in range(0, 180):
                grid[i][j] = gridArray[x]
                x = x+1
        self.writeRaster(openRaster, grid, filename)

    def prepare_raster(self, pixel_size = 100):
        """
        Vorbereitung des Rasters
        """
        NoData_value = 0

        source_ds = ogr.Open(self.area)
        source_layer = source_ds.GetLayer()
        x_min, x_max, y_min, y_max = source_layer.GetExtent()

        x_res = int((x_max - x_min) / pixel_size)
        y_res = int((y_max - y_min) / pixel_size)
        target_ds = gdal.GetDriverByName('GTiff').Create(self.output_raster, x_res, y_res, 1, gdal.GDT_Byte)
        target_ds.SetGeoTransform((x_min, pixel_size, 0, y_max, 0, -pixel_size))
        band = target_ds.GetRasterBand(1)
        band.SetNoDataValue(NoData_value)
        band = None
        target_ds = None

        openRaster = gdal.Open(self.output_raster)
        geoTrans = openRaster.GetGeoTransform()

        rasterlist =[]
        for i in range(0, 180):
            for j in range(0, 180):
                rasterlist.append(self.pixel2world(geoTrans, j, i))
        raslist = np.array(rasterlist)

        return openRaster, raslist

    def import_points(self):
        """
        Import der Punktgeometrien und der Attributwerte
        """
        with fiona.open(self.points, 'r') as source:
            layerPoints = list(source)

        listOfCoords = []
        listOfValues = []
        for point in layerPoints:
            listOfCoords.append([point['geometry']['coordinates'][0], point['geometry']['coordinates'][1]])
            listOfValues.append(point['properties'][self.attribute])
        points = np.array(listOfCoords)
        values = np.array(listOfValues)

        return points, values
    
    def import_polygons(self):
        """
        Import der Flächengeometrien und Berechnung der Gesamtfläche
        """
        
        with fiona.open(self.area, 'r') as source:
            layerPolys = list(source)
        
        shap = []
        for pol in layerPolys:
            shap.append(shape(pol['geometry']))
        shapeOfLayer = unary_union(shap)
        
        return layerPolys, shapeOfLayer
    
    
    def import_points_with_uncertainties(self, uncertainty):
        """
        Import der Punktgeometrien und der UNSICHEREN Attributwerte
        """
        with fiona.open(self.points, 'r') as source:
            layerPoints = list(source)

        listOfCoords = []
        listOfValuesUncertPlus = []
        listOfValuesUncertMinus = []
        for point in layerPoints:
            listOfCoords.append([point['geometry']['coordinates'][0], point['geometry']['coordinates'][1]])
            
            d = 2
    
            if is_number(uncertainty):
                listOfValuesUncertPlus.append(point['properties'][self.attribute]+point['properties'][self.attribute]*(uncertainty / 100))
                listOfValuesUncertMinus.append(point['properties'][self.attribute]-point['properties'][self.attribute]*(uncertainty / 100))
            elif uncertainty == "mathematical":
                listOfValuesUncertPlus.append(point['properties'][self.attribute])
                listOfValuesUncertMinus.append(point['properties'][self.attribute])
            elif uncertainty == "exactly":
                listOfValuesUncertPlus.append(point['properties'][self.attribute]+(10**(-(d+1))))
                listOfValuesUncertMinus.append(point['properties'][self.attribute]-(10**(-(d+1))))
            elif uncertainty == "about":
                listOfValuesUncertPlus.append(point['properties'][self.attribute]+2*(10**(-d)))
                listOfValuesUncertMinus.append(point['properties'][self.attribute]-2*(10**(-d)))
            elif uncertainty == "around":
                listOfValuesUncertPlus.append(point['properties'][self.attribute]+2*(10**(-d)))
                listOfValuesUncertMinus.append(point['properties'][self.attribute]-2*(10**(-d)))
            elif uncertainty == "count":
                data[key] = ufloat(data[key], math.sqrt(data[key]), str(key))
                listOfValuesUncertPlus.append(point['properties'][self.attribute]+math.sqrt(point['properties'][self.attribute]))
                listOfValuesUncertMinus.append(point['properties'][self.attribute]-math.sqrt(point['properties'][self.attribute]))

        points = np.array(listOfCoords)
        valuesPlus = np.array(listOfValuesUncertPlus)
        valuesMinus = np.array(listOfValuesUncertMinus)

        return points, valuesPlus, valuesMinus


    def calculate_uncertaintyRaster(self, cellsize, neighbors, maxDistance):
        """
        Berechnung des Unsicherheitsrasters
        """        
        # Create directory "/UncertaintyRaster" if it does not exist already
        if not os.path.exists(self.path + "/UncertaintyRaster"):
            os.makedirs(self.path + "/UncertaintyRaster")
        
        listOfCoords, values = self.import_points()
        layerPolys, shapeOfLayer = self.import_polygons()
        openRaster, raslist = self.prepare_raster(float(cellsize))
        
        outputFile = self.path + "/UncertaintyRaster" + "/uncertaintyRaster.tiff"

        print(str(datetime.datetime.now()) + " Calculating Voronoi-Polygons...................")
        points = np.array(listOfCoords)
        poly_shapes, represent_pts, poly_to_pt_assignments = voronoi_regions_from_coords(points, shapeOfLayer)
        shapeList = []
        for x in range(0, len(poly_shapes)):
            for polygon in layerPolys:
                if represent_pts[(poly_to_pt_assignments[x][0])].intersects(shape(polygon['geometry'])):
                    shapeList.append(poly_shapes[x].difference(shape(polygon['geometry'])))
        shapeUnion = unary_union(shapeList)
        # union als shp exportieren

        print(str(datetime.datetime.now()) + " Initializing kdTree............................")
        kdtree = KDTree(listOfCoords)
        
        print(str(datetime.datetime.now()) + " Calculating UncertaintyRaster.............................")
        geoTrans = openRaster.GetGeoTransform()
        
        
        print(str(datetime.datetime.now()) + "  --- Calculating NeighborRaster.............................")
        uncertRaster2 = np.zeros(shape=(openRaster.RasterYSize, openRaster.RasterXSize))
        for i in range(0, openRaster.RasterYSize):
            for j in range(0, openRaster.RasterXSize):
                
                #Distanz zu nächstem Punkt
                coords = self.pixel2world(geoTrans, j, i)  
                dist2neighbor = kdtree.query(coords)
                dist = dist2neighbor[0]
                #print(dist)
                classif = values[dist2neighbor[1]]
                #print(classif)

                #Variation der Nachbartypen
                nearPoints = kdtree.query((coords), k=int(neighbors), p=2, distance_upper_bound=float(maxDistance))[1]
                change = 0.5**2
                typs = []
                classes = 1
                if len(nearPoints) >0:
                    for nearpoint in nearPoints:
                        if nearpoint < len(listOfCoords):
                            typs.append(values[nearpoint])
                    classes = len(set(typs))
                    change = (classes*0.5)**2
                    
                    #falsche Klassifizierung in Voronoi
                    #falseClass = 1
                    #if Point(coords).intersects(shapeUnion):
                        #falseClass = 2

 
                    ## Uncertainty-Wert festschreiben
                    uncertRaster2[i][j] = dist*change#*falseClass
                
        
        # Raster schreiben
        outputFileNeighbor = self.path + "/UncertaintyRaster" + "/uncertaintyRaster_Neighbor.tiff"
        self.writeRaster(openRaster, uncertRaster2, outputFileNeighbor)
        
        print(str(datetime.datetime.now()) + " DONE!..........................................")



    def calculate_transitionRaster(self, cellsize, changematrix):
        """
        Berechnung der Variation der Übergangszonen
        """        
        # Create directory "/UncertaintyRaster" if it does not exist already
        if not os.path.exists(self.path + "/UncertaintyRaster"):
            os.makedirs(self.path + "/UncertaintyRaster")
        
        listOfCoords, values = self.import_points()
        layerPolys, shapeOfLayer = self.import_polygons()
        openRaster, raslist = self.prepare_raster(float(cellsize))
        
        outputFile = self.path + "/UncertaintyRaster" + "/uncertaintyRaster.tiff"

        print(str(datetime.datetime.now()) + " Calculating Voronoi-Polygons...................")
        points = np.array(listOfCoords)
        poly_shapes, represent_pts, poly_to_pt_assignments = voronoi_regions_from_coords(points, shapeOfLayer)
        shapeList = []
        for x in range(0, len(poly_shapes)):
            for polygon in layerPolys:
                if represent_pts[(poly_to_pt_assignments[x][0])].intersects(shape(polygon['geometry'])):
                    shapeList.append(poly_shapes[x].difference(shape(polygon['geometry'])))
        shapeUnion = unary_union(shapeList)
        # union als shp exportieren

        print(str(datetime.datetime.now()) + " Initializing kdTree............................")
        kdtree = KDTree(listOfCoords)
        
        print(str(datetime.datetime.now()) + " Calculating UncertaintyRaster.............................")
        geoTrans = openRaster.GetGeoTransform()

        print(str(datetime.datetime.now()) + "  --- Calculating ChangeRaster.........................")
        uncertRaster1 = np.zeros(shape=(openRaster.RasterYSize, openRaster.RasterXSize))
        
        for i in range(0, openRaster.RasterYSize):
            for j in range(0, openRaster.RasterXSize):
 
                fuz = 1.0
                coods = self.pixel2world(geoTrans, j, i)
                cellPoint = Point(coods)
                for polyS in poly_shapes:
                    if polyS.intersects(Point(coods)):
                        l = []
                        for coords in range(0, len(polyS.exterior.coords)-1):
                            lineS = LineString([polyS.exterior.coords[coords], polyS.exterior.coords[coords+1]])
                            typ1 = values[kdtree.query((lineS.centroid), k=2, p=2)[1][0]]
                            typ2 = values[kdtree.query((lineS.centroid), k=2, p=2)[1][1]]
                            distanceWidth = kdtree.query((lineS.centroid), k=2, p=2)[0][0]
                            dis = cellPoint.distance(lineS)
                            #print("Typen: "+str(typ1)+" // "+str(typ2))
                            l.append(1)
                            if str(typ1) != str(typ2):
                                #print("Changetyp: " + str(changematrix[typ1][typ2]))
                                if (dis < distanceWidth*int(changematrix[typ1][typ2])):
                                    l.append(0.5 + dis/ distanceWidth*int(changematrix[typ1][typ2]))
                        fuz = min(l)
                        break

                uncertRaster1[i][j] = fuz
                

        # Raster schreiben
        outputFileChange = self.path + "/UncertaintyRaster" + "/uncertaintyRaster_Change.tiff"
        self.writeRaster(openRaster, uncertRaster1, outputFileChange)
                
        print(str(datetime.datetime.now()) + " DONE!..........................................")



    
    def calculate_uncertaintyRasters(self, cellsize, neighbors, maxDistance, changematrix):
        """
        Berechnung beider Analysen in einer Funktion
        """
        
        
        # Create directory "/UncertaintyRaster" if it does not exist already
        if not os.path.exists(self.path + "/UncertaintyRaster"):
            os.makedirs(self.path + "/UncertaintyRaster")
        
        listOfCoords, values = self.import_points()
        layerPolys, shapeOfLayer = self.import_polygons()
        openRaster, raslist = self.prepare_raster(float(cellsize))
        
        outputFile = self.path + "/UncertaintyRaster" + "/uncertaintyRaster.tiff"

        print(str(datetime.datetime.now()) + " Calculating Voronoi-Polygons...................")
        points = np.array(listOfCoords)
        poly_shapes, represent_pts, poly_to_pt_assignments = voronoi_regions_from_coords(points, shapeOfLayer)
        shapeList = []
        for x in range(0, len(poly_shapes)):
            for polygon in layerPolys:
                if represent_pts[(poly_to_pt_assignments[x][0])].intersects(shape(polygon['geometry'])):
                    shapeList.append(poly_shapes[x].difference(shape(polygon['geometry'])))
        shapeUnion = unary_union(shapeList)
        # union als shp exportieren

        print(str(datetime.datetime.now()) + " Initializing kdTree............................")
        kdtree = KDTree(listOfCoords)
        
        print(str(datetime.datetime.now()) + " Calculating UncertaintyRaster.............................")
        geoTrans = openRaster.GetGeoTransform()

        print(str(datetime.datetime.now()) + "  --- Calculating ChangeRaster.........................")
        uncertRaster1 = np.zeros(shape=(openRaster.RasterYSize, openRaster.RasterXSize))
        
        for i in range(0, openRaster.RasterYSize):
            for j in range(0, openRaster.RasterXSize):
 
                fuz = 1.0
                coods = self.pixel2world(geoTrans, j, i)
                cellPoint = Point(coods)
                for polyS in poly_shapes:
                    if polyS.intersects(Point(coods)):
                        l = []
                        for coords in range(0, len(polyS.exterior.coords)-1):
                            lineS = LineString([polyS.exterior.coords[coords], polyS.exterior.coords[coords+1]])
                            typ1 = values[kdtree.query((lineS.centroid), k=2, p=2)[1][0]]
                            typ2 = values[kdtree.query((lineS.centroid), k=2, p=2)[1][1]]
                            distanceWidth = kdtree.query((lineS.centroid), k=2, p=2)[0][0]
                            dis = cellPoint.distance(lineS)
                            #print("Typen: "+str(typ1)+" // "+str(typ2))
                            l.append(1)
                            if str(typ1) != str(typ2):
                                #print("Changetyp: " + str(changematrix[typ1][typ2]))
                                if (dis < distanceWidth*int(changematrix[typ1][typ2])):
                                    l.append(0.5 + dis/ distanceWidth*int(changematrix[typ1][typ2]))
                        fuz = min(l)
                        break

                uncertRaster1[i][j] = fuz
                

        # Raster schreiben
        outputFileChange = self.path + "/UncertaintyRaster" + "/uncertaintyRaster_Change.tiff"
        self.writeRaster(openRaster, uncertRaster1, outputFileChange)
        
        
        print(str(datetime.datetime.now()) + "  --- Calculating NeighborRaster.............................")
        uncertRaster2 = np.zeros(shape=(openRaster.RasterYSize, openRaster.RasterXSize))
        for i in range(0, openRaster.RasterYSize):
            for j in range(0, openRaster.RasterXSize):
                
                #Distanz zu nächstem Punkt
                coords = self.pixel2world(geoTrans, j, i)  
                dist2neighbor = kdtree.query(coords)
                dist = dist2neighbor[0]
                #print(dist)
                classif = values[dist2neighbor[1]]
                #print(classif)

                #Variation der Nachbartypen
                nearPoints = kdtree.query((coords), k=int(neighbors), p=2, distance_upper_bound=float(maxDistance))[1]
                change = 0.5**2
                typs = []
                classes = 1
                if len(nearPoints) >0:
                    for nearpoint in nearPoints:
                        if nearpoint < len(listOfCoords):
                            typs.append(values[nearpoint])
                    classes = len(set(typs))
                    change = (classes*0.5)**2
                    
                    #falsche Klassifizierung in Voronoi
                    #falseClass = 1
                    #if Point(coords).intersects(shapeUnion):
                        #falseClass = 2

 
                    ## Uncertainty-Wert festschreiben
                    uncertRaster2[i][j] = dist*change#*falseClass
                
        
        # Raster schreiben
        outputFileNeighbor = self.path + "/UncertaintyRaster" + "/uncertaintyRaster_Neighbor.tiff"
        self.writeRaster(openRaster, uncertRaster2, outputFileNeighbor)
        
        print(str(datetime.datetime.now()) + " DONE!..........................................")


def is_number(string):
    try:
        float(string)
        return True
    except ValueError:
        return False