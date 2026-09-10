#!/usr/bin/python
from tensorflow.keras.models import model_from_json
from scipy.io.arff import loadarff
import threading
import traceback
import numpy as np
import csv

import argparse

import sys
import tty
import termios


from collections import defaultdict
from datetime import datetime

from AR_modules.config.general_recorder import RASPI, debug, TRAINING_LENGTH_PER_ACTIVITY
from AR_modules.config.general_recorder import DATA_PATH, DATA_SET, NUM_USERS
from AR_modules.timing.timing import RepeatedTimer
from AR_modules.timing.timing import AccelerometerRecorder

if RASPI:
    from AR_modules.sensehat.RTIMULib import InitializeRTIMU
    from AR_modules.sensehat.displayLib import ShowInitialMsg
    from AR_modules.sensehat.displayLib import InitializeDisplay
    from AR_modules.sensehat.displayLib import stand_pixel_list, sit_pixel_list, walk_pixel_list
    from AR_modules.sensehat.displayLib import RECORDING,OFF
    from AR_modules.sensehat.displayLib import colour_array

    import getopt

    sys.path.append('.')
    import RTIMU
    import os.path
    import time
    import math

parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('-t', '-T', nargs = 1, dest = 'train_length_per_activity', help='TRAINING MODE ON - seconds to record per activity')
parser.add_argument('-d', '-D', nargs = '?', const = 1, default = 0, help='DEBUG MODE ON')
parser.set_defaults()
#print parser.get_default('arg_train')
args = parser.parse_args()

print("\nargs:")
print(args)

if args.train_length_per_activity != None and args.train_length_per_activity[0] > 0:
    TRAINING_LENGTH_PER_ACTIVITY = int(args.train_length_per_activity[0])
    
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

print("\n[ACTIVITY RECORDER]\n")

print("\t[DEBUG MODE][%d]\n" % debug)

recorder.printRecorderInfo()

def wait_for_keypress(target_key, exit_key, yes_to_all_key):
    print(f"Press '{target_key}' to continue or '{exit_key}' to exit... ('{yes_to_all_key}') if YES to all...")
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    result = ''
    
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
        result = char
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return result

def record_raw_dataset(csv_path, num_frames_to_record=TRAINING_LENGTH_PER_ACTIVITY):
    succesfull_recording = True
    print("\n[RECORDING NEW DATA]")
    print("\t[recording " + str(num_frames_to_record) + " new frames per class]\n")
    
    activities = DATA_SET.split("_")
    num_activities=len(activities)
    
    global recorder
    print("RECORDING ACTIVITIES FROM", NUM_USERS, "USERS.")
    print("\t[ACTIVITY SET]")
    for step in range(0, num_activities):
        print("\t\t[" + str(step+1) + "][" + activities[step] + "]")
        
    # initialize array of output data
    csv_data=[]
        
    for user in range(NUM_USERS):
        
        print("[USER][" + str(user) + "]")
        print('[Change the user and get ready to start recording!]')
        
        for step in range(0, num_activities):
            
            recorder.item = 0
            recorder.ResetRecordingParameters()
            timer = RepeatedTimer(0.02, recorder.ReadAccelerometer)
            num_frames_recorded = 0
            
            print('\n[ACTIVITY][' + activities[step] + ']')
            
            #key=input("[press q to quit; press c to continue]")
            key = wait_for_keypress('c', 'q', 'y')
            if key == 'q':
                #exit(0)
                timer.stop ()
                succesfull_recording = False
                break
            
            print("RECORDING!!!!")
            if RASPI:
                sense.set_pixels(RECORDING)

            while(1):
                if (num_frames_recorded >= num_frames_to_record):
                    timer.stop ()
                    if RASPI:
                        sense.set_pixels(OFF)
                    break
                
                # consumer thread
                recorder.condition.acquire()
                while True:
                    #... get item from resource
                    recorder.count_lock.acquire()
                    try:
                        if recorder.item:
                        
                            #get new data row and append it to csv data
                            new_data=list(recorder.AccXarray)+list(recorder.AccYarray)+list(recorder.AccZarray)+[activities[step],user]
                            csv_data.append(new_data)
                       
                            if debug:
                                print(new_data)
                            
                            num_frames_recorded = num_frames_recorded + 1
                            
                            # Clear the current line before printing the new message
                            print(f"\rRecorded {num_frames_recorded} out of {num_frames_to_record} frames.", end='', flush=True)
                            
                            recorder.item = 0
                            break
                    finally:
                        recorder.count_lock.release() # release lock, no matter what
                    
                    recorder.condition.wait() # sleep until item becomes available
                recorder.condition.release()
    
    if succesfull_recording:
        # save data in csv
        print('\n[RECORDED DATA SAVED IN ', csv_path, ']')
        with open(csv_path, 'a') as f:
            csv_writer = csv.writer(f)
            csv_writer.writerows(csv_data)

if __name__ == "__main__":
    try:
        if RASPI:
            print("[InitializeDisplay]")
            sense = InitializeDisplay()
        
        # Get the current timestamp with a custom format
        timestamp = datetime.now().strftime('%Y-%m-%d_%H.%M.%S')

        # Construct the CSV file path
        csv_path = DATA_PATH + DATA_SET + '_' + timestamp + '.csv'

        print(csv_path)
        record_raw_dataset(csv_path)
        
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
