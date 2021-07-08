import fiona
import datetime
import os

from osgeo import gdal, ogr
from metpy import interpolate
from shapely.geometry import *
from shapely.ops import unary_union
from geovoronoi import voronoi_regions_from_coords

import numpy as np


class Interpolation():
    """
    Class for calculating and visualizing uncertainties with respect to uncertainties
    """

    def __init__(self, points, area, output_path, attribute, cellsize):
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
        self.output_wkt = output_path + "/voronoi_vergleich.wkt"
        self.output_shp = output_path + "/voronoi_vergleich.shp"
        self.attribute = attribute
        self.cellsize = cellsize
    
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
        for i in range(0, openRaster.RasterYSize):
            for j in range(0, openRaster.RasterYSize):
                grid[i][j] = gridArray[x]
                x = x+1
        self.writeRaster(openRaster, grid, filename)

    def prepare_raster(self):
        """
        Vorbereitung des Rasters
        """
        NoData_value = 0

        source_ds = ogr.Open(self.area)
        source_layer = source_ds.GetLayer()
        x_min, x_max, y_min, y_max = source_layer.GetExtent()
        x_res = int((x_max - x_min) / self.cellsize)
        y_res = int((y_max - y_min) / self.cellsize)
        target_ds = gdal.GetDriverByName('GTiff').Create(self.output_raster, x_res, y_res, 1, gdal.GDT_Byte)
        target_ds.SetGeoTransform((x_min, self.cellsize, 0, y_max, 0, -self.cellsize))
        band = target_ds.GetRasterBand(1)
        band.SetNoDataValue(NoData_value)
        band = None
        target_ds = None

        openRaster = gdal.Open(self.output_raster)
        geoTrans = openRaster.GetGeoTransform()

        rasterlist =[]
        for i in range(0, x_res):
            for j in range(0, y_res):
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
    

    def calculate_uncertainties(self, methods):
        """
        verschiedene Interpolationsverfahren
        """
        print("calculate_uncertainties")
        # Create directory "/Interpolationen" if it does not exist already
        if not os.path.exists(self.path + "/Interpolationen"):
            os.makedirs(self.path + "/Interpolationen")

        points, values = self.import_points()
        openRaster, raslist = self.prepare_raster()

        results = []

        for method in methods:
            print(method)
            method_str = str(method)
            if method_str == "barnes":
                interp_method = interpolate.interpolate_to_points(points, values, raslist, interp_type = method, minimum_neighbors = 10)
            else:
                interp_method = interpolate.interpolate_to_points(points, values, raslist, interp_type = method)
            results.append(interp_method)
            self.exportGrid(openRaster, interp_method, (self.path + f"/Interpolationen/{method_str}IntPol.tiff"))

        # Maximaler Unterschied zwischen den Interpolationsverfahren (zwei verschiedene numpy-Methoden; Ergebnis sollte gleich sein)
        #maximum = np.maximum.reduce(results)
        #minimum = np.minimum.reduce(results)
        #uncertainty = np.subtract(maximum, minimum)

        maxi = np.asarray(results).max(0)
        mini = np.asarray(results).min(0)
        uncertainty = np.subtract(maxi, mini)
        
        self.exportGrid(openRaster, uncertainty, (self.path + "/uncertainty.tiff"))
        
    
    def calculate_uncertainties_with_inputUncertainties(self, methods, uncertainty):
        """
        verschiedene Interpolationsverfahren
        """
        print("calculate_uncertainties_with_inputUncertainties")
        # Create directory "/Interpolationen" if it does not exist already
        if not os.path.exists(self.path + "/Interpolationen"):
            os.makedirs(self.path + "/Interpolationen")

        points, valuesHigh, valuesLow = self.import_points_with_uncertainties(uncertainty)
        openRaster, raslist = self.prepare_raster()

        results = []

        for method in methods:
            print(method)
            method_str = str(method)
            if method_str == "barnes":
                interp_methodHigh = interpolate.interpolate_to_points(points, valuesHigh, raslist, interp_type = method, minimum_neighbors = 10)
                interp_methodLow = interpolate.interpolate_to_points(points, valuesLow, raslist, interp_type = method, minimum_neighbors = 10)
            else:
                interp_methodHigh = interpolate.interpolate_to_points(points, valuesHigh, raslist, interp_type = method)
                interp_methodLow = interpolate.interpolate_to_points(points, valuesLow, raslist, interp_type = method)
            results.append(interp_methodHigh)
            results.append(interp_methodLow)
            self.exportGrid(openRaster, interp_methodHigh, (self.path + f"/Interpolationen/{method_str}IntPol.tiff"))

        # Maximaler Unterschied zwischen den Interpolationsverfahren (zwei verschiedene numpy-Methoden; Ergebnis sollte gleich sein)
        #maximum = np.maximum.reduce(results)
        #minimum = np.minimum.reduce(results)
        #uncertainty = np.subtract(maximum, minimum)

        maxi = np.asarray(results).max(0)
        mini = np.asarray(results).min(0)
        uncertainty = np.subtract(maxi, mini)
        
        self.exportGrid(openRaster, uncertainty, (self.path + "/uncertainty.tiff"))

    
    
    def voronoi_comparison(self):
        """
        Vergleich Voronoi-Polygone mit den vorhandenen Polygonen
        """
        print("Voronoi comparison")
        
        
        points = self.import_points()[0]
        layerPolys, shapeOfLayer = self.import_polygons()

        print(str(datetime.datetime.now()) + " Calculating Voronoi-Polygons...................")
        poly_shapes, represent_pts, poly_to_pt_assignments = voronoi_regions_from_coords(points, shapeOfLayer)
        
        voronoi_differences = []
        
        for pol in layerPolys:
            for i in range(0, len(poly_shapes)):
                if represent_pts[poly_to_pt_assignments[i][0]].intersects(shape(pol['geometry'])):
                    voronoi_differences.append(poly_shapes[i].difference(shape(pol['geometry'])))
                    
        union = Polygon()
        for poly in voronoi_differences:
            union = unary_union((union, poly))
            print(type(union))
        
        
        # Exporting WKT
        with open(self.output_wkt, "w", ) as target:
            #for element in voronoi_differences:
            target.write(union.wkt)
        
        
        # Exporting SHP
        schema = {
                'geometry': 'Polygon',
                'properties': {}
            }

        with fiona.open(self.output_shp, 'w', 'ESRI Shapefile', schema) as target:
            target.write({
                'geometry': mapping(union),
                'properties': {}
                })
        

    

def is_number(string):
    try:
        float(string)
        return True
    except ValueError:
        return False