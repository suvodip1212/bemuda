import osmnx as ox
import uncertainties as uc
import datetime
import math
import fiona
import csv

# Anwendungsfall
from isochrones import Isochrones
from interpolation import Interpolation
from rastercalc import UncertRasterCalculator

# Unsicherheitsbehandlung
from uncertainties import ufloat
from uncertainties.umath import *
#from uncertainties import unumpy

# GUI
from PyQt5.QtWidgets import (QApplication, QAbstractScrollArea, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
        QLineEdit, QPlainTextEdit, QPushButton, QRadioButton, QSpinBox, QTableWidget, QTableWidgetItem, QWidget)
from PyQt5.QtGui import QPixmap, QIcon, QFont, QColor
from PyQt5.QtCore import *
#from uihelp import Ui_Help


class Ui_Help(object):
    def setupUi(self, Help, values):
        Help.setObjectName("Test")
        Help.resize(1600, 500)

        #global vals
        
        Help.setWindowTitle("uncertainty matrix")
        
        self.gridLayoutWidget = QWidget(Help)
        self.gridLayoutWidget.setGeometry(QRect(15, 15, 1600, 450))
        #self.gridLayoutWidget.setObjectName("gridLayoutWidget")
        self.gridLayout = QGridLayout(self.gridLayoutWidget)
        #self.gridLayout.setContentsMargins(0, 0, 1, 1)
        self.gridLayout.setObjectName("gridLayout")
        self.plainTextEdit = QPlainTextEdit(self.gridLayoutWidget)
        font = QFont()
        font.setFamily("Times New Roman")
        font.setPointSize(10)
        font.setBold(True)
        font.setWeight(75)
        self.plainTextEdit.setFont(font)
        self.plainTextEdit.setFrameShape(QFrame.WinPanel)
        self.plainTextEdit.setFrameShadow(QFrame.Sunken)
        self.plainTextEdit.setLineWidth(1)
        self.plainTextEdit.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self.plainTextEdit.setReadOnly(True)
        self.plainTextEdit.setObjectName("plainTextEdit")
        #self.gridLayout.addWidget(self.plainTextEdit, 0, 0, 1, 1)
        
        csvInput = []
        with open('changematrix.csv', newline='') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                csvInput.append(row)
        
        vals = csvInput[0]
        matrix = csvInput[1:]
        
        values_len = len(vals)
        print(f"Anzahl Attribute: {values_len}")

        # Tabelle
        global table_a2        
        table_a2 = QTableWidget(values_len, values_len)
        table_a2.setHorizontalHeaderLabels(vals)
        table_a2.horizontalHeader().setDefaultSectionSize(140)
        table_a2.horizontalHeader().setStretchLastSection(True)
        table_a2.setVerticalHeaderLabels(vals)
        

        
        for i in range(values_len):
            for j in range(values_len):
                if i == j:
                    dark = QTableWidgetItem("")
                    table_a2.setItem(i, j, dark)
                    table_a2.item(i,j).setBackground(QColor(96, 96, 96))
                elif i>j:
                    spinBox = create_spinbox(10, 1)
                    #print(str(i)+" "+str(j))#+" "+str(matrix[i-1][j]))
                    spinBox.setValue(int(matrix[i-1][j]))
                    table_a2.setCellWidget(i, j, spinBox)
                else:
                    grey = QTableWidgetItem("")
                    table_a2.setItem(i, j, grey)
                    table_a2.item(i,j).setBackground(QColor(192, 192, 192))

        self.gridLayout.addWidget(table_a2, 0, 0, 1, 1)
        
        speichern = QPushButton(" save uncertainty matrix ")
        speichern.clicked.connect(self.printer)
        self.gridLayout.addWidget(speichern, 1, 0, 1, 0)

        space = QLabel("")
        self.gridLayout.addWidget(space, 2, 0, 2, 0)
    
    @staticmethod
    def printer():
        global table_a2
        global vals
        #print(table_a2.cellWidget(1,0).currentText())
        
        vals_len = len(vals)
        #print(vals_len)
        
        changematrix = dict()
        for element in vals:
            changematrix[str(element)] = {}
        
        for i in range(vals_len):
            for j in range(vals_len):
                if i>j:
                    print(vals[i]+" in "+vals[j]+": "+table_a2.cellWidget(i,j).text())
                    changematrix[str(vals[i])][str(vals[j])] = table_a2.cellWidget(i,j).text()
                    changematrix[str(vals[j])][str(vals[i])] = table_a2.cellWidget(i,j).text()
        
        print(changematrix)
        
        csvfile = "changematrix.csv"
        with open(csvfile, "w") as output:
            writer = csv.writer(output, lineterminator='\n')
            writer.writerow(vals)
            for i in range(1, vals_len):
                k = []
                for j in range(i):
                    if i>j:
                        k.append(table_a2.cellWidget(i,j).text())    
                writer.writerow(k)


def create_spinbox(maxi, value):
    spinBox = QSpinBox()
    spinBox.setMaximum(maxi)
    spinBox.setMinimum(1)
    spinBox.setValue(value)
    spinBox.setAlignment(Qt.AlignRight)
    spinBox.setVisible(False)
    return spinBox


class Help(QDialog, Ui_Help):
    def __init__(self, values, parent=None):
        super(Help, self).__init__(parent)
        self.setupUi(self, values)


