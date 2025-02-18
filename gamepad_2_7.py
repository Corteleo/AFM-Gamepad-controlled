#Script to interface between a gamepad controller and a DriveAFM using Python and an Arduino board. 
#AFM must be on, Studio must be on and a measuring sesion open, gamepad should be conected and recognized by the PC, and Arduino should be conected to the PC and running the code to measure voltages and write to serial.
#Working on:
#Studio 13.2
#Nanosurf python script package  1.9.4
#sys 1013
#pygame 2.6.1
#PySide6 6.7.3
#matplotlib 3.9.2
#numpy 1.25.1
#pandas 2.0.3
#scipy 1.11.1
#serial 3.5

#%%%%%%%%%%%%%%%%%%
# Start by loading some libraries
#%%%%%%%%%%%%%%%%%%

import sys
import pygame
from PySide6 import  QtWidgets
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QBrush, QPen
from PySide6.QtWidgets import QFormLayout, QApplication, QSlider, QDoubleSpinBox, QWidget, QVBoxLayout, QLabel, QComboBox, QLineEdit,QHBoxLayout, QGroupBox, QPushButton, QGridLayout
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.colors as mcolors
import matplotlib.cm as cm
import numpy as np
import matplotlib.pyplot as plt
from PySide6.QtGui import QPalette, QColor
import nanosurf
import time
import threading
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning) #This is to avoid getting messages about some of the libraries and or functions changing in the future.
warnings.simplefilter(action='ignore', category=UserWarning)
import pandas as pd
import datetime
from pathlib import Path  
from scipy import ndimage
import serial
import re

#%%%%%%%%%%%%%%%%%%
# Initialize conections to different systems.
#%%%%%%%%%%%%%%%%%%

##Arduino
try:    
    ser = serial.Serial('COM19', 2000000, timeout=0.01) #User should change the port number accordingly.
except:
    print("COM not working or wrong COM port selected")

##Gamepad
# Initialize Pygame for gamepad input
pygame.init()
pygame.joystick.init()
# Check if a gamepad is connected
if pygame.joystick.get_count() == 0:
    print("No gamepad detected.")
try:
    # Create a joystick object for the first gamepad
    gamepad = pygame.joystick.Joystick(0)
    gamepad.init()    
except:
    print("Cannot connect to gamepad.")

##Studio
# Initialize connection with Studio and prepares Studio by changing the User outputs and some imaging/spectroscopy parameters.
try:
    studio = nanosurf.Studio()
    studio.connect()
    spm = studio.spm
    
    #Choose Position x y and z as outputs of the BNC connectors    
    spm.core.user_out.property.hi_res_input1.value = spm.core.user_out.property.hi_res_input1.ValueEnum.Position_X
    spm.core.user_out.property.hi_res_input2.value = spm.core.user_out.property.hi_res_input2.ValueEnum.Position_Y
    spm.core.user_out.property.hi_res_input3.value = spm.core.user_out.property.hi_res_input3.ValueEnum.Position_Z
    
    #Then we scale and offset the output so instead of going from -10 to 10V it goes from 0 to 5V (The Arduino only accepts from 0 to 5V).
    #Note that these values are system specific so they could change depending ont he calibration of the system.
    spm.lu.analog_hi_res_out.user1.attribute.calib_gain.value=-0.5
    spm.lu.analog_hi_res_out.user1.attribute.calib_offset.value=0.25    
    spm.lu.analog_hi_res_out.user2.attribute.calib_gain.value=-0.5
    spm.lu.analog_hi_res_out.user2.attribute.calib_offset.value=0.25    
    spm.lu.analog_hi_res_out.user3.attribute.calib_gain.value=-0.5
    spm.lu.analog_hi_res_out.user3.attribute.calib_offset.value=0.25   
    
    #Prepare the spectroscopy routine
    #It is a simple routine that retracts the tip some distance (so it doesn't matter if the system is initially retracted or engaged). Then performs an advance to setpoint, and last another retract to capture advance and retract force vs distance.
    #First removes any existing spectroscopy routine by deleting the segments.
    while spm.workflow.spectroscopy_setup.segment_count()>0:
        spm.workflow.spectroscopy_setup.remove_segment(0)
    time.sleep(1)#It can be faster than this, but I found that python sometimes tries to edit a segment before Studio finished adding it, and this can crash Studio.
    studio.spm.workflow.spectroscopy_setup.add_new_segment()
    time.sleep(1)
    studio.spm.workflow.spectroscopy_setup.transform_segment(0,"ramp_with_fixed_length_retract")
    time.sleep(1)
    studio.spm.workflow.spectroscopy_setup.add_new_segment()
    time.sleep(1)
    studio.spm.workflow.spectroscopy_setup.transform_segment(1,"ramp_with_setpoint_advance")
    time.sleep(1)
    studio.spm.workflow.spectroscopy_setup.segment_configuration(1,r'{"id":"ramp_with_setpoint_advance","property":{"setpoint":{"value":100e-03, "unit":"V"}}}')
    time.sleep(1)
    studio.spm.workflow.spectroscopy_setup.add_new_segment()
    time.sleep(1)
    studio.spm.workflow.spectroscopy_setup.transform_segment(2,"ramp_with_fixed_length_retract")    
