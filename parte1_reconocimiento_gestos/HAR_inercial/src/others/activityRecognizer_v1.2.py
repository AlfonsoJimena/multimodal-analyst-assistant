#!/usr/bin/python
from tensorflow.keras.models import model_from_json
from scipy.io.arff import loadarff
import threading
import traceback
import numpy as np
#import javabridge
import csv
import pandas as pd

import argparse

from collections import defaultdict
from datetime import datetime

from AR_modules.config.general import RASPI, WEKA, debug, TRAIN, TRAIN_FROM_DATA_SET, TRAINING_LENGTH_PER_ACTIVITY, RECORD_MODE, TEST_MODE
#from AR_modules.weka.wekaLib import *
from AR_modules.keypress.keypress import getch
from AR_modules.timing.timing import RepeatedTimer
from AR_modules.timing.timing import AccelerometerRecorder
#from AR_modules.octave.featureExtraction import FeatureExtraction

from AR_modules.config.general import FEATURES_PATH, MODELS_PATH, DATA_PATH, RAW_DATA_PATH, DATA_SET, MODELS_PREFIX, CLASSIFIER_NAME #, CLASSIFIER_OPTIONS

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

print("\t[TRAIN MODE][%d]" % TRAIN)
if TRAIN:
    print("\t[TRAIN LENGTH PER ACTIVITY][%d]" % TRAINING_LENGTH_PER_ACTIVITY)

print("\t[DEBUG MODE][%d]\n" % debug)

recorder.printRecorderInfo()

def Recognize(model, test_data):
    global sense
    
    if debug:
        print("\n[Recognize]\n")
    
    for index, inst in enumerate(test_data):
        pred = model.classify_instance(inst)
        dist = model.distribution_for_instance(inst)
        print(
            str(index+1) + ": label index=" + str(pred) + 
            ", class distribution=" + str(dist) + 
            ", predicted=" +  inst.class_attribute.value(int(pred)) + 
            ", actual=" + inst.get_string_value(inst.class_index))
        
        if RASPI:
            if MODELS_PREFIX == "UP_SIT_PITCH_ROLL_YAW":
                if int(pred) == 0:
                    #sense.set_pixels(stand_pixel_list)
                    sense.set_pixels(UP_list)
                elif int(pred) == 1:
                    #sense.set_pixels(sit_pixel_list)
                    sense.set_pixels(SIT_list)
                elif int(pred) == 2:
                    sense.set_pixels(PITCH_list)
                elif int(pred) == 3:
                    sense.set_pixels(ROLL_list)
                else:
                    #sense.set_pixels(walk_pixel_list)
                    sense.set_pixels(YAW_list)
            else:
                num_colours = len(colour_array)
                p_colour = int(pred)
                
                if p_colour > num_colours:
                    p_colour = num_colours
                
                #sense.show_message(inst.class_attribute.value(int(pred)), text_colour=colour_array[p_colour], scroll_speed=0.05)
                sense.show_message(inst.class_attribute.value(int(pred)), text_colour=colour_array[p_colour])

def Recognize_lstm(model, tensor):
    global sense
    
    if debug:
        print("\n[Recognize]\n")
    
        print("Instance to predict",tensor)
        print("Size of the instance",len(tensor))
        
    #classes = ["DRIVE","BACKHAND","SERVE","LOB"]
    classes = MODELS_PREFIX.split("_")
    
    dist = model.predict(tensor)
    #print("prediction distributions:",dist)
    pred = classes[np.argmax(dist, axis=1)]
    print("predicted class:",pred)
        
    if RASPI:
                
            #sense.show_message(inst.class_attribute.value(int(pred)), text_colour=colour_array[p_colour], scroll_speed=0.05)
            sense.show_message(pred, scroll_speed=0.1)

def RecordIntancesForClass(dataset, sample_instance, training_step, num_frames_to_record):
    global recorder
    
    recorder.item = 0

    recorder.ResetRecordingParameters()
    
    timer = RepeatedTimer(0.02, recorder.ReadAccelerometer) 
    num_frames_recorded = 0
    while(1):
        if (num_frames_recorded >= num_frames_to_record):
            timer.stop ()
            if debug:
               print("[RecordIntancesForClass][num_frames_recorded = " + str(num_frames_recorded) + "]")
               print("[RecordIntancesForClass][timer.stop ()]")
            break
        
        # consumer thread
        recorder.condition.acquire()
        while True:
            #... get item from resource
            recorder.count_lock.acquire()
            try:
                if recorder.item:
                    if debug:
                       print("[RecordIntancesForClass][NEW FRAME]")
                
                    DumpAccelerationValuesToFile(fd_raw_data, 
                                                 recorder.AccXarray, 
                                                 recorder.AccYarray, 
                                                 recorder.AccZarray, 
                                                 training_step+1, raw_data_filename)
                    
                    numerical_values = FeatureExtraction(recorder.AccXarray, 
                                                         recorder.AccYarray, 
                                                         recorder.AccZarray,
                                                         recorder.window_size, recorder.overlap, debug)
       
                    #print numerical_values
                    dataset = LoadInstanceForTraining(dataset, sample_instance, numerical_values, training_step)
                    #print dataset
                    
                    num_frames_recorded = num_frames_recorded + 1
                    
                    recorder.item = 0
                    break
            finally:
                recorder.count_lock.release() # release lock, no matter what
            
            recorder.condition.wait() # sleep until item becomes available
        recorder.condition.release()
        #... process item
    return dataset