class BEMUDA():
    
    def startGUI(self):
        

        # default-Werte
        self.attr = 4
        self.attributes = [] # Attribute input data
        
        self.folder_path = None # Output-Folder
        self.G = None # Graph

        # Inputfiles
        self.graph_fileName = None 
        self.points_fileName = None
        self.poly_fileName = None

        # Erstellung der GUI
        print(str(datetime.datetime.now()) + ":   preparing BEMUDA-GUI")
        app = QApplication([])
        app.setStyle('Fusion')
        app.setWindowIcon(QIcon('images/logo.jpg'))
        window = QWidget()
        
        
        # Werkzeug-Auswahl
        print(str(datetime.datetime.now()) + ":   preparing toolbox")
        self.tool_box = QHBoxLayout()
        task = QLabel("tool / analysis")
        self.tool_box.addWidget(task)
        self.tool_task = QComboBox()
        self.tool_task.addItem("tool selection")
        self.tool_task.addItem("isochrones")
        self.tool_task.addItem("interpolations")
        self.tool_task.addItem("raster calculation")
        #self.tool_task.addItem("Bufferung")
        #self.tool_task.addItem("Verschneidung")
        #self.tool_task.setToolTip("Auswahl der Analyse") # Hilfe-Button für Auswahl des Werkzeugs Isochronen / Interpolationen / ....
        self.tool_task.currentTextChanged.connect(self.tool_handling)
        self.tool_box.addWidget(self.tool_task)

        # Datei-Eingabe
        print(str(datetime.datetime.now()) + ":   preparing input box")
        
        # Default
        self.input_default_box = QHBoxLayout()
        self.input_default_label = QLabel("input file")
        self.input_default_box.addWidget(self.input_default_label)
        self.input_default_value = QPushButton(" folder...")
        self.input_default_value.setStyleSheet("Text-align:left")
        self.input_default_value.setEnabled(False)
        self.input_default_box.addWidget(self.input_default_value)
        
        ## Isochronen
        print(str(datetime.datetime.now()) + ":   - isochrones")
        self.input_isochrones_box = QHBoxLayout()
        self.input_isochrones_label = QLabel("input file")
        self.input_isochrones_box.addWidget(self.input_isochrones_label)
        self.input_isochrones_value = QPushButton(" folder...")
        self.input_isochrones_value.setStyleSheet("Text-align:left")
        self.input_isochrones_value.clicked.connect(self.input_isochrones_handling)
        self.input_isochrones_value.setToolTip("selection of input file (.graphml)") # Hilfe-Button für QPushButton Datei-Pfad (Eingabe Graph)
        self.input_isochrones_box.addWidget(self.input_isochrones_value)

        self.input_isochrones_box_param = QGridLayout()
        self.input_isochrones_box_param_mode_label = QLabel("travel mode")
        self.input_isochrones_box_param.addWidget(self.input_isochrones_box_param_mode_label, 0, 0, 1, 4)
        self.input_isochrones_box_param_mode_value = QComboBox()
        self.input_isochrones_box_param_mode_value.addItem("driving")
        self.input_isochrones_box_param_mode_value.addItem("walking")
        self.input_isochrones_box_param_mode_value.currentTextChanged.connect(self.input_isochrones_mode_handling)
        self.input_isochrones_box_param_mode_value.setToolTip("""
        <br>mode of locomotion:</br>
        <ul>
            <li>'driving'</li>
            <li>'walking'</li>
        </ul>
        
        The chosen mode should already be considered in the input file.</br>
        """) # Hilfe-Button für QComboBox zur Auswahl des Travel mode
        self.input_isochrones_box_param.addWidget(self.input_isochrones_box_param_mode_value, 0, 4, 1, 4)
        self.input_isochrones_box_param_range_label = QLabel("time in minutes")
        self.input_isochrones_box_param.addWidget(self.input_isochrones_box_param_range_label, 1, 0, 1, 4)
        self.input_isochrones_box_param_range_value = self.create_spinbox(60, 20)
        self.input_isochrones_box_param_range_value.setAlignment(Qt.AlignLeft)
        self.input_isochrones_box_param_range_value.setVisible(True)
        self.input_isochrones_box_param_range_value.setToolTip("travel time (in minutes)") # Hilfe-Button für spinbox zur Auswahl der Reisezeit (Zeit in Minuten)
        self.input_isochrones_box_param.addWidget(self.input_isochrones_box_param_range_value, 1, 4, 1, 4)
        self.input_isochrones_box_param_coords_label = QLabel("starting point (lat, lon)")
        self.input_isochrones_box_param.addWidget(self.input_isochrones_box_param_coords_label, 2, 0, 1, 4)
        self.input_isochrones_box_param_coords_value = QLineEdit("53.540342, 10.005247")
        self.input_isochrones_box_param_coords_value.setAlignment(Qt.AlignLeft)
        self.input_isochrones_box_param_coords_value.setToolTip("starting point coordinates (WGS 84)") # Hilfe-Button für QLineEdit zur Angabe des Starpunkts (lat,lon)
        self.input_isochrones_box_param.addWidget(self.input_isochrones_box_param_coords_value, 2, 4, 1, 4)
        
        self.input_isochrones_list = [self.input_isochrones_label, self.input_isochrones_value, self.input_isochrones_box_param_mode_label, self.input_isochrones_box_param_mode_value,
                                      self.input_isochrones_box_param_range_label, self.input_isochrones_box_param_range_value, self.input_isochrones_box_param_coords_label,
                                      self.input_isochrones_box_param_coords_value]
        self.set_visible(self.input_isochrones_list, False)        
        

        ## Interpolationen
        print(str(datetime.datetime.now()) + ":   - interpolations")
        self.input_interpol_points = QHBoxLayout()
        # Set Data Input: Input-Datei Punktlayer
        self.input_interpol_pointlayer_label = QLabel("input file (points)") 
        self.input_interpol_points.addWidget(self.input_interpol_pointlayer_label)
        self.input_interpol_pointlayer_value = QPushButton(" folder...")
        self.input_interpol_pointlayer_value.setStyleSheet("Text-align:left")
        self.input_interpol_pointlayer_value.clicked.connect(self.input_interpol_read_points)
        self.input_interpol_pointlayer_value.clicked.connect(self.input_interpol_handling)
        self.input_interpol_pointlayer_value.setToolTip("point data which should be interpolated") # Hilfe-Button für QPushButton Datei-Pfad (Punktlayer)
        self.input_interpol_points.addWidget(self.input_interpol_pointlayer_value)
        # Set Data Input: Input-Datei Flächenlayer
        self.input_interpol_polygon = QHBoxLayout()
        self.input_interpol_polygonlayer_label = QLabel("input file (bounding area)")
        self.input_interpol_polygon.addWidget(self.input_interpol_polygonlayer_label)
        self.input_interpol_polygonlayer_value = QPushButton(" folder...")
        self.input_interpol_polygonlayer_value.setStyleSheet("Text-align:left")
        self.input_interpol_polygonlayer_value.clicked.connect(self.input_interpol_read_polygons)
        self.input_interpol_polygonlayer_value.clicked.connect(self.input_interpol_handling)
        self.input_interpol_polygonlayer_value.setToolTip("""
            <br>input file (polygons) used as,</br>
            <ul>
                <li>the bounding area for the interpolation</li>
                <li>the reference for the voronoi comparison</li>
            </ul>
            """) # Hilfe-Button für QPushButton Datei-Pfad (Flächenlayer)
        self.input_interpol_polygon.addWidget(self.input_interpol_polygonlayer_value)
        
        
        ## Attributauswahl
        self.input_interpol_attribute = QGridLayout()
        self.input_interpol_attribute_label = QLabel("attribute selection")
        self.input_interpol_attribute_label.setEnabled(False)
        self.input_interpol_attribute.addWidget(self.input_interpol_attribute_label, 0, 0, 1, 4)
        self.input_interpol_attribute_value = QComboBox()
        self.input_interpol_attribute_value.setEnabled(False)
        self.input_interpol_attribute_value.currentTextChanged.connect(self.input_interpol_attribute_handling)
        self.input_interpol_attribute_value.setToolTip("numerical attribute from the point layer which should be interpolated") # Hilfe-Button für QComboBox choose_attribute Auswahl des Attributes
        self.input_interpol_attribute.addWidget(self.input_interpol_attribute_value, 0, 4, 1, 4)
        
        ## Zellengröße
        self.input_interpol_cellsize = QHBoxLayout()
        self.input_interpol_cellsize_label = QLabel("cell size (m)")
        #self.input_interpol_cellsize_label.setEnabled(False)
        self.input_interpol_attribute.addWidget(self.input_interpol_cellsize_label, 1, 0, 1, 4)
        # Value
        self.input_interpol_cellsize_value = QLineEdit("100")
        #self.input_interpol_cellsize_value.setEnabled(False)
        self.input_interpol_cellsize_value.setAlignment(Qt.AlignLeft)
        self.input_interpol_cellsize_value.setToolTip("grid cell size in m") # Hilfe-Button für QLineEdit Zellengröße (m)
        self.input_interpol_attribute.addWidget(self.input_interpol_cellsize_value, 1, 4, 1, 4)
        
        
        self.input_interpol_list = [self.input_interpol_pointlayer_label,
                                    self.input_interpol_pointlayer_value,
                                    self.input_interpol_polygonlayer_label,
                                    self.input_interpol_polygonlayer_value,
                                    self.input_interpol_attribute_label,
                                    self.input_interpol_attribute_value,
                                    self.input_interpol_cellsize_label,
                                    self.input_interpol_cellsize_value]
        #print(type(self.input_interpol_list))
        
        # Set Interpolationen Input fields invisible
        self.set_visible(self.input_interpol_list, False)
           

        ## Rasterrechner
        print(str(datetime.datetime.now()) + ":   - raster calculations")
        self.input_rastercalc_points = QHBoxLayout()
        # Set Data Input: Input-Datei Punktlayer
        self.input_rastercalc_pointlayer_label = QLabel("input file (points)") 
        self.input_rastercalc_points.addWidget(self.input_rastercalc_pointlayer_label)
        self.input_rastercalc_pointlayer_value = QPushButton(" folder...")
        self.input_rastercalc_pointlayer_value.setStyleSheet("Text-align:left")
        self.input_rastercalc_pointlayer_value.clicked.connect(self.input_rastercalc_read_points)
        self.input_rastercalc_pointlayer_value.clicked.connect(self.input_rastercalc_handling)
        self.input_rastercalc_pointlayer_value.setToolTip("input data, on which the calculations should be based on") # Hilfe-Button für QPushButton Datei-Pfad (Punktlayer)
        self.input_rastercalc_points.addWidget(self.input_rastercalc_pointlayer_value)
        # Set Data Input: Input-Datei Flächenlayer
        self.input_rastercalc_polygon = QHBoxLayout()
        self.input_rastercalc_polygonlayer_label = QLabel("input file (area)")
        self.input_rastercalc_polygon.addWidget(self.input_rastercalc_polygonlayer_label)
        self.input_rastercalc_polygonlayer_value = QPushButton(" folder...")
        self.input_rastercalc_polygonlayer_value.setStyleSheet("Text-align:left")
        self.input_rastercalc_polygonlayer_value.clicked.connect(self.input_rastercalc_read_polygons)
        self.input_rastercalc_polygonlayer_value.clicked.connect(self.input_rastercalc_handling)
        self.input_rastercalc_polygonlayer_value.setToolTip("""
            input file(polygon) which determines the bounding area for the calculations
            """) # Hilfe-Button für QPushButton Datei-Pfad (Flächenlayer)
        self.input_rastercalc_polygon.addWidget(self.input_rastercalc_polygonlayer_value)
        
        ## Attributauswahl 
        self.input_rastercalc_attribute = QHBoxLayout()
        self.input_rastercalc_attribute_label = QLabel("attribute selection")
        self.input_rastercalc_attribute_label.setEnabled(False)
        self.input_rastercalc_attribute.addWidget(self.input_rastercalc_attribute_label)
        self.input_rastercalc_attribute_value = QComboBox()
        self.input_rastercalc_attribute_value.setEnabled(False)
        self.input_rastercalc_attribute_value.currentTextChanged.connect(self.input_rastercalc_attribute_handling)
        self.input_rastercalc_attribute_value.setToolTip("attribute selection of the input layer for calculating the transition zones (only attributes with 10 or less different values") # Hilfe-Button für QComboBox self.input_rastercalc_attribute_value (Kreuz-Tabelle öffnet sich nach Auswahl)
        self.input_rastercalc_attribute.addWidget(self.input_rastercalc_attribute_value)
        
        # Set Rastercalcs Input fields invisible
        self.set_visible((self.input_rastercalc_pointlayer_label,
                          self.input_rastercalc_pointlayer_value,
                          self.input_rastercalc_polygonlayer_label,
                          self.input_rastercalc_polygonlayer_value,
                          self.input_rastercalc_attribute_label,
                          self.input_rastercalc_attribute_value), False)
        self.input_rastercalc_list = [self.input_rastercalc_pointlayer_label,
                                      self.input_rastercalc_pointlayer_value,
                                      self.input_rastercalc_polygonlayer_label,
                                      self.input_rastercalc_polygonlayer_value,
                                      self.input_rastercalc_attribute_label,
                                      self.input_rastercalc_attribute_value]
        
        # Set Rastercalc Input fields invisible
        self.set_visible(self.input_rastercalc_list, False)
        
        ## Picture
        print(str(datetime.datetime.now()) + ":   prepare diagram")
        pic = QLabel()
        pic_konzept = QPixmap("images/Konzept_breit_en.png")
        pic.setPixmap(pic_konzept.scaledToWidth(1500)) 
        

        print(str(datetime.datetime.now()) + ":   preparing data box")
        # Parameter-Eingabe
        
        # Input-Analyse - Isochronen
        print(str(datetime.datetime.now()) + ":   - isochrones")
        self.data_isochrones_box = QGroupBox("uncertainties in input data")
        self.data_isochrones_layout = QGridLayout()
        self.data_isochrones_mode = QComboBox()
        self.data_isochrones_mode.addItem("no uncertainties")
        self.data_isochrones_mode.addItem("define uncertainties")
        self.data_isochrones_mode.addItem("describe uncertainties")
        self.data_isochrones_mode.currentTextChanged.connect(self.data_isochrones_uncert_handling)
        self.data_isochrones_box.setToolTip("""
        <br>handling of uncertainties in the input data:</br>
        <ul>
            <li>no uncertainties: no propagation of input data uncertainties</li>
            <li>define uncertainties: uncertainties of (numerical) attributes can be defined as percentages, e.g. attribute a = 200 with 5 % uncertainty will be propagated as 200 +/- 10 </li>
            <li>describe uncertainties: uncertainties of (numerical) attributes can be described with linguistic approximators ("about", "approximately", etc.), which the will be converted to numerical uncertainty values (see study of Ferson et al. (2015))</li>
        </ul>
        """) # Hilfe-Button für QComboBox zur Definition der Unsicherheiten in den Eingangsdaten (keine Unsicherheit, Unsicherheit definieren, Unsicherheit beschreiben)
        self.data_isochrones_layout.addWidget(self.data_isochrones_mode)
        data_isochrones_space = QLabel("")
        #self.data_isochrones_layout.addWidget(data_isochrones_space)
        self.data_isochrones_table_uncert_definition = QTableWidget(self.attr, 2) # Tabelle für Unsicherheiten definieren
        self.data_isochrones_table_uncert_definition.setVisible(False) 
        self.data_isochrones_layout.addWidget(self.data_isochrones_table_uncert_definition)
        self.data_isochrones_table_uncert_description = QTableWidget(self.attr, 2) # Tabelle für Unsicherheiten beschreiben
        self.data_isochrones_table_uncert_description.setVisible(False)
        self.data_isochrones_layout.addWidget(self.data_isochrones_table_uncert_description)
        self.data_isochrones_layout.addWidget(data_isochrones_space)
        self.data_isochrones_box.setLayout(self.data_isochrones_layout)

        self.data_isochrones_list = [self.data_isochrones_mode]

        # Input-Analyse - Interpolationen
        print(str(datetime.datetime.now()) + ":   - interpolations")
        self.data_interpol_box = QGroupBox("uncertainties in input data")
        self.data_interpol_layout = QGridLayout()
        self.data_interpol_layout.setAlignment(Qt.AlignTop)
        ## Unsicherheiten definieren
        self.data_interpol_mode = QComboBox()
        self.data_interpol_mode.addItem("no uncertainties")
        self.data_interpol_mode.addItem("define uncertainties")
        self.data_interpol_mode.addItem("describe uncertainties")
        self.data_interpol_mode.currentTextChanged.connect(self.data_interpol_uncert_handling)
        self.data_interpol_mode.setVisible(False)
        self.data_interpol_mode.setEnabled(False)
        self.data_interpol_box.setToolTip("""
        <br>Beschreibung der Unsicherheit in den Eingangsdaten</br>
        <ul>
            <li>no uncertainties: no propagation of input data uncertainties</li>
            <li>define uncertainties: uncertainties of (numerical) attributes can be defined as percentages, e.g. attribute a = 200 with 5 % uncertainty will be propagated as 200 +/- 10 </li>
            <li>describe uncertainties: uncertainties of (numerical) attributes can be described with linguistic approximators ("about", "approximately", etc.), which the will be converted to numerical uncertainty values (see study of Ferson et al. (2015))</li>
        </ul>
        """) # Hilfe-Button für QComboBox zur Definition der Unsicherheiten in den Eingangsdaten (keine Unsicherheit, Unsicherheit definieren, Unsicherheit beschreiben)
        self.data_interpol_layout.addWidget(self.data_interpol_mode)
        data_interpol_space = QLabel("")
        self.data_interpol_layout.addWidget(data_interpol_space)
        self.data_interpol_table_uncert_definition = QTableWidget(1, 2)
        self.data_interpol_table_uncert_definition.setVisible(False)
        self.data_interpol_layout.addWidget(self.data_interpol_table_uncert_definition)
        self.data_interpol_table_uncert_description = QTableWidget(1, 2)
        self.data_interpol_table_uncert_description.setVisible(False)
        self.data_interpol_layout.addWidget(self.data_interpol_table_uncert_description)
        self.data_interpol_layout.addWidget(data_interpol_space)
        self.data_interpol_box.setLayout(self.data_interpol_layout)
        
        self.data_interpol_list = [self.data_interpol_mode, self.data_interpol_table_uncert_definition, self.data_interpol_table_uncert_description]

        ######################################
        # Input-Analyse - Rasterrechner
        print(str(datetime.datetime.now()) + ":   - raster calculation")
        self.data_rastercalc_box = QGroupBox("uncertainties in input data")
        self.data_rastercalc_layout = QGridLayout()
        self.data_rastercalc_layout.setAlignment(Qt.AlignTop)
        ### Kreuz-Tabelle
        data_interpol_space = QLabel("")
        self.data_rastercalc_layout.addWidget(data_interpol_space)
        self.data_rastercalc_layout.addWidget(data_interpol_space)
        self.data_rastercalc_matrix = QPushButton(" define uncertainty matrix ")