except:
    print("Cannot connect with Studio session")

#%%%%%%%%%%%%%%%%%%
# Define functions that will be executed when pressing buttons on the gamepad
#%%%%%%%%%%%%%%%%%%

#Note: Functions can be pre-selected here: # Set up control mappings    and should be in the function_dic at the bottom of this section 


# Define functions to be executed when gamepad buttons are pressed
def H_curve():
    print("Executing the H curve")  
    t2 = threading.Thread(target=move_H_curve)
    t2.start()

def decrease_setpoint():
    print("decrease_setpoint")
    try:
        currentsetpoint=spm.core.z_controller.property.setpoint.value
        spm.core.z_controller.property.setpoint.value=currentsetpoint-0.1*currentsetpoint
    except:
        print("Setpoint not decreased")

def increase_setpoint():
    print("increase_setpoint")
    try:
        currentsetpoint=spm.core.z_controller.property.setpoint.value
        spm.core.z_controller.property.setpoint.value=currentsetpoint+0.1*currentsetpoint
    except:
        print("Setpoint not indecreased")

def Aproach():
    spm.workflow.approach.start_approach()
    print("Aproaching")

def interact():
    print("Interacting")

    
    spm.workflow.spectroscopy.start_cycle()


def Withdraw():
    spm.workflow.approach.start_withdraw()
    print("Withdrawing")

def startstop():
    is_scanning=spm.workflow.imaging.is_scanning() #True or false value indicating if system is currently scanning.
    if is_scanning==False:
        spm.workflow.imaging.property.auto_generator.value=False #Disable auto scan generator
        spm.workflow.imaging.property.generator.value=spm.workflow.imaging.property.generator.value.Spiral_Scan #Change the scan type to spiral
        spm.workflow.imaging.property.line_rate.value=1.5 #Set line rate in Hz
        spm.workflow.imaging.property.points_per_line.value=128 #Set number of pixels
        spm.workflow.imaging.property.scan_range_fast_axis.value=30e-6 #Set scan range along fast scan axis
        spm.workflow.imaging.property.scan_range_slow_axis.value=30e-6 #Set scan range along slow scan axis
        spm.workflow.imaging.start_imaging() #Start imaging
        print("Scanning")
    else:
        spm.workflow.imaging.stop_imaging() #Stop imaging
        print("Stop Scanning")

def select():
    print("Selecting item")  
    
function_dic={'H_curve':H_curve,'decrease_setpoint':decrease_setpoint,'increase_setpoint':increase_setpoint,'Aproach':Aproach,'interact':interact,'Withdraw':Withdraw,'startstop':startstop,'select':select}
def move_H_curve():       


    vx=4e-6
    vy=0





    hilbert_seq = "a"

    for _ in range(7):
        new_seq = ""
        for char in hilbert_seq:
            if char == "a":
                new_seq += "-bF+aFa+Fb-"
            elif char == "b":
                new_seq += "+aF-bFb-Fa+"
            else:
                new_seq += char
        hilbert_seq = new_seq


    for char in hilbert_seq:
        x=spm.lu.position_control.instance.attribute.current_pos_x.value
        time.sleep(0.2)
        y=spm.lu.position_control.instance.attribute.current_pos_y.value
        time.sleep(0.2)
        newvx=vx
        newvy=vy
        if char == "F":
            #spm.workflow.imaging.property.image_offset_x.value=(x+vx)
            time.sleep(0.2)
            spm.lu.position_control.instance.attribute.target_move_pos_x.value=(x+vx)
            time.sleep(0.2)
            spm.lu.position_control.instance.attribute.target_move_pos_y.value=(y+vy)
            time.sleep(0.2)
            spm.lu.position_control.instance.trigger.move_to_target_fix_speed_xy()
            time.sleep(0.2)
            #spm.workflow.imaging.property.image_offset_y.value=(y+vy)        
        elif char == "+":
            newvx=vy
            newvy=-vx
        elif char == "-":        
            newvx=-vy
            newvy=vx
        
        vx=newvx
        vy=newvy
        #time.sleep(2)
    
    