def TrainNewModel(seconds_per_activity):
       
    #seconds_per_activity = 30
    num_samples_per_frame = (recorder.window_size - recorder.overlap) # every "num_samples_per_frame" samples we have a new frame
    num_seconds_per_frame = recorder.interval*num_samples_per_frame # we take one sample per "INTERVAL" seconds
    frames_per_activity = round(seconds_per_activity / num_seconds_per_frame)

    print("\n[TRAINING NEW MODEL]")
    print("\t[new frame every " + str(num_samples_per_frame) + " samples]")
    print("\t[new frame every " + str(num_seconds_per_frame) + " seconds]")
    print("\t[recording " + str(frames_per_activity) + " new frames per class]")
    
    [train_data, sample_instance] = InitNewDataset()
    target_attribute = train_data.attribute_by_name("activity")
    
    activities = target_attribute.values
    num_activities = target_attribute.num_values

    print("\t[ACTIVITY SET]")
    for step in range(0, num_activities):
        print("\t\t[" + str(step+1) + "][" + activities[step] + "]")
    
    num_training_steps = target_attribute.num_values
    #print activities
        
    for step in range(0, num_training_steps):
    
        print("\n[TRAINING NEW MODEL][STEP " + str(step+1) + " OF " + str(num_training_steps) + "]")
        print("[ACTIVITY][" + activities[step] + "]")
        print("[press q to quit; press c to continue]")
        quit=False
        # loop
        while quit !=True:
            c = getch()
            if (c == "q"):
                quit=True
            elif (c == "c"):
                print("\n[ACTIVITY RECORDING!!!]")
                train_data = RecordIntancesForClass(train_data, sample_instance, step, frames_per_activity)
                
                if debug:
                    print(train_data)
                break
        if quit:
            exit(0)
            
    train_data.class_is_last()
    
    # train classifier
    #classifier = Classifier("weka.classifiers.trees.RandomForest",  options=["-I","100","-K","0","-S","1"])
    classifier = Classifier(CLASSIFIER_NAME, options=[option for option in CLASSIFIER_OPTIONS])
        
    classifier.build_classifier(train_data)
       
    # save arff dataset
    arff_outfile = FEATURES_PATH + "raspi_training_data_mfcc_plp_online_" + MODELS_PREFIX + datetime.now().strftime('_%Y-%m-%d_%H:%M:%S') + ".arff"
    print("\n[TrainNewModel][NEW DATASET][%s]\n" % arff_outfile)
    saver = Saver(classname="weka.core.converters.ArffSaver")
    saver.save_file(train_data, arff_outfile)
    
    # save classifier object
    model_outfile = MODELS_PATH + "raspi_data_mfcc_plp_online_" + MODELS_PREFIX + "_" + CLASSIFIER_NAME + ".model"
    
    print("\n[TrainNewModel][NEW MODEL][%s]\n" % model_outfile)
    serialization.write(model_outfile, classifier)
    
    fd_raw_data.close()
    
def TrainNewModelFromDataset():
       
    print("\n[TRAINING NEW MODEL FROM DATASET]")
    # save arff dataset
    train_data_arff = FEATURES_PATH + DATA_SET
    
    print("\n[TrainNewModelFromDataset][DATASET][%s]\n" % train_data_arff)
    
    print("\n[LOADING WEKA DATASET][%s]" % train_data_arff)
    train_data = LoadDataset(train_data_arff) 

    # train classifier
    #classifier = Classifier("weka.classifiers.trees.RandomForest",  options=["-I","100","-K","0","-S","1"])
    classifier = Classifier(CLASSIFIER_NAME, options=[option for option in CLASSIFIER_OPTIONS])
        
    classifier.build_classifier(train_data)      
    
    # save classifier object
    model_outfile = MODELS_PATH + "raspi_data_mfcc_plp_online_" + MODELS_PREFIX + "_" + CLASSIFIER_NAME + ".model"
    
    print("\n[TrainNewModel][NEW MODEL][%s]\n" % model_outfile)
    serialization.write(model_outfile, classifier)

def DumpAccelerationValuesToFile(fd, auxAccXarray, auxAccYarray, auxAccZarray, auxClass, auxFilename):
    
    auxDelimiter = ';'
    
    if debug:
        print("[DumpAccelerationValuesToFile][" + auxFilename + "][NEW FRAME FOR CLASS " + str(auxClass) + "]")
    
    # We concatenate the acceleration values arrays as a single vector/array
    auxAccSuperVector = np.concatenate((auxAccXarray, auxAccYarray, auxAccZarray), axis=0)

    # We dump accel values to file...
    np.savetxt(fd, auxAccSuperVector, fmt='%10.8f', delimiter=auxDelimiter, newline=' ')
    
    # ... together with the class corresponding to the values recorded
    np.savetxt(fd, [auxClass], fmt='%d', delimiter=auxDelimiter, newline='\r\n')