#         self.data_rastercalc_matrix.setToolTip("""
#         <br>Definition einer Unsicherheitsmatrix, in der die Breite der Übergänge zwischen den einzelnen Klassen mit Werten
#         zwischen 1 (scharfer Übergang) und 10 (langsamer Übergang) angegeben werden kann.</br>
#         <br></br>
#         <br>Beispiel Landklassifikation:</br>
#         <br>Der Übergang zwischen den Kategorien Wohnfläche und Parkfläche kann sehr scharf sein, der Übergang zwischen den
#         Kategorien Laub- und Mischwald sehr langsam</br>
#         """)
        self.data_rastercalc_box.setLayout(self.data_rastercalc_layout)

        # Parameter-Box
        print(str(datetime.datetime.now()) + ":   preparing parameter box")
        
        # Isochronen
        print(str(datetime.datetime.now()) + ":   - isochrones")
        self.param_isochrones_box = QGroupBox("model uncertainties")
        self.param_isochrones_layout = QGridLayout()

        self.param_isochrones_speeduncert_label = QLabel("velocity uncertainty in %")
        self.param_isochrones_layout.addWidget(self.param_isochrones_speeduncert_label, 2, 0, 1, 4)
        

        self.param_isochrones_speeduncert_value = QLineEdit("0.0")
        self.param_isochrones_speeduncert_value.setAlignment(Qt.AlignCenter)
        self.param_isochrones_speeduncert_value.setToolTip("""
        <br>velocity uncertainty in %</br>
        <br>   </br>
        <br>Example: for covering a distance of 2 km, the calculated time is 3 minutes. With a supposed velocity uncertainty of 15 %, the calculated time
        for covering the distance varies between 2:33 minutes (no traffic jams, no traffic lights) and 3:27 minutes (due to traffic jams, red lights).
        Therefore, the value of 3 Min +/-27 s is propagated.</br>
        """) # Hilfe-Button für QLineEdit zur Geschwindigkeitsunsicherheit
        self.param_isochrones_layout.addWidget(self.param_isochrones_speeduncert_value, 2, 4, 1, 2)

        param_isochrones_space = QLabel("")
        self.param_isochrones_layout.addWidget(param_isochrones_space, 3, 0, 1, 6)

        self.param_isochrones_heading = QLabel("default parameters")
        self.param_isochrones_layout.addWidget(self.param_isochrones_heading, 5, 0, 1, 6)
        self.param_isochrones_line = self.create_line()
        self.param_isochrones_layout.addWidget(self.param_isochrones_line, 6, 0, 1, 6)
        
        self.param_isochrones_list = [self.param_isochrones_speeduncert_label, self.param_isochrones_speeduncert_value, self.param_isochrones_heading, self.param_isochrones_line]
        
        # Walking
        self.param_isochrones_walking_speed_label = QLabel("walking speed (km/h)")
        self.param_isochrones_walking_speed_value = self.create_spinbox(10, 5)
        self.param_isochrones_walking_speed_value.setToolTip("walking speed used for isochrone calculation") # Hilfe-Button für spinbox Walking speed (km/h)
        self.param_isochrones_layout.addWidget(self.param_isochrones_walking_speed_label, 7, 0, 1, 2)
        self.param_isochrones_layout.addWidget(self.param_isochrones_walking_speed_value, 7, 4, 1, 2)
        param_isochrones_walking_space = QLabel("")
        self.param_isochrones_layout.addWidget(param_isochrones_walking_space, 8, 0, 1, 6)
        
        self.param_isochrones_walking_list = [self.param_isochrones_walking_speed_label, self.param_isochrones_walking_speed_value]
        self.set_visible(self.param_isochrones_walking_list, False)

        # Driving
        self.param_isochrones_driving_labels_label = QLabel("value")
        self.param_isochrones_layout.addWidget(self.param_isochrones_driving_labels_label, 7, 0, 1, 2)

        self.param_isochrones_driving_labels_speed = QLabel("speed (km/h)")
        self.param_isochrones_driving_labels_speed.setAlignment(Qt.AlignRight)
        self.param_isochrones_layout.addWidget(self.param_isochrones_driving_labels_speed, 7, 2, 1, 2)

        self.param_isochrones_driving_labels_uncert = QLabel("uncertainty (+/-)")
        self.param_isochrones_driving_labels_uncert.setAlignment(Qt.AlignRight)
        self.param_isochrones_layout.addWidget(self.param_isochrones_driving_labels_uncert, 7, 4, 1, 2)

        self.param_isochrones_driving_novalue_label = QLabel("'no limit'")
        self.param_isochrones_driving_novalue_value = self.create_spinbox(250, 130)
        self.param_isochrones_driving_novalue_value.setToolTip("maximum speed used for roads without any limit (e.g. german motorways). ") # Hilfe-Button für spinbox 'no limit' Geschwindigkeit
        self.param_isochrones_driving_novalue_value_uncert = self.create_spinbox(250, 0)
        self.param_isochrones_driving_novalue_value_uncert.setToolTip("uncertainty value for the maximum speed in km/h (value of which the maximum speed can vary in both directions (+/-))") # Hilfe-Button für spinbox 'no limit' Unsicherheit (+/-)
        self.param_isochrones_layout.addWidget(self.param_isochrones_driving_novalue_label, 8, 0, 1, 2)
        self.param_isochrones_layout.addWidget(self.param_isochrones_driving_novalue_value, 8, 2, 1, 2)
        self.param_isochrones_layout.addWidget(self.param_isochrones_driving_novalue_value_uncert, 8, 4, 1, 2)

        self.param_isochrones_driving_nodata_label = QLabel("'no data'")
        self.param_isochrones_driving_nodata_value = self.create_spinbox(130, 50)
        self.param_isochrones_driving_nodata_value.setToolTip("speed limit for roads without any regarding information in the input data. ") # Hilfe-Button für spinbox 'no data' Geschwindigkeit
        self.param_isochrones_driving_nodata_value_uncert = self.create_spinbox(130, 0)
        self.param_isochrones_driving_nodata_value_uncert.setToolTip("uncertainty for the speed limit in km/h (value of which the speed limit can vary in both directions (+/-))") # Hilfe-Button für spinbox 'no data' Unsicherheit (+/-)
        self.param_isochrones_layout.addWidget(self.param_isochrones_driving_nodata_label, 9, 0, 1, 2)
        self.param_isochrones_layout.addWidget(self.param_isochrones_driving_nodata_value, 9, 2, 1, 2)
        self.param_isochrones_layout.addWidget(self.param_isochrones_driving_nodata_value_uncert, 9, 4, 1, 2)

        self.param_isochrones_layout.addWidget(param_isochrones_space)
        self.param_isochrones_box.setLayout(self.param_isochrones_layout)

        self.param_isochrones_driving_list = [self.param_isochrones_driving_labels_label, self.param_isochrones_driving_labels_speed, self.param_isochrones_driving_labels_uncert,
                          self.param_isochrones_driving_novalue_label, self.param_isochrones_driving_nodata_label, self.param_isochrones_driving_novalue_value,
                          self.param_isochrones_driving_novalue_value_uncert, self.param_isochrones_driving_nodata_value, self.param_isochrones_driving_nodata_value_uncert]
        self.set_visible(self.param_isochrones_driving_list, True)


        # Interpolationen
        print(str(datetime.datetime.now()) + ":   - interpolations")
        
        ### Setzen der Parameter für Analyse 1
        self.param_interpol_box = QGroupBox("selection of interpolation methods")
        self.param_interpol_box.setToolTip("interpolation methods that will be used for the uncertainty calculation")
        self.param_interpol_layout = QGridLayout()
        #### Linear
        self.param_interpol_button_linear = QCheckBox("Linear")
        self.param_interpol_button_linear.setChecked(True)
        self.param_interpol_layout.addWidget(self.param_interpol_button_linear, 0, 0)
        #### Nearest
        self.param_interpol_button_nearest = QCheckBox("Nearest Neighbor")
        self.param_interpol_button_nearest.setChecked(True)
        self.param_interpol_layout.addWidget(self.param_interpol_button_nearest, 0, 1)
        #### Cubic
        self.param_interpol_button_cubic = QCheckBox("Cubic")
        self.param_interpol_button_cubic.setChecked(True)
        self.param_interpol_layout.addWidget(self.param_interpol_button_cubic, 1, 0)
        #### Rbf
        self.param_interpol_button_rbf = QCheckBox("Radial Basis Function")
        self.param_interpol_button_rbf.setChecked(True)
        self.param_interpol_layout.addWidget(self.param_interpol_button_rbf, 1, 1)
        #### Barnes
        self.param_interpol_button_barnes = QCheckBox("Barnes")
        self.param_interpol_button_barnes.setChecked(True)
        self.param_interpol_layout.addWidget(self.param_interpol_button_barnes, 2, 0)
        #### Cressman
        self.param_interpol_button_cressman = QCheckBox("Cressman")
        self.param_interpol_button_cressman.setChecked(True)
        self.param_interpol_layout.addWidget(self.param_interpol_button_cressman, 2, 1)
        #### Natural Neighbor
        self.param_interpol_button_natural = QCheckBox("Natural Neighbor (long computation time)")
        self.param_interpol_button_natural.setChecked(False)
        self.param_interpol_layout.addWidget(self.param_interpol_button_natural, 3, 0, 2, 0)
        ##### Set Layout for Box "Auswahl der Interpolationsmethoden"
        self.param_interpol_box.setLayout(self.param_interpol_layout)

        self.param_interpol_list = [self.param_interpol_button_linear,
                                    self.param_interpol_button_nearest,
                                    self.param_interpol_button_cubic,
                                    self.param_interpol_button_rbf,
                                    self.param_interpol_button_barnes,
                                    self.param_interpol_button_cressman,
                                    self.param_interpol_button_natural]
        self.set_visible(self.param_interpol_list, False)

        # Rasterrechner
        print(str(datetime.datetime.now()) + ":   - raster calculation")
        
        ### Setzen der Parameter für Analyse 2
        self.param_rastercalc_box = QGroupBox("uncertainty raster calculation parameters")
        self.param_rastercalc_layout = QGridLayout()
        #### Zellengröße (m)
        # Label
        self.param_rastercalc_cellsize_label = QLabel("cellsize (m)")
        self.param_rastercalc_cellsize_label.setEnabled(False)
        self.param_rastercalc_layout.addWidget(self.param_rastercalc_cellsize_label, 2, 0, 1, 4)
        # Value
        self.param_rastercalc_cellsize_value = QLineEdit("100")
        self.param_rastercalc_cellsize_value.setEnabled(False)
        self.param_rastercalc_cellsize_value.setAlignment(Qt.AlignCenter)
        self.param_rastercalc_cellsize_value.setToolTip("cellsize in m") # Hilfe-Button für QLineEdit Zellengröße (m)
        self.param_rastercalc_layout.addWidget(self.param_rastercalc_cellsize_value, 2, 4, 1, 2)
        ####Anzahl der untersuchten Nachbarn in der Umgebeung
        # Label
        self.param_rastercalc_neighbors_label = QLabel("accounted neighbors")
        self.param_rastercalc_neighbors_label.setEnabled(False)
        self.param_rastercalc_layout.addWidget(self.param_rastercalc_neighbors_label, 3, 0, 1, 4)
        # Value
        self.param_rastercalc_neighbors_value = QLineEdit("3")
        self.param_rastercalc_neighbors_value.setEnabled(False)
        self.param_rastercalc_neighbors_value.setAlignment(Qt.AlignCenter)
        self.param_rastercalc_neighbors_value.setToolTip("""
        Number of accounted (point) neighbors which are included in the analysis. The more different class types
        are located between the neighbors, the higher is the calculate uncertainty value of each cell.
        """) # Hilfe-Button für QLineEdit Anzahl untersuchter Nachbarn
        self.param_rastercalc_layout.addWidget(self.param_rastercalc_neighbors_value, 3, 4, 1, 2)
        ####maximale Distanz zu Nachbarn, damit dieser berücksichtigt wird
        # Label
        self.param_rastercalc_distance_label = QLabel("maximum distance to neighbours (m)")
        self.param_rastercalc_distance_label.setEnabled(False)
        self.param_rastercalc_layout.addWidget(self.param_rastercalc_distance_label, 4, 0, 1, 4)
        # Value
        self.param_rastercalc_distance_value = QLineEdit("1000")
        self.param_rastercalc_distance_value.setEnabled(False)
        self.param_rastercalc_distance_value.setAlignment(Qt.AlignCenter)
        self.param_rastercalc_distance_value.setToolTip("""
        The maximum distance of neighbors to get accounted for local variation calculation.The more different class types
        are located between the neighbors, the higher is the calculate uncertainty value of each cell.
        """) # Hilfe-Button für QLineEdit Max. Distanz zu Nachbarn (m)
        self.param_rastercalc_layout.addWidget(self.param_rastercalc_distance_value, 4, 4, 1, 2)
        ##### Set Layout for Box "Parameter für Rasterrechner der Unsicherheit"
        self.param_rastercalc_box.setLayout(self.param_rastercalc_layout)

        self.param_rastercalc_list = [self.param_rastercalc_box]

        # Analysis-Box
        print(str(datetime.datetime.now()) + ":   preparing analysis box")
        
        # Isochronen
        print(str(datetime.datetime.now()) + ":   - isochrones")

        self.analysis_isochrones_box = QGroupBox("aim of uncertainy analysis")
        self.analysis_isochrones_layout = QGridLayout()
        self.analysis_isochrones_erweitert_button = QCheckBox("extended analysis")
        self.analysis_isochrones_erweitert_button.setToolTip("""
        The "extended analysis" calulates the isochrone conventionally, while the uncertainty boundaries
        visualize the area between the minimal and maximal location of the isochrone when considering uncertainties.
        """) # Hilfe-Button für Button "Erweiterte Analyse"
        self.analysis_isochrones_vorsichtig_button = QCheckBox("cautions analysis")
        self.analysis_isochrones_vorsichtig_button.setToolTip("""
        The "cautious analysis" calculates the mean isochrone while already using the velocity uncertainty as a reducing factor,
        so the maximal location of the isochrone is the same as a conventional one without considering any uncertainty. 
        """) # Hilfe-Button für Button "Vorsichtige Analyse"
        self.analysis_isochrones_randwert_button = QCheckBox("marginal value analysis")
        self.analysis_isochrones_randwert_button.setEnabled(False)
        #self.analysis_isochrones_randwert_button.setToolTip("") # Hilfe-Button für Button "Randwert-Analyse"
        self.analysis_isochrones_layout.addWidget(self.analysis_isochrones_erweitert_button)
        self.analysis_isochrones_layout.addWidget(self.analysis_isochrones_vorsichtig_button)
        self.analysis_isochrones_layout.addWidget(self.analysis_isochrones_randwert_button)
        self.analysis_isochrones_box.setLayout(self.analysis_isochrones_layout)
        self.analysis_isochrones_box.setVisible(True)
        

        ## Modellierung - Interpolationen
        print(str(datetime.datetime.now()) + ":   - interpolations")
        ### Auswahl der Analyse 1 / 2
        self.analysis_interpol_box = QGroupBox("aim of uncertainty analysis")
        self.analysis_interpol_layout = QGridLayout()

        self.analysis_interpol_verfahren_button = QRadioButton("uncertainty through interpolation methods")
        self.analysis_interpol_verfahren_button.setChecked(True)
        self.analysis_interpol_verfahren_button.toggled.connect(self.analysis_interpol_handling)
        self.analysis_interpol_verfahren_button.setToolTip("""
        uncertainty through interpolation methods:
        pixelwise calculation of maximum difference between the selected interpolation methods.
        """) # Hilfe-Button für CheckBox Unsicherheit durch Interpolationsverfahren
        self.analysis_interpol_layout.addWidget(self.analysis_interpol_verfahren_button)

        self.analysis_interpol_voronoi_button = QRadioButton("Voronoi comparison")
        self.analysis_interpol_voronoi_button.toggled.connect(self.analysis_interpol_handling)
        self.analysis_interpol_voronoi_button.setToolTip("""
        Voronoi comparison:
        Identification of areas of the polygon layer which have different
        categories than the nearest neighbor from the point layer input.
        """)
        self.analysis_interpol_layout.addWidget(self.analysis_interpol_voronoi_button)
        
        self.analysis_interpol_layout.setAlignment(Qt.AlignTop)
        self.analysis_interpol_box.setLayout(self.analysis_interpol_layout)
        self.analysis_interpol_box.setVisible(False)
        self.analysis_interpol_box.setEnabled(False)

        ## Modellierung - Rasterrechner
        print(str(datetime.datetime.now()) + ":   - raster calculation")
        ### Auswahl der Analyse 1 / 2
        self.analysis_rastercalc_box = QGroupBox("aim of uncertainty analysis")
        self.analysis_rastercalc_layout = QGridLayout()
        
        self.analysis_rastercalc_rasterrechner_button = QRadioButton("uncertainty raster calculation")
        self.analysis_rastercalc_rasterrechner_button.setChecked(True)
        self.analysis_rastercalc_rasterrechner_button.toggled.connect(self.analysis_rastercalc_handling)
        self.analysis_rastercalc_rasterrechner_button.setToolTip("""
        <br>Uncertainty calculation for raster cells based on distances to nearest neighors and the number of
        different classes between them.</br>
        <br></br>
        <br>The uncertainty is therefore smaller, if many data points of the same class are in close distance, and
        bigger, if the nearest data points are more far away and belong to different classes.</br>
        """) # Hilfe-Button für CheckBox Rasterrechner der Unsicherheit
        self.analysis_rastercalc_layout.addWidget(self.analysis_rastercalc_rasterrechner_button)
        
        self.analysis_rastercalc_uebergang_button = QRadioButton("variation of transition zones")
        self.analysis_rastercalc_uebergang_button.toggled.connect(self.analysis_rastercalc_handling)
        self.analysis_rastercalc_uebergang_button.setToolTip("""
        (beta) calculation of transition zones between neighboring classes
        """) # Hilfe-Button für CheckBox Variation der Übergangszonen
        self.analysis_rastercalc_layout.addWidget(self.analysis_rastercalc_uebergang_button)
        self.analysis_rastercalc_uebergang_button.setEnabled(False)

        self.analysis_rastercalc_layout.setAlignment(Qt.AlignTop)
        self.analysis_rastercalc_box.setLayout(self.analysis_rastercalc_layout)
        self.analysis_rastercalc_box.setEnabled(False)
        self.analysis_rastercalc_box.setVisible(False)

        # Visualisierungs-Box
        print(str(datetime.datetime.now()) + ":   preparing visualization box")
        
        # Isochronen
        print(str(datetime.datetime.now()) + ":   - isochrones")
        ## Visualisierung - Isochronen
        self.viz_isochrones_box = QGroupBox("visualization techniques")
        self.viz_isochrones_layout = QGridLayout()
        self.viz_isochrones_schummerung_button = QCheckBox("shading")
        self.viz_isochrones_symbole_button = QCheckBox("symbols")
        self.viz_isochrones_noise_button = QCheckBox("noise annotation lines")
        self.viz_isochrones_uncertmap_button = QCheckBox("uncertainty map")
        self.viz_isochrones_polygone_button = QCheckBox("uncertainty polygons")
        self.viz_isochrones_points_button = QCheckBox("uncertainty points")
        self.viz_isochrones_network_button = QCheckBox("uncertainty network")
        self.viz_isochrones_layout.addWidget(self.viz_isochrones_points_button)
        self.viz_isochrones_layout.addWidget(self.viz_isochrones_polygone_button)
        self.viz_isochrones_layout.addWidget(self.viz_isochrones_network_button)
        self.viz_isochrones_layout.addWidget(self.viz_isochrones_uncertmap_button)
        #self.viz_isochrones_layout.addWidget(self.viz_isochrones_schummerung_button)
        #self.viz_isochrones_layout.addWidget(self.viz_isochrones_symbole_button)
        #self.viz_isochrones_layout.addWidget(self.viz_isochrones_noise_button)
        viz_isochrones_space = QLabel("")
        self.viz_isochrones_layout.addWidget(viz_isochrones_space)
        self.viz_isochrones_box.setLayout(self.viz_isochrones_layout)
        self.viz_isochrones_box.setToolTip("""
        <br>Visualization techniques:</br>
        <ul>
            <li>uncertainty points: visualization of network nodes (crossings) and their uncertainty of accessibility</li>
            <li>uncertainty polygones: visualization of accessibility via alpha shapes</li>
            <li>uncertainty network: visualization of the network edges (roads) and their uncertainty of accessibility</li>
            <li>uncertainty map: visualization of the network egdes and their dominant source of uncertainty</li>
        </ul>
        <br></br>
        
        """)

        self.viz_isochrones_list = [self.viz_isochrones_points_button, self.viz_isochrones_polygone_button,
                                    self.viz_isochrones_network_button, self.viz_isochrones_uncertmap_button]
        
        ## Visualisierung - Interpolationen
        print(str(datetime.datetime.now()) + ":   - interpolations")
        self.viz_interpol_box = QGroupBox("visualization techniques")
        self.viz_interpol_layout = QGridLayout()
        self.viz_interpol_layout.setAlignment(Qt.AlignTop)
        self.viz_interpol_uncertmap_button = QCheckBox("uncertainty map")
        #self.viz_interpol_uncertmap_button.setToolTip("Unsicherheitskarte: Rastervisualisierung") # Hilfe-Button für QCheckBox Unsicherheitskarte
        self.viz_interpol_shades_button = QCheckBox("shading")
        #self.viz_interpol_shades_button.setToolTip("Lorem ipsum") # Hilfe-Button für QCheckBox Schummerung
        self.viz_interpol_layout.addWidget(self.viz_interpol_uncertmap_button)
        self.viz_interpol_layout.addWidget(self.viz_interpol_shades_button)
        self.viz_interpol_box.setLayout(self.viz_interpol_layout)
        
        self.viz_interpol_list = [self.viz_interpol_uncertmap_button,
                                  self.viz_interpol_shades_button]
        
        ## Visualisierung - Rasterrechner
        print(str(datetime.datetime.now()) + ":   - raster calculation")
        self.viz_rastercalc_box = QGroupBox("visualization techniques")
        self.viz_rastercalc_layout = QGridLayout()
        self.viz_rastercalc_layout.setAlignment(Qt.AlignTop)
        self.viz_rastercalc_uncertmap_button = QCheckBox("uncertainty map")
        #self.viz_rastercalc_uncertmap_button.setToolTip("Unsicherheitskarte: Rastervisualisierung") # Hilfe-Button für QCheckBox Unsicherheitskarte
        self.viz_rastercalc_shades_button = QCheckBox("shading")
        #self.viz_rastercalc_shades_button.setToolTip("Lorem ipsum") # Hilfe-Button für QCheckBox Schummerung
        self.viz_rastercalc_layout.addWidget(self.viz_rastercalc_uncertmap_button)
        self.viz_rastercalc_layout.addWidget(self.viz_rastercalc_shades_button)
        self.viz_rastercalc_box.setLayout(self.viz_rastercalc_layout)
        self.viz_rastercalc_box.setVisible(False)
        
        self.viz_rastercalc_list = [self.viz_rastercalc_uncertmap_button,
                                    self.viz_rastercalc_shades_button]
        
        # Output-Box
        print(str(datetime.datetime.now()) + ":   preparing output box")

        self.output_layout = QHBoxLayout()
        self.output_label = QLabel("output folder")

        self.output_layout.addWidget(self.output_label)
        self.output_button = QPushButton("output folder...")
        self.output_button.setToolTip("folder to save the output data and maps") # Hilfe-Button für QPushButton zur Auswahl des Output Ordners
        self.output_button.clicked.connect(self.output_button_handling)
        self.output_button.setEnabled(False)
        self.output_layout.addWidget(self.output_button)

        
        # Run-Box
        print(str(datetime.datetime.now()) + ":   preparing run box") 
        self.run_button = QPushButton("Calculate")
        self.run_button.setDefault(True)
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self.run_tool)

        # Erstelle GUI
        print(str(datetime.datetime.now()) + ":   preparing GUI") 
        line = self.create_line()
        line2 = self.create_line()
        line3 = self.create_line()
        line4 = self.create_line()

        self.mainLayout = QGridLayout()
        self.mainLayout.addLayout(self.tool_box, 0, 0, 1, 6)
        self.mainLayout.addWidget(line, 1, 0, 1, 6)
        
        # Inputfelder
        self.mainLayout.addLayout(self.input_default_box, 2, 0, 1, 6)
        self.mainLayout.addLayout(self.input_isochrones_box, 2, 0, 1, 6)
        self.mainLayout.addLayout(self.input_isochrones_box_param, 4, 0, 1, 6)
        
        self.mainLayout.addLayout(self.input_interpol_points, 2, 0, 1, 6)
        self.mainLayout.addLayout(self.input_interpol_polygon, 3, 0, 1, 6)
        self.mainLayout.addLayout(self.input_interpol_attribute, 4, 0, 1, 6)
        #self.mainLayout.addLayout(self.input_interpol_cellsize, 5, 0, 1, 6)
        
        self.mainLayout.addLayout(self.input_rastercalc_points, 2, 0, 1, 6)
        self.mainLayout.addLayout(self.input_rastercalc_polygon, 3, 0, 1, 6)
        self.mainLayout.addLayout(self.input_rastercalc_attribute, 4, 0, 1, 6)

        self.mainLayout.addWidget(line2, 5, 0, 1, 6)
        
        # BEMUDA-Picture
        self.mainLayout.addWidget(pic, 6, 0, 1, 6)
        
        # Inputdaten - Unsicherheiten
        self.mainLayout.addWidget(self.data_isochrones_box, 7, 0, 3, 2)
        self.mainLayout.addWidget(self.data_interpol_box, 7, 0, 3, 2)
        self.mainLayout.addWidget(self.data_rastercalc_box, 7, 0, 3, 2)
        
        # Parameter - Modellierung
        self.mainLayout.addWidget(self.param_isochrones_box, 7, 2, 2, 2)
        self.mainLayout.addWidget(self.param_interpol_box, 7, 2, 1, 2)
        self.mainLayout.addWidget(self.param_rastercalc_box, 7, 2, 1, 2)
        
        # Analyse-Auswahl
        self.mainLayout.addWidget(self.analysis_isochrones_box, 9, 2, 1, 2)
        self.mainLayout.addWidget(self.analysis_interpol_box, 8, 2, 2, 2)
        self.mainLayout.addWidget(self.analysis_rastercalc_box, 8, 2, 2, 2)
        
        #Visualisierung
        self.mainLayout.addWidget(self.viz_isochrones_box, 7, 4, 3, 2)
        self.mainLayout.addWidget(self.viz_interpol_box, 7, 4, 3, 2)
        self.mainLayout.addWidget(self.viz_rastercalc_box, 7, 4, 3, 2)
        self.mainLayout.addWidget(line3, 10, 0, 1, 6)
        
        # Outputpfad
        self.mainLayout.addLayout(self.output_layout, 11, 0, 1, 6)
        self.mainLayout.addWidget(line4, 12, 0, 1, 6)
        
        # run Button
        self.mainLayout.addWidget(self.run_button, 13, 4, 1, 2)

        # Listen zum Ausblenden
        self.isochrones_list = [self.input_isochrones_list,
                              self.data_isochrones_list,
                              self.param_isochrones_list,
                              self.param_isochrones_driving_list,
                              self.param_isochrones_walking_list,
                              self.analysis_isochrones_box,
                              self.viz_isochrones_list]
        self.interpol_list = [self.input_interpol_list,
                              self.data_interpol_list,
                              self.param_interpol_list,
                              self.analysis_interpol_box,
                              self.viz_interpol_list]
        self.rastercalc_list = [self.input_rastercalc_list]

        self.set_enabled((self.input_isochrones_value, self.data_isochrones_box, self.analysis_isochrones_box, self.param_isochrones_box, self.viz_isochrones_box, self.output_label), False)
        self.set_visible((self.analysis_isochrones_box, self.param_interpol_box, self.param_rastercalc_box, self.viz_interpol_box, self.data_interpol_box,       
                    self.data_rastercalc_box), False)

        # Fenster
        window.setLayout(self.mainLayout)
        window.setGeometry(400, 100, 1080, 850)
        window.setWindowTitle("BEMUDA")

        window.show()
        app.exec_()
    

    def tool_handling(self):
        """
        Handling der aktivierten Felder auf Basis des ausgewählten Tools
        """
        
        
        if str(self.tool_task.currentText()) == "isochrones":
            
            self.set_visible([self.input_interpol_list,
                              self.data_interpol_box,
                              self.data_interpol_table_uncert_definition,
                              self.data_interpol_table_uncert_description,
                              self.param_interpol_box,
                              self.param_interpol_list,
                              self.analysis_interpol_box,
                              self.viz_interpol_list], False)
            
            self.set_visible([self.input_rastercalc_list,
                              self.data_rastercalc_box,
                              self.param_rastercalc_list,
                              self.analysis_rastercalc_box,
                              self.viz_rastercalc_box,
                              self.viz_rastercalc_list], False)
            
            # Isochronen einblenden
            self.set_visible([self.input_isochrones_list,
                              self.data_isochrones_list,
                              self.data_isochrones_box,
                              self.param_isochrones_list,
                              self.param_isochrones_box,
                              self.analysis_isochrones_box,
                              self.viz_isochrones_list], True)
            self.input_isochrones_value.setEnabled(True)
            self.input_isochrones_mode_handling()

            

                    
        if str(self.tool_task.currentText()) == "interpolations":
            
            self.set_visible([self.input_isochrones_list,
                              self.data_isochrones_list,
                              self.data_isochrones_box,
                              self.param_isochrones_list,
                              self.param_isochrones_box,
                              self.analysis_isochrones_box,
                              self.viz_isochrones_list], False)
            
            self.set_visible([self.input_rastercalc_list,
                              self.data_rastercalc_box,
                              self.param_rastercalc_list,
                              self.analysis_rastercalc_box,
                              self.viz_rastercalc_box,
                              self.viz_rastercalc_list], False)            
            
            self.set_visible([self.input_interpol_list,
                              self.data_interpol_box,
                              self.data_interpol_mode,
                              self.param_interpol_list,
                              self.param_interpol_box,
                              self.analysis_interpol_box,
                              self.viz_interpol_box,
                              self.viz_interpol_list], True)
            self.set_enabled([self.param_interpol_list], False)
            if self.input_interpol_pointlayer_value.text() != " folder..." and self.input_interpol_polygonlayer_value.text() != " folder...":
                self.analysis_interpol_handling()
                #self.input_rastercalc_attribute_handling

            
        if str(self.tool_task.currentText()) == "raster calculation":
            
            self.set_visible([self.input_interpol_list,
                              self.data_interpol_box,
                              self.data_interpol_mode,
                              self.param_interpol_list,
                              self.param_interpol_box,
                              self.analysis_interpol_box,
                              self.viz_interpol_box,
                              self.viz_interpol_list], False)
            
            self.set_visible([self.input_isochrones_list,
                              self.data_isochrones_list,
                              self.data_isochrones_box,
                              self.param_isochrones_list,
                              self.param_isochrones_box,
                              self.analysis_isochrones_box,
                              self.viz_isochrones_list], False)
            
            self.set_visible([self.input_rastercalc_list,
                              self.data_rastercalc_box,
                              self.param_rastercalc_list,
                              self.analysis_rastercalc_box,
                              self.viz_rastercalc_box,
                              self.viz_rastercalc_list], True)
            
            if self.input_rastercalc_pointlayer_value.text() != " folder..." and self.input_rastercalc_polygonlayer_value.text() != " folder...":
                self.analysis_rastercalc_handling()
             

    def run_tool(self):
        """
        "Funktion zum aufrufen der übergebenen Funktion"
        und Statusausgabe der GUI-Felder
        """
        if self.tool_task.currentText() == "interpolations":
            print("")
            print("-----------------------------------------------")
            print("current status:")
            print("task: "+str(self.tool_task.currentText()))
            print("file - point layer: "+str(self.input_interpol_pointlayer_value.text()))
            print("file - polygon layer: "+str(self.input_interpol_polygonlayer_value.text()))
            print("attribute: " + str(self.input_interpol_attribute_value.currentText()))
            print("cellsize: " + str(self.input_interpol_cellsize_value.text()))
            print("modeling:")
            print("   uncertainty through interpolation methods: "+str(self.analysis_interpol_verfahren_button.isChecked()))
            print("        Linear: " + str(self.param_interpol_button_linear.isChecked()))
            print("        Nearest: " + str(self.param_interpol_button_nearest.isChecked()))
            print("        Natural: " + str(self.param_interpol_button_natural.isChecked()))
            print("        Cubic: " + str(self.param_interpol_button_cubic.isChecked()))
            print("        Rbf: " + str(self.param_interpol_button_rbf.isChecked()))
            print("        Barnes: " + str(self.param_interpol_button_barnes.isChecked()))
            print("        Cressman: " + str(self.param_interpol_button_cressman.isChecked()))
            print("visualization:")
            print("   uncertainty map: "+str(self.viz_interpol_uncertmap_button.isChecked()))
            print("   shading: "+str(self.viz_interpol_shades_button.isChecked())) 
            print("output folder: "+str(self.output_button.text()))
            print("-----------------------------------------------") 
            self.run_interpolation()
        
        elif self.tool_task.currentText() == "isochrones":
            print("")
            print("-----------------------------------------------")
            print("current status:")
            print("task: "+str(self.tool_task.currentText()))    
            print("file: "+str(self.input_isochrones_value.text()))
            print("input: "+str(self.data_isochrones_mode.currentText()))
            print("modeling:")
            print("   analysis - expanded: "+str(self.analysis_isochrones_erweitert_button.isChecked()))
            print("   analysis - cautious:     "+str(self.analysis_isochrones_vorsichtig_button.isChecked()))
            print("   analysis - marginal value:     "+str(self.analysis_isochrones_randwert_button.isChecked()))
            print("visualization:")
            print("   uncertainty points: "+str(self.viz_isochrones_points_button.isChecked()))
            print("   uncertainty polygons: "+str(self.viz_isochrones_polygone_button.isChecked()))    
            print("   uncertainty network: "+str(self.viz_isochrones_network_button.isChecked()))
            print("   uncertainty map: "+str(self.viz_isochrones_uncertmap_button.isChecked()))   
            print("   shading: "+str(self.viz_isochrones_schummerung_button.isChecked()))
            print("   symbols: "+str(self.viz_isochrones_symbole_button.isChecked()))
            print("   noise annotation: "+str(self.viz_isochrones_noise_button.isChecked()))
            print("-----------------------------------------------")
            self.run_isochrones()
        
        elif self.tool_task.currentText() == "raster calculation":
            print("")
            print("-----------------------------------------------")
            print("current status:")
            self.run_rastercalc()
        
        
        else:
            self.run_dummy()





    def input_interpol_read_points(self):
        """
        Behandlung des Eingabefeldes zum Datei-Import von Punktlayer (Interpolationen).
        """
        self.points_fileName = QFileDialog.getOpenFileName(None, "Open Template", "c:\\", "ESRI Shapefiles (*.shp);;All Files (*.*)")[0]
        if self.points_fileName:
            print(self.points_fileName)
            self.input_interpol_pointlayer_value.setText(" {}".format(self.points_fileName))
        else:
            pass

    def input_interpol_read_polygons(self):
        """
        Behandlung des Eingabefeldes zum Datei-Import von Flächenlayer (Interpolationen).
        """
        self.poly_fileName = QFileDialog.getOpenFileName(None, "Open Template", "c:\\", "ESRI Shapefiles (*.shp);;All Files (*.*)")[0]
        if self.poly_fileName:
            print(self.poly_fileName)
            self.input_interpol_polygonlayer_value.setText(" {}".format(self.poly_fileName))
        else:
            pass


    def input_interpol_handling(self):
        """
        Aktivieren der Einstellungen für Methode Interpolationen, wenn Punkt- und Flächenlayer
        ausgewählt wurden.
        """
        if self.input_interpol_pointlayer_value.text() != " folder..." and self.input_interpol_polygonlayer_value.text() != " folder...":
            self.set_enabled((self.input_interpol_attribute_label, self.data_interpol_box, self.analysis_interpol_box,
                              self.param_interpol_box, self.viz_interpol_box, 
                              self.output_label, self.output_button, self.run_button), True)
            self.set_checked((self.analysis_interpol_verfahren_button, self.viz_interpol_uncertmap_button), True)
            self.analysis_interpol_handling()
            self.set_enabled([self.data_interpol_list], True)
        else:
            pass

    
    def input_interpol_attribute_loading(self):
        """
        Add attributes from Inputfile to QComboBox input_interpol_attribute_value
        """
        #global choose_attribute
        self.input_interpol_attribute_value.clear()
        with fiona.open(self.points_fileName, "r", encoding="UTF-8") as source:
            properties = source.schema["properties"]
            for att in properties:
                dtype = properties[att].split(":")[0]
                if dtype == "int" or dtype == "float":
                    self.input_interpol_attribute_value.addItem(att)


    def input_interpol_attribute_handling(self):
        """
        Handling der "input_interpol_attribute_value" QComboBox.
        Wenn "input_interpol_attribute_value" bereits aktiv ist, aktualisieren der Tabelle.
        Aktivieren der QComboBox zur Definition der Unsicherheiten wenn Box noch nicht aktiv ist. 
        """
        if self.input_interpol_attribute_value.isEnabled():
            if str(self.data_interpol_mode.currentText()) == "define uncertainties":
                text = str(self.input_interpol_attribute_value.currentText())
                self.data_interpol_update_table_define(text)
                self.data_interpol_table_uncert_definition.setVisible(True)
                self.data_interpol_table_uncert_description.setVisible(False)
            if str(self.data_interpol_mode.currentText()) == "describe uncertainties":
                text = str(self.input_interpol_attribute_value.currentText())
                self.data_interpol_update_table_describe(text)
                self.data_interpol_table_uncert_description.setVisible(True)
                self.data_interpol_table_uncert_definition.setVisible(False)
            else:
                pass 
        else:
            self.set_enabled([self.input_interpol_attribute_value], True)

    
    def data_interpol_uncert_handling(self):
        """
        Handling der aktivierten Felder für die Bestimmung der Unsicherheit
        in den Eingangsdaten (Interpolationen)
        """    
        # Interpolationen
        if str(self.data_interpol_mode.currentText()) == "no uncertainties":
            self.data_interpol_table_uncert_definition.setVisible(False)
            self.data_interpol_table_uncert_description.setVisible(False)
        if str(self.data_interpol_mode.currentText()) == "define uncertainties":
            text = str(self.input_interpol_attribute_value.currentText())
            self.data_interpol_create_table_define(text)
            self.data_interpol_table_uncert_definition.setVisible(True)
            self.data_interpol_table_uncert_description.setVisible(False)
        if str(self.data_interpol_mode.currentText()) == "describe uncertainties":
            text = str(self.input_interpol_attribute_value.currentText())
            self.data_interpol_create_table_describe(text)
            self.data_interpol_table_uncert_description.setVisible(True)
            self.data_interpol_table_uncert_definition.setVisible(False)


    def data_interpol_create_table_define(self, att):
        """
        Darstellung des gewählten Attributs des Punktlayers in Tabelle bei Auswahl "define uncertainties"
        """
        self.data_interpol_table_uncert_definition.setRowCount(0)

        # Tabelle
        self.data_interpol_table_uncert_definition = QTableWidget(1, 2)
        self.data_interpol_table_uncert_definition.setHorizontalHeaderLabels(["attribute","uncertainy in %"])
        self.data_interpol_table_uncert_definition.horizontalHeader().setDefaultSectionSize(150)
        self.data_interpol_table_uncert_definition.horizontalHeader().setStretchLastSection(True)
        self.data_interpol_table_uncert_definition.verticalHeader().setVisible(False)
        uncert = QLineEdit("0.0")
        uncert.setAlignment(Qt.AlignCenter)
        #uncert.setToolTip("Lorem ipsum") # Hilfe-Button für Eingabefeld Unsicherheit in %
        attribute = QTableWidgetItem(att)
        attribute.setFlags(Qt.ItemIsEnabled)
        self.data_interpol_table_uncert_definition.setItem(0, 0, attribute)
        self.data_interpol_table_uncert_definition.setCellWidget(0, 1, uncert)
        self.data_interpol_table_uncert_definition.setVisible(True)
        self.data_interpol_layout.addWidget(self.data_interpol_table_uncert_definition)
            
    def data_interpol_update_table_define(self, att):
        """
        Update der Tabelle self.data_interpol_table_uncert_definition
        """
        #self.data_interpol_table_uncert_definition.setRowCount(0)
        #self.data_interpol_table_uncert_definition.setColumnCount(0)
        uncert = QLineEdit("0.0")
        uncert.setAlignment(Qt.AlignCenter)
        #uncert.setToolTip("Lorem ipsum") # Hilfe-Button für Eingabefeld Unsicherheit in % (wie in Funtkion data_interpol_create_table_define()!!)
        attribute = QTableWidgetItem(att)
        attribute.setFlags(Qt.ItemIsEnabled)
        self.data_interpol_table_uncert_definition.setItem(0, 0, attribute)
        self.data_interpol_table_uncert_definition.setCellWidget(0, 1, uncert)

    def data_interpol_create_table_describe(self, att):
        """
        Darstellung des gewählten Attributs des Punktlayers in Tabelle bei Auswahl "Unsicherheiten beschreiben
        """
        
        self.data_interpol_table_uncert_description.setRowCount(0)

        # Tabelle
        self.data_interpol_table_uncert_description = QTableWidget(1, 2)
        self.data_interpol_table_uncert_description.setHorizontalHeaderLabels(["attribute","linguistic approximation"])
        self.data_interpol_table_uncert_description.horizontalHeader().setDefaultSectionSize(150)
        self.data_interpol_table_uncert_description.horizontalHeader().setStretchLastSection(True)
        self.data_interpol_table_uncert_description.verticalHeader().setVisible(False)

        uncert = QComboBox()
        uncert.addItem("describe uncertainty")
        uncert.addItem("mathematical")
        uncert.addItem("exactly")
        uncert.addItem("about")
        uncert.addItem("around")
        uncert.addItem("count")
        #uncert.setToolTip("Lorem ipsum") # Hilfe-Button für Eingabefeld Unsicherheit in %

        attribute = QTableWidgetItem(att)
        attribute.setFlags(Qt.ItemIsEnabled)
        self.data_interpol_table_uncert_description.setItem(0, 0, attribute)
        self.data_interpol_table_uncert_description.setCellWidget(0, 1, uncert)

        self.data_interpol_layout.addWidget(self.data_interpol_table_uncert_description)

    def data_interpol_update_table_describe(self, att):
        """
        Update der Tabelle self.data_interpol_table_uncert_description
        """
        #global data_isochrones_table_uncert_description_interp

        uncert = QComboBox()
        uncert.addItem("describe uncertainty")
        uncert.addItem("mathematical")
        uncert.addItem("exactly")
        uncert.addItem("about")
        uncert.addItem("around")
        uncert.addItem("count")
        #uncert.setToolTip("Lorem ipsum") # Hilfe-Button für Eingabefeld Unsicherheit in % (wie in Funktion create_table_descrieb()!!)
        
        attribute = QTableWidgetItem(att)
        attribute.setFlags(Qt.ItemIsEnabled)
        self.data_interpol_table_uncert_description.setItem(0, 0, attribute)
        self.data_interpol_table_uncert_description.setCellWidget(0, 1, uncert)

    def analysis_interpol_handling(self):
        """
        Aktivieren der Attributauswahl für Methode "Unsicherheiten durch Interpolationsverfahren"
        """
        if self.analysis_interpol_verfahren_button.isChecked():
            self.input_interpol_attribute_loading()
            self.viz_interpol_shades_button.setEnabled(False)
            self.set_visible((self.param_interpol_box, self.data_interpol_box, self.param_interpol_button_linear,
                              self.param_interpol_button_nearest, self.param_interpol_button_cubic, self.param_interpol_button_rbf,
                              self.param_interpol_button_barnes, self.param_interpol_button_cressman), True)
            self.set_enabled((self.input_interpol_attribute_label, self.input_interpol_cellsize_label, self.input_interpol_cellsize_value,
                              self.data_interpol_mode, self.data_interpol_table_uncert_definition,
                              self.data_interpol_table_uncert_description, self.param_interpol_button_linear,
                              self.param_interpol_button_nearest, self.param_interpol_button_cubic,
                              self.param_interpol_button_rbf, self.param_interpol_button_barnes,
                              self.param_interpol_button_cressman, self.param_interpol_button_natural), True)
        
        elif self.analysis_interpol_voronoi_button.isChecked():
            self.viz_interpol_shades_button.setEnabled(False)
            self.set_visible((self.param_interpol_box, self.data_interpol_box, self.param_interpol_button_linear,
                              self.param_interpol_button_nearest, self.param_interpol_button_cubic, self.param_interpol_button_rbf,
                              self.param_interpol_button_barnes, self.param_interpol_button_cressman), True)
            self.set_enabled((self.input_interpol_attribute_label, self.input_interpol_attribute_value,
                              self.input_interpol_cellsize_label, self.input_interpol_cellsize_value,
                              self.data_interpol_mode, self.data_interpol_table_uncert_definition,
                              self.data_interpol_table_uncert_description, self.param_interpol_button_linear,
                              self.param_interpol_button_nearest, self.param_interpol_button_cubic,
                              self.param_interpol_button_rbf, self.param_interpol_button_barnes,
                              self.param_interpol_button_cressman, self.param_interpol_button_natural), False)
        
        else:
            #self.set_enabled((label_attribute, choose_attribute, self.data_interpol_mode, self.data_interpol_table_uncert_definition, self.data_interpol_table_uncert_description), False)
            pass

    def run_interpolation(self):
        """
        Ausführung der Interpolationen
        """
        perfect = True
        # Set StyleSheets back to normal
        self.set_stylesheet((self.input_interpol_cellsize_value, self.viz_interpol_shades_button, self.viz_interpol_uncertmap_button, self.output_button), "")

        input_points = self.input_interpol_pointlayer_value.text()[1:]
        input_area = self.input_interpol_polygonlayer_value.text()[1:]
        output_path = self.output_button.text()
        
        
        # Unsicherheit durch Interpolationsverfahren
        if self.analysis_interpol_verfahren_button.isChecked():
            print("uncertainty through interpolation methods:")
            
            attribute = self.input_interpol_attribute_value.currentText()
            todo = self.data_interpol_mode.currentText()
            
            if self.is_number(self.input_interpol_cellsize_value.text()):
                cellsize = float(self.input_interpol_cellsize_value.text())
            else:
                self.input_interpol_cellsize_value.setStyleSheet("background-color: red;")
                perfect = False
            
            
            # Input
            uncertainty = {}
            if todo == "define uncertainties":
                print(todo)
                if self.is_number(self.data_interpol_table_uncert_definition.cellWidget(0,1).text()):
                    self.data_interpol_table_uncert_definition.cellWidget(0,1).setStyleSheet("background-color: white;")
                    print("{}:  {}%".format(str(attribute), self.data_interpol_table_uncert_definition.cellWidget(0,1).text()))
                    uncertainty = float(self.data_interpol_table_uncert_definition.cellWidget(0,1).text())
                else:
                    self.data_interpol_table_uncert_definition.cellWidget(0,1).setStyleSheet("background-color: red;")
                    perfect = False
                print(uncertainty)
            
            elif todo == "describe uncertainties":
                print(todo)
                print("{}:  {}".format(str(attribute), self.data_interpol_table_uncert_description.cellWidget(0,1).currentText()))
                uncertainty = self.data_interpol_table_uncert_description.cellWidget(0,1).currentText()
            
            else:
                print("no uncertainties")
                uncertainty = None
            
            
            # Output
            if not self.viz_interpol_uncertmap_button.isChecked() and not self.viz_interpol_shades_button.isChecked():
                print("Please select visualization technique!")
                self.set_stylesheet((self.viz_interpol_uncertmap_button, self.viz_interpol_shades_button), "red")
                perfect = False
            if not self.folder_path:
                self.set_stylesheet([self.output_button], "red")
                perfect = False 
        
            # Berechnung
            if perfect == True:
                
                # Visualisierung: Unsicherheitskarte
                if self.viz_interpol_uncertmap_button.isChecked():
                    method_buttons = [self.param_interpol_button_linear, self.param_interpol_button_nearest, self.param_interpol_button_cubic, self.param_interpol_button_rbf, self.param_interpol_button_barnes, self.param_interpol_button_cressman, self.param_interpol_button_natural]
                    interp = Interpolation(input_points, input_area, output_path, attribute, cellsize)
                    interp_methods = []
                    for button in method_buttons:
                        if button.isChecked():
                            if button.text()=="Nearest Neighbor":
                                interp_methods.append("nearest")
                            elif button.text().split()[0]=="Natural":
                                interp_methods.append("natural_neighbor")
                            elif button.text()=="Radial Basis Function":
                                interp_methods.append("rbf")
                            else:
                                interp_methods.append(button.text().lower())
                    if uncertainty is None:
                        interp.calculate_uncertainties(interp_methods)
                    else:
                        interp.calculate_uncertainties_with_inputUncertainties(interp_methods, uncertainty)

        
        # Vergleich mit Voronoi-Polygonen
        if self.analysis_interpol_voronoi_button.isChecked():
            print("Voronoi comparison:")
            
            attribute = self.input_interpol_attribute_value.currentText() # only necessary for initializing Interpolation
            
            # Output
            if not self.viz_interpol_uncertmap_button.isChecked() and not self.viz_interpol_shades_button.isChecked():
                print("Please select visualization technique!")
                self.set_stylesheet((self.viz_interpol_uncertmap_button, self.viz_interpol_shades_button), "red")
                perfect = False
            if not self.folder_path:
                self.set_stylesheet([self.output_button], "red")
                perfect = False
                
            # Berechnung
            if perfect == True:
            
                # Visualisierung: Unsicherheitskarte
                if self.viz_interpol_uncertmap_button.isChecked():
                    interp = Interpolation(input_points, input_area, output_path, attribute)
                    interp.voronoi_comparison()
            


        if perfect == True:
            print("Analysis done!")
            print("----------------------------------------------------------")
        else:
            print("Analysis was not able to succeed.")
            print("----------------------------------------------------------")            

    

    
    def input_rastercalc_read_points(self):
        """
        Behandlung des Eingabefeldes zum Datei-Import von Punktlayer (Rasterrechner).
        """
        #print("input_rastercalc_read_points")
        self.points_fileName = QFileDialog.getOpenFileName(None, "Open Template", "c:\\", "ESRI Shapefiles (*.shp);;All Files (*.*)")[0]
        if self.points_fileName:
            print(self.points_fileName)
            self.input_rastercalc_pointlayer_value.setText(" {}".format(self.points_fileName))
        else:
            pass


    
    def input_rastercalc_read_polygons(self):
        """
        Behandlung des Eingabefeldes zum Datei-Import von Flächenlayer (Rasterrechner).
        """
        #print("input_rastercalc_read_polygons")
        self.poly_fileName = QFileDialog.getOpenFileName(None, "Open Template", "c:\\", "ESRI Shapefiles (*.shp);;All Files (*.*)")[0]
        if self.poly_fileName:
            print(self.poly_fileName)
            self.input_rastercalc_polygonlayer_value.setText(" {}".format(self.poly_fileName))
        else:
            pass
        


        
    
    def input_rastercalc_handling(self):
        """
        Aktivieren der Einstellungen für Methode Rasterrechner, wenn Punkt- und Flächenlayer
        ausgewählt wurden.
        """
        #print("input_rastercalc_handling")
        if self.input_rastercalc_pointlayer_value.text() != " folder..." and self.input_rastercalc_polygonlayer_value.text() != " folder...":
            self.set_enabled((self.data_rastercalc_box, self.analysis_rastercalc_box,
                              self.param_rastercalc_box, self.viz_rastercalc_box,
                              self.output_label, self.output_button,
                              self.run_button), True)
            self.set_checked((self.analysis_rastercalc_rasterrechner_button,
                              self.viz_rastercalc_uncertmap_button), True)
            self.analysis_rastercalc_handling()
        else:
            pass






    def input_rastercalc_attribute_loading(self):
        """
        Add attributes from Inputfile to QComboBox self.input_rastercalc_attribute_value
        """
        #print("input_rastercalc_attribute_loading")
        #self.input_rastercalc_attribute_value.clear()
        with fiona.open(self.points_fileName, "r", encoding="UTF-8") as source:
            points = list(source)
            properties = source.schema["properties"]
            for att in properties:
                values = set()
                for point in points:
                    values.add(str(point["properties"][att]))
                if len(values) <= 10:
                    self.input_rastercalc_attribute_value.addItem(att)



    def input_rastercalc_attribute_handling(self):
        """
        Handling der "self.input_rastercalc_attribute_value" QComboBox.
        Anzeigen des Tabellen-Buttons und Speicherung der Matrix
        """
        #print("input_rastercalc_attribute_handling")
        text = str(self.input_rastercalc_attribute_value.currentText())
        print(text)
        
        with fiona.open(self.points_fileName, "r", encoding="UTF-8") as source:
            points = list(source)
            values = set()
            for point in points:
                values.add(str(point["properties"][text]))
        
        csvfile = "changematrix.csv"

        
        with open(csvfile, "w") as output:
            writer = csv.writer(output, lineterminator='\n')
            writer.writerow(values)
            for i in range(len(values)-1):
                k = []
                for j in range(i+1):
                    k.append(1)
                writer.writerow(k)
        
        if self.analysis_rastercalc_rasterrechner_button.isChecked():
            self.data_rastercalc_matrix.setEnabled(False)
            
        self.data_rastercalc_crosstable()


    def data_rastercalc_crosstable(self):
        """
        Darstellung des gewählten Attributs des Punktlayers als Kreuztabelle beim Rasterrechner der Unsicherheit
        """
        #print("data_rastercalc_crosstable")
        self.data_rastercalc_layout.removeWidget(self.data_rastercalc_matrix)

        
        
        csvInput = []
        with open("changematrix.csv", newline='') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                csvInput.append(row)
            
        values = csvInput[0]

        self.data_rastercalc_matrix = QPushButton(" define uncertainty matrix ")
        self.data_rastercalc_matrix.clicked.connect(lambda: self.matrix_window(values))
        self.data_rastercalc_layout.addWidget(self.data_rastercalc_matrix)
        
        if self.analysis_rastercalc_rasterrechner_button.isChecked():
            self.data_rastercalc_matrix.setEnabled(False)
        
    def analysis_rastercalc_handling(self):
        """
        Aktivieren der Parameter für Rasterrechner der Unsicherheit
        """
        #print("analysis_rastercalc_handling")
        if self.analysis_rastercalc_rasterrechner_button.isChecked():
            self.input_rastercalc_attribute_loading()
            self.viz_rastercalc_shades_button.setEnabled(False)
            self.set_visible((self.param_rastercalc_box,
                              self.data_rastercalc_box,
                              self.param_rastercalc_cellsize_label,
                              self.param_rastercalc_cellsize_value,
                              self.param_rastercalc_neighbors_label,
                              self.param_rastercalc_neighbors_value,
                              self.param_rastercalc_distance_label,
                              self.param_rastercalc_distance_value), True)

            self.set_enabled((self.input_rastercalc_attribute_label,
                              self.input_rastercalc_attribute_value,
                              self.param_rastercalc_cellsize_label,
                              self.param_rastercalc_cellsize_value,
                              self.param_rastercalc_neighbors_label,
                              self.param_rastercalc_neighbors_value,
                              self.param_rastercalc_distance_label,
                              self.param_rastercalc_distance_value), True)
            self.data_rastercalc_matrix.setEnabled(False)
        
        elif self.analysis_rastercalc_uebergang_button.isChecked():
            self.viz_rastercalc_shades_button.setEnabled(False)
            self.set_enabled((self.param_rastercalc_neighbors_label,
                              self.param_rastercalc_neighbors_value,
                              self.param_rastercalc_distance_label,
                              self.param_rastercalc_distance_value), False)
            self.data_rastercalc_matrix.setEnabled(True)
        else:
            pass


    def run_rastercalc(self):
        """
        Ausführung des Rasterrechners
        """
        
        perfect = True
        # Set StyleSheets back to normal
        self.set_stylesheet((self.viz_rastercalc_shades_button, self.viz_rastercalc_uncertmap_button, self.output_button), "")

        
        input_points = self.input_rastercalc_pointlayer_value.text()[1:]
        input_area = self.input_rastercalc_polygonlayer_value.text()[1:]
        output_path = self.output_button.text()
        
        self.attribute = self.input_rastercalc_attribute_value.currentText()
        
        if self.analysis_rastercalc_rasterrechner_button.isChecked():
            
            if not self.viz_rastercalc_uncertmap_button.isChecked() and not self.viz_rastercalc_shades_button.isChecked():
                print("Please select visualization technique!")
                self.set_stylesheet((self.viz_rastercalc_uncertmap_button, self.viz_rastercalc_shades_button), "red")
                perfect = False
            if not self.folder_path:
                self.set_stylesheet([self.output_button], "red")
                perfect = False
            else:
                print("raster calculation of uncertainty:")
                print("initialising attribute: " +str(self.attribute))
                rasterrechner = UncertRasterCalculator(input_points,
                                                       input_area,
                                                       output_path,
                                                       self.attribute)
                cellsizeValue = self.param_rastercalc_cellsize_value.text()
                print("cellsize: "+str(cellsizeValue))
                neighborsValue = self.param_rastercalc_neighbors_value.text()
                print("neighbors: "+str(neighborsValue))
                maxDistanceValue = self.param_rastercalc_distance_value.text()
                print("maxDistance: "+str(maxDistanceValue))

                rasterrechner.calculate_uncertaintyRaster(cellsizeValue, neighborsValue, maxDistanceValue)
        
        
        if self.analysis_rastercalc_uebergang_button.isChecked():
            
            if not self.viz_rastercalc_uncertmap_button.isChecked() and not self.viz_rastercalc_shades_button.isChecked():
                print("Please select visualization technique!")
                self.set_stylesheet((self.viz_rastercalc_uncertmap_button, self.viz_rastercalc_shades_button), "red")
                perfect = False
            if not self.folder_path:
                self.set_stylesheet([self.output_button], "red")
                perfect = False
            else:
                print("variation of transition zones:")            
                rasterrechner = UncertRasterCalculator(input_points,
                                                       input_area,
                                                       output_path,
                                                       self.attribute)
                
                cellsizeValue = self.param_rastercalc_cellsize_value.text()
                print("cellsize: "+str(cellsizeValue))
                
                csvInput = []
                with open('changematrix.csv', newline='') as csvfile:
                    reader = csv.reader(csvfile)
                    for row in reader:
                        csvInput.append(row)
                
                attributeValues = csvInput[0]
                matrix = csvInput[1:]
                
                changematrix = dict()
                for element in attributeValues:
                    changematrix[str(element)] = {}
                
                for i in range(len(attributeValues)):
                    for j in range(len(attributeValues)):
                        if i>j:
                            changematrix[str(attributeValues[i])][str(attributeValues[j])] = matrix[i-1][j]
                            changematrix[str(attributeValues[j])][str(attributeValues[i])] = matrix[i-1][j]
                print(changematrix)
        
                rasterrechner.calculate_transitionRaster(cellsizeValue, changematrix)
        
        
        if perfect == True:
            print("Analysis done!")
            print("----------------------------------------------------------")
        else:
            print("Analysis was not able to succeed.")
            print("----------------------------------------------------------")            



    def input_isochrones_handling(self):
        """
        Behandlung des Eingabefeldes zum Datei-Import
        """
        
        #global graph_fileName
        graph_fileName = QFileDialog.getOpenFileName(None, "Open Template", "c:\\", "GraphML Files (*.graphml);;All Files (*.*)")[0]
        if graph_fileName:
            print(graph_fileName)
            self.input_isochrones_value.setText(" {}".format(graph_fileName))
            self.set_enabled((self.data_isochrones_box, self.analysis_isochrones_box, self.param_isochrones_box, self.viz_isochrones_box, self.output_label, self.output_button, self.run_button), True)
            
            #global G
            self.G = ox.io.load_graphml(graph_fileName)
            #global attributes
            self.attributes = []
            for u, v, k, data in self.G.edges(data=True, keys=True):
                for attribute, value in data.items():
                    if attribute not in self.attributes and (type(value) in (int, float, uc.core.Variable)) and (attribute != "osmid"):
                        self.attributes.append(attribute)
            self.attr = len(self.attributes)
            
            #global data_isochrones_table_uncert_definition
            #global data_isochrones_table_uncert_description
            
            self.data_isochrones_table_uncert_definition.setRowCount(0)
            self.data_isochrones_table_uncert_description.setRowCount(0)
            
            # Tabelle
            self.data_isochrones_table_uncert_definition = QTableWidget(self.attr, 2)
            self.data_isochrones_table_uncert_definition.setHorizontalHeaderLabels(["attribute","uncertainty in %"])
            self.data_isochrones_table_uncert_definition.horizontalHeader().setDefaultSectionSize(150)
            self.data_isochrones_table_uncert_definition.horizontalHeader().setStretchLastSection(True)
            self.data_isochrones_table_uncert_definition.verticalHeader().setVisible(False)
            self.data_isochrones_table_uncert_definition.setVisible(False)

            #print("{}  a".format(attr))
            for i in range(0, self.attr):
                uncert = QLineEdit("0.0")
                uncert.setAlignment(Qt.AlignCenter)
                #uncert.setToolTip("Lorem ipsum") # Hilfe-Button für Angabe der Unsicherheit in %
                attribute = QTableWidgetItem(str(self.attributes[i]))
                attribute.setFlags(Qt.ItemIsEnabled)
                self.data_isochrones_table_uncert_definition.setItem(i,0, attribute)
                self.data_isochrones_table_uncert_definition.setCellWidget(i, 1, uncert)

            self.data_isochrones_layout.addWidget(self.data_isochrones_table_uncert_definition)

            self.data_isochrones_table_uncert_description = QTableWidget(self.attr, 2)
            self.data_isochrones_table_uncert_description.setHorizontalHeaderLabels(["attribute","linguistic approximation"])
            self.data_isochrones_table_uncert_description.horizontalHeader().setDefaultSectionSize(150)
            self.data_isochrones_table_uncert_description.horizontalHeader().setStretchLastSection(True)
            self.data_isochrones_table_uncert_description.verticalHeader().setVisible(False)

            #print("{}  b".format(attr))
            for i in range(0, self.attr):
                uncert = QComboBox()
                uncert.addItem("describe uncertainty")
                uncert.addItem("mathematical")
                uncert.addItem("exactly")
                uncert.addItem("about")
                uncert.addItem("around")
                uncert.addItem("count")
                #uncert.addItem("almost")
                #uncert.setToolTip("Lorem ipsum") # Hilfe-Button für Angabe der Unsicherheit in %

                attribute = QTableWidgetItem(str(self.attributes[i]))
                attribute.setFlags(Qt.ItemIsEnabled)
                self.data_isochrones_table_uncert_description.setItem(i,0, attribute)
                self.data_isochrones_table_uncert_description.setCellWidget(i, 1, uncert)

            self.data_isochrones_table_uncert_description.setVisible(False)
            self.data_isochrones_layout.addWidget(self.data_isochrones_table_uncert_description)
            

            



    def input_isochrones_mode_handling(self):
        """
        Handling der aktivierten Felder auf Basis des ausgewählten Modus zur Fortbewegung (walking/driving)
        """
        if str(self.input_isochrones_box_param_mode_value.currentText()) == "driving":
            self.set_visible(self.param_isochrones_driving_list, True)
            self.set_visible(self.param_isochrones_walking_list, False)
        
        elif str(self.input_isochrones_box_param_mode_value.currentText()) == "walking":
            self.set_visible(self.param_isochrones_driving_list, False)
            self.set_visible(self.param_isochrones_walking_list, True)


    def data_isochrones_uncert_handling(self):
        """
        Handling der aktivierten Felder für die Bestimmung der Unsicherheit
        in den Eingangsdaten (Isochronen)
        """
        # Isochronen
        if str(self.data_isochrones_mode.currentText()) == "no uncertainties":
            self.data_isochrones_table_uncert_definition.setVisible(False)
            self.data_isochrones_table_uncert_description.setVisible(False)
        if str(self.data_isochrones_mode.currentText()) == "define uncertainties":
            self.data_isochrones_table_uncert_definition.setVisible(True)
            self.data_isochrones_table_uncert_description.setVisible(False)
        if str(self.data_isochrones_mode.currentText()) == "describe uncertainties":
            self.data_isochrones_table_uncert_description.setVisible(True)
            self.data_isochrones_table_uncert_definition.setVisible(False)
    
    
    


    def run_isochrones(self):
        """
        Ausführung der Isochronenberechnung mit Unsicherheiten
        """
        
        print("isochrones")
        perfect = True
        mode = self.data_isochrones_mode.currentText()
        
        # Standard-Eingaben
        print(self.input_isochrones_value.text())
        print("{} in {} minutes".format(self.input_isochrones_box_param_mode_value.currentText(), self.input_isochrones_box_param_range_value.text()))
        
        coords = [x.strip() for x in self.input_isochrones_box_param_coords_value.text().split(',')]
        if len(coords) == 2:
            if (self.is_number(coords[0]) and (-90 <= float(coords[0]) <= 90) and self.is_number(coords[1]) and (-180 <= float(coords[1]) <= 180)):
                self.input_isochrones_box_param_coords_value.setStyleSheet("background-color: white;")
                print("Starting Point: (lat: {}, lon: {})".format(coords[0], coords[1]))
            else:    
                self.input_isochrones_box_param_coords_value.setStyleSheet("background-color: red;")
                perfect = False    
        else:
            self.input_isochrones_box_param_coords_value.setStyleSheet("background-color: red;")
            perfect = False
        
        # Input
        uncertainties = {}
        print(self.attr)
        if mode == "define uncertainties":
            print(mode)
            for i in range(0, self.attr):
                if self.is_number(self.data_isochrones_table_uncert_definition.cellWidget(i,1).text()):
                    self.data_isochrones_table_uncert_definition.cellWidget(i,1).setStyleSheet("background-color: white;")
                    print("{}:  {}%".format(str(self.attributes[i]), self.data_isochrones_table_uncert_definition.cellWidget(i,1).text()))
                    uncertainties[self.attributes[i]] = float(self.data_isochrones_table_uncert_definition.cellWidget(i,1).text())
                else:
                    self.data_isochrones_table_uncert_definition.cellWidget(i,1).setStyleSheet("background-color: red;")
                    perfect = False
            print(uncertainties)
        
        elif mode == "describe uncertainties":
            print(mode)
            for i in range(0, self.attr):
                print("{}:  {}".format(str(self.attributes[i]), self.data_isochrones_table_uncert_description.cellWidget(i,1).currentText()))
                uncertainties[self.attributes[i]] = self.data_isochrones_table_uncert_description.cellWidget(i,1).currentText()
        
        else:
            print("no uncertainties")
            for i in range(0, self.attr):
                print(i)
                #print("{}:  {}".format(str(attributes[i]), self.data_isochrones_table_uncert_description.cellWidget(i,1).currentText()))
                uncertainties[self.attributes[i]] = 0.0
        
        
        # Modellierung
        if self.is_number(self.param_isochrones_speeduncert_value.text()):
            self.param_isochrones_speeduncert_value.setStyleSheet("background-color: white;")
            print("speed-uncert: {}".format(self.param_isochrones_speeduncert_value.text()))
        else: 
            self.param_isochrones_speeduncert_value.setStyleSheet("background-color: red;")
            perfect = False
        
        if self.input_isochrones_box_param_mode_value.currentText() == "driving":
            print("no limit: {} +/-{}".format(self.param_isochrones_driving_novalue_value.text(), self.param_isochrones_driving_novalue_value_uncert.text()))
            print("no data: {} +/-{}".format(self.param_isochrones_driving_nodata_value.text(), self.param_isochrones_driving_nodata_value_uncert.text()))
        
        #Ziel
        if self.analysis_isochrones_erweitert_button.isChecked():
            print("MinMax mit {}".format(mode))
        
        if self.analysis_isochrones_vorsichtig_button.isChecked():
            print("CT mit {}".format(mode))
        
        if not self.folder_path:
            self.output_button.setStyleSheet("background-color: red;")
            perfect = False
        
        if perfect == False:
            return
        
        # Visualisierung -> Methodenaufruf
        
        # Methodenaufruf
        print(str(datetime.datetime.now()) + "   Starting Isochrone Calculations.....")
        starting_point = (float(coords[0]), float(coords[1]))
        
        d = 2
        
        for u, v, k, data in self.G.edges(data=True, keys=True):
            for key, value in uncertainties.items():
                if self.is_number(value):
                    data[key] = ufloat(data[key], data[key]*(value / 100), str(key))
                elif value == "mathematical":
                    data[key] = ufloat(data[key], 0.0, str(key))
                elif value == "exactly":
                    data[key] = ufloat(data[key], (10**(-(d+1))), str(key))
                elif value == "about":
                    data[key] = ufloat(data[key], 2*(10**(-d)), str(key))
                elif value == "around":
                    data[key] = ufloat(data[key], 10*(10**(-d)), str(key))
                elif value == "count":
                    data[key] = ufloat(data[key], math.sqrt(data[key]), str(key))
        
        isochrone = Isochrones.fromGraph(self.G, starting_point)    
        #iso = Isochrones.fromGraphUTM(self.G, starting_point)
        
        if self.input_isochrones_box_param_mode_value.currentText() == "driving":
            speed_uncert = float(self.param_isochrones_speeduncert_value.text())
            isochrone.weightingDefault(speed_uncert/100)
            nolimit = ufloat(float(self.param_isochrones_driving_novalue_value.text()), float(self.param_isochrones_driving_novalue_value_uncert.text()) , "speed")
            nodata = ufloat(float(self.param_isochrones_driving_nodata_value.text()), float(self.param_isochrones_driving_nodata_value_uncert.text()) , "no data")
            
            if self.analysis_isochrones_erweitert_button.isChecked():
                isochrone.weightingExpand_drive(speed_uncert, nolimit, nodata)
                if self.viz_isochrones_points_button.isChecked():
                    isochrone.isochrone_points(float(self.input_isochrones_box_param_range_value.text()), str(self.folder_path)+"/erweitert_pts")
                if self.viz_isochrones_polygone_button.isChecked():
                    isochrone.isochrone_poly(float(self.input_isochrones_box_param_range_value.text()), str(self.folder_path)+"/erweitert_poly")
                if self.viz_isochrones_network_button.isChecked():
                    isochrone.isochrone_network(float(self.input_isochrones_box_param_range_value.text()), str(self.folder_path)+"/erweitert_net")
                if self.viz_isochrones_uncertmap_button.isChecked():
                    isochrone.isochrone_umap(str(self.folder_path)+"/extended_umap")
            
            if self.analysis_isochrones_vorsichtig_button.isChecked():
                isochrone.weightingCautious_drive(speed_uncert, nolimit, nodata)
                if self.viz_isochrones_points_button.isChecked():
                    isochrone.isochrone_points(float(self.input_isochrones_box_param_range_value.text()), str(self.folder_path)+"/vorsichtig_pts")
                if self.viz_isochrones_polygone_button.isChecked():
                    isochrone.isochrone_poly(float(self.input_isochrones_box_param_range_value.text()), str(self.folder_path)+"/vorsichtig_poly")
                if self.viz_isochrones_network_button.isChecked():
                    isochrone.isochrone_network(float(self.input_isochrones_box_param_range_value.text()), str(self.folder_path)+"/vorsichtig_net")
                if self.viz_isochrones_uncertmap_button.isChecked():
                    isochrone.isochrone_umap(str(self.folder_path)+"/cautious_umap")
            
            if not (self.analysis_isochrones_erweitert_button.isChecked() or self.analysis_isochrones_vorsichtig_button.isChecked()):
                if self.viz_isochrones_points_button.isChecked():
                    isochrone.isochrone_points(float(self.input_isochrones_box_param_range_value.text()), str(self.folder_path)+"/default_pts")
                if self.viz_isochrones_polygone_button.isChecked():
                    isochrone.isochrone_poly(float(self.input_isochrones_box_param_range_value.text()), str(self.folder_path)+"/default_poly")
                if self.viz_isochrones_network_button.isChecked():
                    isochrone.isochrone_network(float(self.input_isochrones_box_param_range_value.text()), str(self.folder_path)+"/default_net")
                if self.viz_isochrones_uncertmap_button.isChecked():
                    isochrone.isochrone_umap(str(self.folder_path)+"/default_umap")
                
        
        if self.input_isochrones_box_param_mode_value.currentText() == "walking":
            
            walking = ufloat(float(self.param_isochrones_walking_speed_value.text()), float(self.param_isochrones_walking_speed_value.text())*(float(self.param_isochrones_speeduncert_value.text())/100), "speed")
            
            if self.analysis_isochrones_erweitert_button.isChecked():
                isochrone.weightingExpand_walk(walking)
                if self.viz_isochrones_points_button.isChecked():
                    isochrone.isochrone_points(float(self.input_isochrones_box_param_range_value.text()), str(self.folder_path)+"/erweitert_pts")
                if self.viz_isochrones_polygone_button.isChecked():
                    isochrone.isochrone_poly(float(self.input_isochrones_box_param_range_value.text()), str(self.folder_path)+"/erweitert_poly")
                if self.viz_isochrones_network_button.isChecked():
                    isochrone.isochrone_network(float(self.input_isochrones_box_param_range_value.text()), str(self.folder_path)+"/erweitert_net")
                if self.viz_isochrones_uncertmap_button.isChecked():
                    isochrone.isochrone_umap(str(self.folder_path)+"/extended_umap")
            
            if self.analysis_isochrones_vorsichtig_button.isChecked():
                isochrone.weightingCautious_walk(walking)
                if self.viz_isochrones_points_button.isChecked():
                    isochrone.isochrone_points(float(self.input_isochrones_box_param_range_value.text()), str(self.folder_path)+"/vorsichtig_pts")
                if self.viz_isochrones_polygone_button.isChecked():
                    isochrone.isochrone_poly(float(self.input_isochrones_box_param_range_value.text()), str(self.folder_path)+"/vorsichtig_poly")
                if self.viz_isochrones_network_button.isChecked():
                    isochrone.isochrone_network(float(self.input_isochrones_box_param_range_value.text()), str(self.folder_path)+"/vorsichtig_net")
                if self.viz_isochrones_uncertmap_button.isChecked():
                    isochrone.isochrone_umap(str(self.folder_path)+"/cautious_umap")
        
            if not (self.analysis_isochrones_erweitert_button.isChecked() or self.analysis_isochrones_vorsichtig_button.isChecked()):
                if self.viz_isochrones_points_button.isChecked():
                    isochrone.isochrone_points(float(self.input_isochrones_box_param_range_value.text()), str(self.folder_path)+"/default_pts")
                if self.viz_isochrones_polygone_button.isChecked():
                    isochrone.isochrone_poly(float(self.input_isochrones_box_param_range_value.text()), str(self.folder_path)+"/default_poly")
                if self.viz_isochrones_network_button.isChecked():
                    isochrone.isochrone_network(float(self.input_isochrones_box_param_range_value.text()), str(self.folder_path)+"/default_net")
                if self.viz_isochrones_uncertmap_button.isChecked():
                    isochrone.isochrone_umap(str(self.folder_path)+"/default_umap")
       
       
    def run_dummy(self):
        """
        DUMMY
        """
        print("Die anderen Analysen")
        
    
    def output_button_handling(self):
        """
        Behandlung der Eingabe des Output-Ordners
        """
        
        self.folder_path = QFileDialog.getExistingDirectory(None, "Select Folder")
        if self.folder_path:
            print(self.folder_path)
            self.output_button.setText(self.folder_path)
            self.output_button.setStyleSheet("background-color: white;")

    # Hilfsfunktionen
    def is_number(self,string):
        try:
            float(string)
            return True
        except ValueError:
            return False        


    def set_visible(self, liste, bool):
        #print("set Visible: {}".format(liste))
        for element in liste:
            if type(element) == list:
                self.set_visible(element, bool)
            else:
                element.setVisible(bool)


    def set_enabled(self, liste, bool):
        #print("set Enabled: {}".format(liste))
        for element in liste:
            if type(element) == list:
                self.set_enabled(element, bool)
            else:
                element.setEnabled(bool)


    def set_checked(self, liste, bool):
        #print("set Checked: {}".format(liste))
        for element in liste:
            if type(element) == list:
                set_checked(element, bool)
            else:
                element.setChecked(bool)

    def set_stylesheet(self, list, color):
        """
        @param list: list of elements
        @param color: color
        """
        if color == "":
            # set back to normal
            for element in list:
                element.setStyleSheet("")
        else:
            # set background-color
            for element in list:
                element.setStyleSheet(f"background-color: {color};")


    def create_line(self):
        lineToCreate = QFrame()
        lineToCreate.setFrameShape(QFrame.HLine)
        lineToCreate.setFrameShadow(QFrame.Sunken)
        return lineToCreate


    def create_spinbox(self, maxi, value):
        spinBox = QSpinBox()
        spinBox.setMaximum(maxi)
        spinBox.setValue(value)
        spinBox.setAlignment(Qt.AlignRight)
        spinBox.setVisible(False)
        return spinBox


    def matrix_window(self, values):
        widget = Help(values)
        widget.exec_()




if __name__ == "__main__":
    gui = BEMUDA()
    gui.startGUI()