#%%%%%%%%%%%%%%%%%%
# Thread to capture data from the AFM, this has several sleep because a code executed later on has to create the newfile before read_AFM can start storing data.
#%%%%%%%%%%%%%%%%%%

# Thread for reading AFM data
def read_AFM():
    global Z,idj,idk, buferlenght, ser
    k = 0
    time.sleep(1)

    # Initialize DataFrame once
    data0 = {
        "X": [],
        "Y": [],
        "Z": [],
        "timestamp": []
    }
    df1 = pd.DataFrame(data0)

    while True:
        try:
            # Read and decode serial data
            data = ser.readline().decode().strip()
            
            if data:
                result = [x.strip() for x in data.split(',')]
                
                # Ensure correct data length
                if len(result) != 3:
                    print(f"Warning: Unexpected data format: {data}")
                    continue
                
                # Convert to float and store
                x_val = float(result[0])
                y_val = float(result[1])
                z_val = float(result[2])
                #╗print(z_val)

                data2 = {
                    "X": [x_val],
                    "Y": [y_val],
                    "Z": [z_val],
                    "timestamp": [datetime.datetime.now()]
                }

                df2 = pd.DataFrame(data2)
                df1 = pd.concat([df1, df2], ignore_index=True)  # Efficient appending
                
                k += 1

        except (ValueError, IndexError) as e:
            print(f"Error parsing data: {data} -> {e}")
        
        # Process data when buffer limit is reached
        if k > buferlenght:
            k = 0
            xdata = df1["X"].tolist()
            ydata = df1["Y"].tolist()
            zdata = df1["Z"].tolist()
            

            for i in range(len(xdata)):
                pos_x = xdata[i]
                pos_y = ydata[i]
                pos_z = zdata[i]

                idj = (np.abs(X[0, :] - pos_x)).argmin()
                idk = (np.abs(Y[:, 0] - pos_y)).argmin()

                Z[idj, idk] =1024-pos_z
            
            df1.to_csv(filepath, mode='a', index=False, header=False)
            # Reset DataFrame after processing
            df1 = pd.DataFrame(data0)
            

t1 = threading.Thread(target=read_AFM)
t1.start()                   

#%%%%%%%%%%%%%%%%%%
# GUI and main thread
#%%%%%%%%%%%%%%%%%%

