import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from tkinter import Tk     # from tkinter import Tk for Python 3.x
from tkinter.filedialog import askopenfilename
import pandas as pd
from datetime import datetime
#Ask user for file to be loaded
Tk().withdraw() # we don't want a full GUI, so keep the root window from appearing
filename = askopenfilename() # show an "Open" dialog box and return the path to the selected file
#Load the data
df = pd.read_csv(filename)
xdata = df["X"].tolist()
ydata = df["Y"].tolist()
zdata = df["Z"].tolist()
tdata = df["timestamp"].tolist()

# print(df.to_string()) Use this to visualize the data structure.

# Next, we need an square array to visualize the data, which is not square, so we create an array
# and change its values according to proximity.
zmin=490
zmax=535
xmin=-50
xmax=50
ymin=-50
ymax=50
scansize = 1023
numofpoints = 1024
x = np.linspace(0,1023, numofpoints)
y = np.linspace(0,1023, numofpoints)
tdata_time=[]
for i in range(len(xdata)):
    tdata_time.append(pd.to_datetime(tdata[i], format='%Y-%m-%d %H:%M:%S.%f'))
X, Y = np.meshgrid(x, y)
Z = np.ones((numofpoints, numofpoints))
idj=0
idk=0
#For each data point, we find the closest point in our square array    
for i in range(len(xdata)):
    pos_x = float(xdata[i])
    pos_y = float(ydata[i])
    pos_z = float(zdata[i])
    if tdata_time[i]>=tdata_time[0]:# Here we can use this to restrict the data visualization to a specific range.
        if tdata_time[i]<=tdata_time[-1]:
            idj = (np.abs(X[0, :] - pos_x)).argmin()
            idk = (np.abs(Y[:, 0] - pos_y)).argmin()
            Z[idj, idk] =1024-pos_z #Z data is inverted    
#Plot the data in 2D
plt.imshow(Z, cmap='viridis', vmin=zmin, vmax=zmax,extent=[-50,50,-50,50])   
plt.show()
#Plot the data in 3D
fig, ax = plt.subplots(subplot_kw={"projection": "3d"})
ax.plot_surface(X, Y, Z, cmap='viridis')  # Plot the updated data