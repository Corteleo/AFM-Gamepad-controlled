#Initialize ---
import nanosurf #Load nanosurf library.
studio = nanosurf.Studio() #Create Studio instance.
studio.connect() #Connect to the Studio sesion running.
spm = studio.spm

#Move tip and read x y z ---
offsetx=spm.workflow.imaging.property.image_offset_x.value #read x offset (i.e. current tip position), replace x by y to get y offset.
newxofset=offsetx+0.2e-6 #Set x offset
spm.workflow.imaging.property.image_offset_x.value=newxofset #Increase x offset
spm.lu.analog_hi_res_out.position_z.attribute.current_output_value.value #Read the z position according to the desired piezo position.
spm.lu.analog_hi_res_in.position_x.attribute.current_input_value.value #Read the x position according to the x sensor.

#Feedback ---
zposition=spm.core.z_controller.property.current_position.value #Read the idle mode z position
spm.core.z_controller.property.idle_position.value=zposition+1e-6 #Set the idle mode z position
spm.core.z_controller.property.idle_mode.value = spm.core.z_controller.property.idle_mode.value.Set_Z_Position #Set the z feedback to specific z position
spm.core.z_controller.property.idle_mode.value = spm.core.z_controller.property.idle_mode.value.Retract_Tip #Retract the tip
currentsetpoint=spm.core.z_controller.property.actual_feedback_value.value #Read current setpoint.
newsetpoint=currentsetpoint-0.1*currentsetpoint
spm.core.z_controller.property.setpoint.value=newsetpoint #Decrease setpoint.
spm.core.z_controller.property.idle_mode.value = spm.core.z_controller.property.idle_mode.value.Enable_Z_Controller #Enable the z feedback


#Imaging ---
spm.workflow.imaging.property.auto_generator.value=False #Disable auto scan generator
spm.workflow.imaging.property.generator.value=spm.workflow.imaging.property.generator.value.Spiral_Scan #Change the scan type to spiral
spm.workflow.imaging.property.line_rate.value=1 #Set line rate in Hz
spm.workflow.imaging.property.points_per_line.value=256 #Set number of pixels
spm.workflow.imaging.property.scan_range_fast_axis.value=30e-6 #Set scan range along fast scan axis
spm.workflow.imaging.property.scan_range_slow_axis.value=30e-6 #Set scan range along slow scan axis
spm.workflow.imaging.start_imaging() #Start imaging
is_scanning=spm.workflow.imaging.is_scanning() #True or false value indicating if system is currently scanning.
spm.workflow.imaging.stop_imaging() #Stop imaging