# Main window class
class GamepadMonitor(QWidget):
    def __init__(self):
        super().__init__()
        
        self.newimagefile() #This needs to be run first to 


        # Set up the window
        self.setWindowTitle("AFM - Gamepad Interface")
        self.setGeometry(100, 100, 800, 1200)
        self.setAutoFillBackground(True)

        palette = self.palette()
        #palette.setColor(QPalette.Window, QColor('Black'))
        #palette.setColor(QPalette.Window, QColor('Gray'))
        self.setPalette(palette)
        # Layout for the widget
        #self.layout = QVBoxLayout()
        self.layout = QGridLayout()
        # Add button and axis state labels
        #self.empty_space1 = QLabel("")
        #self.empty_space2 = QLabel("")
        #self.layout.addWidget(self.empty_space1)
        #self.layout.addWidget(self.empty_space2,0,0)


        # Add button and axis state labels
        #self.empty_space1 = QLabel("")
        #self.layout.addWidget(self.empty_space1)
        #self.empty_space2 = QLabel("")
        #self.layout.addWidget(self.empty_space2)
        #self.button_state_label = QLabel("Button States: None")
        #self.axis_state_label = QLabel("Axis States: None")
        

        
        




        # Set up control mappings
        control_layout = QVBoxLayout()
        self.create_control_menu(control_layout, 'A', 'decrease_setpoint')
        self.create_control_menu(control_layout, 'B', 'increase_setpoint')
        self.create_control_menu(control_layout, 'X', 'Aproach')
        self.create_control_menu(control_layout, 'Y', 'startstop')
        self.create_control_menu(control_layout, 'LB', 'Map')
        self.create_control_menu(control_layout, 'RB', 'Withdraw')
        self.create_control_menu(control_layout, 'Start','interact')
        self.create_control_menu(control_layout, 'Select', 'Select')

        control_group = QGroupBox('Control Mappings')
        control_group.setLayout(control_layout)
        #self.layout.addWidget(control_group,0,1)
        self.layout.addWidget(control_group,0,0)


        
        # Add a 2D plot
        #figure_layout = QHBoxLayout()
        self.figure = Figure(facecolor='white')
        self.canvas = FigureCanvas(self.figure)
        
        ##self.ax = self.figure.add_subplot(111, projection='3d')
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor('white')         # Axes background
        self.ax.tick_params(colors='black')  # Tick labels
        self.ax.xaxis.label.set_color('black')  # X-axis label
        self.ax.yaxis.label.set_color('black')  # Y-axis label

        for spine in self.ax.spines.values():   # Axes spines
            spine.set_edgecolor('black')

        #self.ax.set_xlim([-1, 1])
        #self.ax.set_ylim([-1, 1])
        #self.ax.set_zlim([-1, 1])
        self.ax.set_xlabel("X Axis")
        self.ax.set_ylabel("Y Axis")
        ##self.ax.set_zlabel("Z Axis")
        #self.dot, = self.ax.plot([0], [0], [0], 'ro')  # Initial dot position
        self.layout.addWidget(self.canvas,1,0)



 
        
        #2D plot interface 
        plot_control_layout = QVBoxLayout()

        xminlabel=QLabel('x min')
        plot_control_layout.addWidget(xminlabel) 
        xmindoublespinbox = QDoubleSpinBox()
        xmindoublespinbox .setMinimum(-50)
        xmindoublespinbox .setMaximum(50)
        xmindoublespinbox .setSingleStep(1)  # Or e.g. 0.5 for QDoubleSpinBox
        xmindoublespinbox .setDecimals(2)
        xmindoublespinbox .setValue(-50) 
        xmindoublespinbox .valueChanged.connect(self.value_xminchanged)
        xmindoublespinbox .textChanged.connect(self.value_xminchanged_str)
        plot_control_layout.addWidget(xmindoublespinbox ) 


        xmaxlabel=QLabel('x max')
        plot_control_layout.addWidget(xmaxlabel) 
        xmaxdoublespinbox = QDoubleSpinBox()
        xmaxdoublespinbox.setMinimum(-50)
        xmaxdoublespinbox.setMaximum(50)
        xmaxdoublespinbox.setSingleStep(1)  # Or e.g. 0.5 for QDoubleSpinBox
        xmaxdoublespinbox.setDecimals(2)
        xmaxdoublespinbox.setValue(50) 
        xmaxdoublespinbox.valueChanged.connect(self.value_xmaxchanged)
        xmaxdoublespinbox.textChanged.connect(self.value_xmaxchanged_str)
        plot_control_layout.addWidget(xmaxdoublespinbox) 


        yminlabel=QLabel('y min')
        plot_control_layout.addWidget(yminlabel) 
        ymindoublespinbox = QDoubleSpinBox()
        ymindoublespinbox.setMinimum(-50)
        ymindoublespinbox.setMaximum(50)
        ymindoublespinbox.setSingleStep(1)  # Or e.g. 0.5 for QDoubleSpinBox
        ymindoublespinbox.setDecimals(2)
        ymindoublespinbox.setValue(-50) 
        ymindoublespinbox.valueChanged.connect(self.value_yminchanged)
        ymindoublespinbox.textChanged.connect(self.value_yminchanged_str)
        plot_control_layout.addWidget(ymindoublespinbox) 


        ymaxlabel=QLabel('y max')
        plot_control_layout.addWidget(ymaxlabel) 
        ymaxdoublespinbox = QDoubleSpinBox()
        ymaxdoublespinbox.setMinimum(-50)
        ymaxdoublespinbox.setMaximum(50)
        ymaxdoublespinbox.setSingleStep(1)  # Or e.g. 0.5 for QDoubleSpinBox
        ymaxdoublespinbox.setDecimals(2)
        ymaxdoublespinbox.setValue(50) 
        ymaxdoublespinbox.valueChanged.connect(self.value_ymaxchanged)
        ymaxdoublespinbox.textChanged.connect(self.value_ymaxchanged_str)
        plot_control_layout.addWidget(ymaxdoublespinbox) 

    
        

        zminlabel=QLabel('Z min')
        plot_control_layout.addWidget(zminlabel) 
        doublespinbox = QDoubleSpinBox()
        doublespinbox.setMinimum(0)
        doublespinbox.setMaximum(1023)
        doublespinbox.setSingleStep(1)  # Or e.g. 0.5 for QDoubleSpinBox
        doublespinbox.setDecimals(0)
        doublespinbox.setValue(0) 
        doublespinbox.valueChanged.connect(self.value_minchanged)
        doublespinbox.textChanged.connect(self.value_minchanged_str)
        plot_control_layout.addWidget(doublespinbox) 

        zmaxlabel=QLabel('Z max')
        plot_control_layout.addWidget(zmaxlabel)         
        doublespinbox2 = QDoubleSpinBox()
        doublespinbox2.setMinimum(0)
        doublespinbox2.setMaximum(1023)
        doublespinbox2.setSingleStep(1)  # Or e.g. 0.5 for QDoubleSpinBox
        doublespinbox2.setDecimals(0)
        doublespinbox2.setValue(1023) 
        doublespinbox2.valueChanged.connect(self.value_maxchanged)
        doublespinbox2.textChanged.connect(self.value_maxchanged_str)
        plot_control_layout.addWidget(doublespinbox2)  



        plot_control_group = QGroupBox('Plot Control')
        plot_control_group.setLayout(plot_control_layout)   


   
        self.layout.addWidget(plot_control_group,1,1)
        
        
        
        

        self.setLayout(self.layout)
        
        
        self.graph_timer = QTimer(self)
        self.graph_timer.setInterval(279)  # Update every half second
        self.graph_timer.timeout.connect(self.update_visualization)
        self.graph_timer.start()
        
        #Start polling for gamepad inputs
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_gamepad_state)
        self.timer.start(2)  # Update every 50 ms
    def value_xminchanged(self, value):
        global xmin,xmax
        xmin=float(value)

    def value_xminchanged_str(self, str_value):
        global xmin,xmax
        xmin=float(str_value)

    def value_xmaxchanged(self, value):
        global xmin,xmax
        xmax=float(value)

    def value_xmaxchanged_str(self, str_value):
        global xmin,xmax
        xmax=float(str_value)
    def value_yminchanged(self, value):
        global ymin,ymax
        ymin=float(value)

    def value_yminchanged_str(self, str_value):
        global ymin,ymax
        ymin=float(str_value)

    def value_ymaxchanged(self, value):
        global ymin,ymax
        ymax=float(value)

    def value_ymaxchanged_str(self, str_value):
        global ymin,ymax
        ymax=float(str_value)

    
        
    def value_minchanged(self, value):
        global zmin,zmax
        zmin=float(value)

    def value_minchanged_str(self, str_value):
        global zmin,zmax
        zmin=float(str_value)

    def value_maxchanged(self, value):
        global zmin,zmax
        zmax=float(value)

    def value_maxchanged_str(self, str_value):
        global zmin,zmax
        zmax=float(str_value)
        
        
        
        
    def newimagefile(self):
        print("New file created")
        global X, Y, Z,t1,t2,x,idj,idk, filepath, scansize, x0, y0, buferlenght,zmin,zmax, xmin,xmax,ymin,ymax

        # Define parameters for the plot
        scansize = 1023
        numofpoints = 1024
        buferlenght=3

        zmin=0
        zmax=1023

        xmin=-50
        xmax=50

        ymin=-50
        ymax=50


        #x0 = 1023/2
        #y0 = 1023/2
        x = np.linspace(0,1023, numofpoints)
        y = np.linspace(0,1023, numofpoints)
        X, Y = np.meshgrid(x, y)
        Z = np.ones((numofpoints, numofpoints))
        idj=0
        idk=0
        

        #j = int(numofpoints / 2)
        #k = int(numofpoints / 2)
        
        data1={
            "X":[],
            "Y":[],
            "Z":[],
            "timestamp":[]
        }    
        df1=pd.DataFrame(data1)
        df3=pd.DataFrame(data1)
        data2={
            "X":[np.nan],
            "Y":[np.nan],
            "Z":[np.nan],
            "timestamp":[np.nan]
        }   


        df2=pd.DataFrame(data2)


        #To save the dataframe to CSV
        t=datetime.datetime.now()
        filename=t.strftime('%Y_%m_%d_%H_%M_%S')
        filepath = Path(filename+'.csv') 
        df1.to_csv(filepath,index=False)
        t1=datetime.datetime.now()
        t2=datetime.datetime.now()
        x=t2-t1

    def create_data_menu(self, layout):
        """Creates a data menu with a dropdown for each button."""
        h_layout = QHBoxLayout()

        
        bottom_line_edit = QLineEdit(
            "Hello! This is a line edit.", parent=self
        )
        h_layout.addWidget(bottom_line_edit)
        
        button = QPushButton("New Capture file")
        button.clicked.connect(self.newimagefile())
        #h_layout.addWidget(button,1,3)
        
        layout.addLayout(h_layout)


    def create_control_menu(self, layout, control_name, default_action):
        """Creates a control menu with a dropdown for each button."""
        h_layout = QHBoxLayout()

        label = QLabel(f"{control_name}: ")
        label.setStyleSheet("color: black;")  # Change the text color to red
        h_layout.addWidget(label)

        combo_box = QComboBox(self)
        combo_box.addItems(list(function_dic.keys()))
        combo_box.setCurrentText(default_action)
        h_layout.addWidget(combo_box)

        setattr(self, f'{control_name}_menu', combo_box)
        layout.addLayout(h_layout)

    

    def update_gamepad_state(self):
        global t1,t2,x
        #t1=datetime.datetime.now()
        pygame.event.pump()  # Process events

        # Button states
        button_states = {
            'A': gamepad.get_button(1),
            'B': gamepad.get_button(0),
            'X': gamepad.get_button(3),
            'Y': gamepad.get_button(2),
            'Plus': gamepad.get_button(7),
            'Minus': gamepad.get_button(6),
            'Home': gamepad.get_button(10),
            'Capture': gamepad.get_button(10),
            'L': gamepad.get_button(4),
            'ZL': gamepad.get_button(8),
            'R': gamepad.get_button(5),
            'ZR': gamepad.get_button(9),
        }

        # Update button trigger actions
        for button, state in button_states.items():
            
            if state:  # If the button is pressed
                action = getattr(self, f'{button}_menu', None)
                if action:
                    action = action.currentText()
                    if action == "H_curve":
                        H_curve()
                    elif action == "decrease_setpoint":
                        decrease_setpoint()
                    elif action == "increase_setpoint":
                        increase_setpoint()
                    elif action == "Aproach":
                        Aproach()
                    elif action == "interact":
                        interact()
                    elif action == "Withdraw":
                        Withdraw()
                    elif action == "startstop":
                        startstop()
                    elif action == "Select":
                        select()

        # Joystick positions
        left_x = gamepad.get_axis(0)
        left_y = gamepad.get_axis(1)
        try:            
            offsetx=spm.workflow.imaging.property.image_offset_x.value #read x offset
            offsety=spm.workflow.imaging.property.image_offset_y.value #read y offset
            t2=datetime.datetime.now()
            x=t2-t1
            if x.microseconds>100:
                t1=datetime.datetime.now()
                if left_x>0.5:
                    #pygame.joystick.rumble(0,0.7,500)
                    spm.workflow.imaging.property.image_offset_x.value=offsetx+0.5e-6 #Set x offset
                if left_x<-0.5:
                    spm.workflow.imaging.property.image_offset_x.value=offsetx-0.5e-6 #Set x offset
                if left_y>0.5:
                    spm.workflow.imaging.property.image_offset_y.value=offsety-0.5e-6 #Set y offset
                if left_y<-0.5:
                    spm.workflow.imaging.property.image_offset_y.value=offsety+0.5e-6 #Set y offset
        except:
                print("Couldn't move the tip")
            
        
        
        right_x = gamepad.get_axis(2)
        right_y = gamepad.get_axis(3)

        
        # Update GUI
        self.update()

    # Define functions to be executed when gamepad buttons are pressed




    def update_visualization(self):

        self.ax.clear()
        



        # Update plot with new colormap limits
        RZ = ndimage.rotate(Z, 90)
        self.ax.imshow(RZ, cmap='viridis', vmin=zmin, vmax=zmax,extent=[-50,50,-50,50])
        #self.ax.imshow(Z2, cmap='hot', alpha=0.9)

        self.ax.plot([-50, 50], [100/1023*idk-50, 100/1023*idk-50], color='red', lw=0.5)  # Horizontal line
        self.ax.plot([100/1023*idj-50, 100/1023*idj-50], [-50, 50], color='red', lw=0.5)  # Vertical line

        self.ax.set_xlabel("X Axis")
        self.ax.set_ylabel("Y Axis")
        # Normalize color mapping
        self.ax.set_xlim(xmin,xmax)
        self.ax.set_ylim(ymin,ymax)
        
    
        self.canvas.draw()        

# Create application and window
app = QApplication(sys.argv)
window = GamepadMonitor()
window.show()
sys.exit(app.exec())



# %%
