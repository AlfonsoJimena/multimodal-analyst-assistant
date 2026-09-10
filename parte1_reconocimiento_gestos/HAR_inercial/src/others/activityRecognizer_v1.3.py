#!/usr/bin/python
from tensorflow.keras.models import model_from_json
from scipy.io.arff import loadarff
import threading
import traceback
import numpy as np
import csv

import argparse

from collections import defaultdict
from datetime import datetime

from AR_modules.config.general import RASPI, debug, TRAINING_LENGTH_PER_ACTIVITY, RECORD_MODE, TEST_MODE
from AR_modules.timing.timing import RepeatedTimer
from AR_modules.timing.timing import AccelerometerRecorder

from AR_modules.config.general import MODELS_PATH, DATA_PATH, DATA_SET, CLASSIFIER_NAME, NUM_USERS

if RASPI:
    from AR_modules.sensehat.RTIMULib import InitializeRTIMU
    from AR_modules.sensehat.displayLib import ShowInitialMsg
    from AR_modules.sensehat.displayLib import InitializeDisplay
    from AR_modules.sensehat.displayLib import stand_pixel_list, sit_pixel_list, walk_pixel_list
    from AR_modules.sensehat.displayLib import UP_list,SIT_list,PITCH_list,ROLL_list,YAW_list,DRIVE_list,LOB_list,SERVE_list,BACKHAND_list
    from AR_modules.sensehat.displayLib import colour_array

    import sys, getopt

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
        TRAIN = 1
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
    
        print("Instance to predict",tensor)
        print("Size of the instance",len(tensor))
        
    classes = DATA_SET.split("_")
    
    dist = model.predict(tensor)
    pred = classes[np.argmax(dist, axis=1)[0]]
    print("predicted class:", pred)
        
    if RASPI:          
            #sense.show_message(inst.class_attribute.value(int(pred)), text_colour=colour_array[p_colour], scroll_speed=0.05)
            sense.show_message(pred, scroll_speed=0.1)


def record_lstm_dataset(csv_path,num_frames_to_record=TRAINING_LENGTH_PER_ACTIVITY):
    
    print("\n[RECORDING NEW DATA]")
    print("\t[recording " + str(num_frames_to_record) + " new frames per class]\n")
    
    activities = DATA_SET.split("_")
    num_activities=len(activities)
    
    global recorder
    print("RECORDING ACTIVITIES FROM",NUM_USERS,"USERS.")
    print("\t[ACTIVITY SET]")
    for step in range(0, num_activities):
        print("\t\t[" + str(step+1) + "][" + activities[step] + "]")
        
    # initialize array of output data
    csv_data=[]
        
    for user in range(NUM_USERS):
        
        print("[USER][" + str(user) + "]")
        print("[Change the user and get ready to start recording!]\n")
        
        for step in range(0, num_activities):
            
            recorder.item = 0
            recorder.ResetRecordingParameters()
            timer = RepeatedTimer(0.02, recorder.ReadAccelerometer)
            num_frames_recorded = 0
            
            print("[ACTIVITY][" + activities[step] + "]")
            key=input("[press q to quit; press c to continue]")
            
            if key!="c":
                exit()
            
            print("RECORDING!!!!")
            
            while(1):
                if (num_frames_recorded >= num_frames_to_record):
                    timer.stop ()
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
                            print("Recorded",num_frames_recorded,"frames.")
                            
                            recorder.item = 0
                            break
                    finally:
                        recorder.count_lock.release() # release lock, no matter what
                    
                    recorder.condition.wait() # sleep until item becomes available
                recorder.condition.release()
                
    #save data in csv
    print("SAVING RECORDED DATA IN ", csv_path)
    with open(csv_path,"a") as f:
        csv_writer=csv.writer(f)
        csv_writer.writerows(csv_data)

    
    
def main(model):
    global timer
    global sense
    global recorder
    
    #demoArray = np.array([[1, 2, 3],[4,5,6],[7,8,9]], dtype=float)

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
                        
                        tensor = np.array([recorder.AccXarray,recorder.AccYarray,recorder.AccZarray]).flatten()
                        #print("INITIAL TENSOR:",tensor)
                        tensor = np.reshape(tensor,newshape=(-1,recorder.buffer_size,3),order='F')
                        #print("RESHAPED TENSOR:",tensor)
                        Recognize_lstm(model, tensor)
                        recorder.item = 0
                        break
                    
            finally:
                recorder.count_lock.release() # release lock, no matter what
                
            recorder.condition.wait() # sleep until item becomes available
        recorder.condition.release()
        #... process item

#    while(1):
#        time.sleep(1)
#        print "."

if __name__ == "__main__":
    try:
        if RASPI:
            print("[InitializeDisplay]")
            sense = InitializeDisplay()
        
        if RECORD_MODE:
            csv_path=DATA_PATH + DATA_SET + "_" + str(datetime.now()).replace(" ","_") + ".csv"
            print(csv_path)
            record_lstm_dataset(csv_path)
            
        if TEST_MODE:
            
            #cambiar .model por .h5/.json
            model_filename = MODELS_PATH + CLASSIFIER_NAME
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

    finally:

        print("\nnum_mini_buffers_recorded = " + str(recorder.num_mini_buffers_recorded))
        print("num_samples_recorded = " + str(recorder.num_samples_recorded))
        exit(1)
