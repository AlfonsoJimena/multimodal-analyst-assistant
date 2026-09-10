#!/usr/bin/python
from tensorflow.keras.models import model_from_json
import threading
import traceback
import numpy as np
import csv

import argparse

from collections import defaultdict
from datetime import datetime

from AR_modules.config.general_recognizer import RASPI, debug
from AR_modules.config.general_recognizer import MODELS_PATH, MODEL_NAME, CLASSES
from AR_modules.timing.timing import RepeatedTimer
from AR_modules.timing.timing import AccelerometerRecorder

if RASPI:
    from AR_modules.sensehat.RTIMULib import InitializeRTIMU
    from AR_modules.sensehat.displayLib import ShowInitialMsg
    from AR_modules.sensehat.displayLib import InitializeDisplay
    #from AR_modules.sensehat.displayLib import stand_pixel_list, sit_pixel_list, walk_pixel_list
    #from AR_modules.sensehat.displayLib import UP_list,SIT_list,PITCH_list,ROLL_list,YAW_list
    from AR_modules.sensehat.displayLib import DRIVE_list, LOB_list, SERVE_list, BACKHAND_list
    from AR_modules.sensehat.displayLib import colour_array, OFF

    import sys, getopt

    sys.path.append('.')
    import RTIMU
    import os.path
    import time
    import math

parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('-d', '-D', nargs = '?', const = 1, default = 0, help='DEBUG MODE ON')
parser.set_defaults()
#print parser.get_default('arg_train')
args = parser.parse_args()

print("\nargs:")
print(args)
    
debug = args.d

columns = defaultdict(list) # each value in each column is appended to a list

if RASPI:
    print("\n[InitializeRTIMU]") 
    
    SETTINGS_FILE = "RTIMULib"
    
    print("Using settings file " + SETTINGS_FILE + ".ini")
    if not os.path.exists(SETTINGS_FILE + ".ini"):
       print("Settings file does not exist, will be created")
    
    s = RTIMU.Settings(SETTINGS_FILE)
    imu = RTIMU.RTIMU(s)
    print("IMU Name: " + imu.IMUName())
    
    if (not imu.IMUInit()):
       print("IMU Init Failed")
       sys.exit(1)
    else:
       print("IMU Init Succeeded")
    
    imu.setAccelEnable(True)
    poll_interval = imu.IMUGetPollInterval()
    print("Recommended Poll Interval: %dmS\n" % poll_interval)
else:
    imu = 0

recorder = AccelerometerRecorder(
    150, # WINDOW_SIZE
    100, # OVERLAP
    #75, # WINDOW_SIZE
    #50, # OVERLAP
    0.02, imu) # INTERVAL in secs == 20 ms

print("\n[ACTIVITY RECOGNIZER]\n")

print("\t[DEBUG MODE][%d]\n" % debug)

recorder.printRecorderInfo()

def wait_for_keypress(target_key, exit_key, yes_to_all_key):
    print(f"Press '{target_key}' to continue or '{exit_key}' to exit... ('{yes_to_all_key}') if YES to all...")
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    yes_to_all_result = False
    
    try:
        tty.setraw(sys.stdin.fileno())
        while True:
            char = sys.stdin.read(1)
            if char == target_key:
                break
            elif char == yes_to_all_key:
                print("Yes to all...")
                yes_to_all_result = True
                break
            elif char == exit_key:
                print("Exiting...")
                sys.exit(0)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return yes_to_all_result

def Recognize_lstm(model, tensor):
    
    global sense
    
    if debug:
        print("\n[Recognize]\n")
    
        print("Instance to predict", tensor)
        print("Size of the instance", len(tensor))
        
    classes = CLASSES.split("_")
    
    dist = model.predict(tensor)
    num_pred = np.argmax(dist, axis=1)[0]
    pred = classes[num_pred]
    print("Predicted class:", pred)
        
    if RASPI:
        if CLASSES == "DRIVE_BACKHAND_SERVE_LOB":
            if num_pred == 0:
                sense.set_pixels(DRIVE_list)
            elif num_pred == 1:
                sense.set_pixels(BACKHAND_list)
            elif num_pred == 2:
                sense.set_pixels(SERVE_list)
            elif num_pred == 3:
                sense.set_pixels(LOB_list)
            else:
                sense.set_pixels(OFF)
        else:
            num_colours = len(colour_array)
            p_colour = num_pred
            
            if p_colour > num_colours:
                p_colour = num_colours
            sense.show_message(inst.class_attribute.value(num_pred), text_colour=colour_array[p_colour], scroll_speed=0.05)
            #sense.show_message(pred, scroll_speed=0.1)
    
def main(model):
    global timer
    global sense
    global recorder

    if RASPI:
        ShowInitialMsg(sense)
  
    recorder.count_lock.acquire()
    try:
        recorder.count = 0 # access shared resource
    finally:
        recorder.count_lock.release() # release lock, no matter what
        
    recorder.item = 0
       
    # call ReadAccelerometer 50 times per second, forever
    timer = RepeatedTimer(0.02, recorder.ReadAccelerometer)
            
    while(1):
        # consumer thread
        recorder.condition.acquire()
        while True:
            #... get item from resource
            recorder.count_lock.acquire()
            try:
                if recorder.item:
                    tensor = np.array([recorder.AccXarray, recorder.AccYarray, recorder.AccZarray]).flatten()
                    
                    if debug:
                        print("INITIAL TENSOR:",tensor)
                    
                    tensor = np.reshape(tensor,newshape=(-1, recorder.buffer_size,3), order='F')
                    
                    if debug:
                        print("RESHAPED TENSOR:",tensor)
                    
                    Recognize_lstm(model, tensor)
                    recorder.item = 0
                    break
            except KeyboardInterrupt:
                # Handle the CTRL+C interruption here
                print("CTRL+C pressed. Exiting gracefully...")
                timer.stop ()
                break
            finally:
                recorder.count_lock.release() # release lock, no matter what
                
            recorder.condition.wait() # sleep until item becomes available
        recorder.condition.release()
        #... process item

if __name__ == "__main__":
    try:
        if RASPI:
            print("[InitializeDisplay]")
            sense = InitializeDisplay()
        
        # Cambiar .model por .h5/.json
        model_filename = MODELS_PATH + MODEL_NAME
        print("\n[LOADING LSTM MODEL][%s]" % model_filename)
        
        json_file = open(model_filename+'.json', 'r')
        loaded_model_json = json_file.read()
        json_file.close()
        model = model_from_json(loaded_model_json)
        
        # load weights into new model
        model.load_weights(model_filename + '.h5')
                
        main(model)
        
    except Exception:
        print(traceback.format_exc())

    # The finally block ensures that certain cleanup or finalization code is always executed, whether an exception occurred or not.
    finally:
        # Create a list to store existing threads
        all_threads = []

        # Enumerate all currently alive threads and add them to the list
        for thread in threading.enumerate():
            all_threads.append(thread)
        print('Number of existing threads = %d' % len(all_threads))
        
        print("\nnum_mini_buffers_recorded = " + str(recorder.num_mini_buffers_recorded))
        print("num_samples_recorded = " + str(recorder.num_samples_recorded))
        exit(0) # Exits with an exit status of 0 (indicating success).