def record_lstm_dataset(seconds_per_activity=30,num_training_steps=3):
    
    num_samples_per_frame = (recorder.window_size - recorder.overlap) # every "num_samples_per_frame" samples we have a new frame
    num_seconds_per_frame = recorder.interval*num_samples_per_frame # we take one sample per "INTERVAL" seconds
    frames_per_activity = round(seconds_per_activity / num_seconds_per_frame)
    
    #global recorder
    global timer
    
    print("\n[RECORDING NEW DATA]")
    print("\t[new frame every " + str(num_samples_per_frame) + " samples]")
    print("\t[new frame every " + str(num_seconds_per_frame) + " seconds]")
    print("\t[recording " + str(frames_per_activity) + " new frames per class]")
    
    activities = DATA_SET.split("_")
    
    num_activities = len(activities)
    sample_instance=[0]

    print("\t[ACTIVITY SET]")
    for step in range(0, num_activities):
        print("\t\t[" + str(step+1) + "][" + activities[step] + "]")
            
    for step in range(0, num_training_steps): # num training steps = activities ?
     
        print("\n[TRAINING NEW MODEL][STEP " + str(step+1) + " OF " + str(num_training_steps) + "]")
        print("[ACTIVITY][" + activities[step] + "]")
        print("[press q to quit; press c to continue]")
        
        quit=False
        csv_data=[]
        
        recorder.count_lock.acquire()
        
        try:
            recorder.count = 0 # access shared resource
        finally:
            recorder.count_lock.release() # release lock, no matter what
        
        recorder.item = 0
       
        # call ReadAccelerometer 50 times per second, forever
        timer = RepeatedTimer(0.02, recorder.ReadAccelerometer) 
        
        # loop
        
        while(1):
            # consumer thread
            recorder.condition.acquire()
        
            while quit !=True:
                c = getch()
                if (c == "q"):
                    quit=True
                elif (c == "c"):
                    print("\n[ACTIVITY RECORDING!!!]")
                    
                    recorder.count_lock.acquire()
                    
                    print(recorder)
                    print(recorder.item)
                    
                    try:
                        if recorder.item:
                            print(recorder.AccXarray+recorder.AccYarray+recorder.AccZarray+[activities[step]])
                    finally:
                        recorder.count_lock.release()     
                    recorder.condition.wait() # sleep until item becomes available
        
                if quit:
                    exit(0)
                    
                recorder.condition.release()
    
def main(model, test_data):
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
                    if WEKA:
                        numerical_values = FeatureExtraction(recorder.AccXarray,
                                                                recorder.AccYarray,
                                                                recorder.AccZarray, 
                                                                recorder.window_size, recorder.overlap, debug)

                        test_data = LoadInstanceForRecognition(test_data, numerical_values)
                            #print test_data.get_instance(0)
                            
                        Recognize(model, test_data)
                    
                    else:                        
                        
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
            
        #jvm.start(max_heap_size="1200m")
        test_data_filename = DATA_PATH + DATA_SET + ".arff"
        
        if RECORD_MODE:
            
            record_lstm_dataset()
            
        if TEST_MODE:
            
            if WEKA:
                model_filename = MODELS_PATH + "raspi_data_mfcc_plp_online_" + MODELS_PREFIX + "_" + CLASSIFIER_NAME + ".model"
                print("\n[LOADING WEKA MODEL][%s]" % model_filename)
                model = LoadClassifier(model_filename)
                
                print("\n[LOADING WEKA DATASET][%s]" % test_data_filename)
                test_data = LoadDataset(test_data_filename) #test_data = LoadDataset("aux_features_raspi.arff")
            
            else:
                #cambiar .model por .h5/.json
                model_filename = MODELS_PATH + "raspi_data_mfcc_plp_online_" + MODELS_PREFIX + "_" + CLASSIFIER_NAME
                print("\n[LOADING LSTM MODEL][%s]" % model_filename)
                json_file = open(model_filename+'.json', 'r')
                loaded_model_json = json_file.read()
                json_file.close()
                model = model_from_json(loaded_model_json)
                # load weights into new model
                model.load_weights(model_filename+".h5")
                print("\n[LOADING LSTM DATASET][%s]" % test_data_filename)
                #test_data=loadarff(test_data_filename)
                test_data=None #EN MODO TEST SIN WEKA NO SE UTILIZA TEST_DATA
                   
            main(model, test_data)
        
    except Exception:
        print(traceback.format_exc())

    finally:
        #timer.stop()
        #jvm.stop()
        print("\nnum_mini_buffers_recorded = " + str(recorder.num_mini_buffers_recorded))
        print("num_samples_recorded = " + str(recorder.num_samples_recorded))
        exit(1)
