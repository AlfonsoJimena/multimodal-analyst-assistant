#!/usr/bin/python

import threading
import traceback
import numpy as np
#import javabridge
import csv

import argparse

from collections import defaultdict
from datetime import datetime

from AR_modules.config.general import RASPI, debug, TRAIN, TRAINING_LENGTH_PER_ACTIVITY
from AR_modules.weka.wekaLib import *
from AR_modules.keypress.keypress import getch
from AR_modules.timing.timing import RepeatedTimer
from AR_modules.timing.timing import AccelerometerRecorder
from AR_modules.octave.featureExtraction import FeatureExtraction

from AR_modules.config.general import FEATURES_PATH, MODELS_PATH, CLASSIFIER_NAME, CLASSIFIER_OPTIONS

if RASPI:
    from AR_modules.sensehat.RTIMULib import InitializeRTIMU
    from AR_modules.sensehat.displayLib import ShowInitialMsg
    from AR_modules.sensehat.displayLib import InitializeDisplay
    from AR_modules.sensehat.displayLib import stand_pixel_list, sit_pixel_list, walk_pixel_list
    from AR_modules.sensehat.displayLib import UP_list,SIT_list,PITCH_list,ROLL_list,YAW_list

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

print("\nargs:", flush=True)
print(args, flush=True)
if args.train_length_per_activity != None and args.train_length_per_activity[0] > 0:
        TRAIN = 1
        TRAINING_LENGTH_PER_ACTIVITY = int(args.train_length_per_activity[0])
    
debug = args.d

columns = defaultdict(list) # each value in each column is appended to a list

if RASPI:
    print("\n[InitializeRTIMU]", flush=True)
    
    SETTINGS_FILE = "RTIMULib"
    
    print("Using settings file " + SETTINGS_FILE + ".ini", flush=True)
    if not os.path.exists(SETTINGS_FILE + ".ini"):
       print("Settings file does not exist, will be created", flush=True)
    
    s = RTIMU.Settings(SETTINGS_FILE)
    imu = RTIMU.RTIMU(s)
    print("IMU Name: " + imu.IMUName(), flush=True)
    
    if (not imu.IMUInit()):
       print("IMU Init Failed", flush=True)
       sys.exit(1)
    else:
       print("IMU Init Succeeded", flush=True);
    
    imu.setAccelEnable(True)
    poll_interval = imu.IMUGetPollInterval()
    print("Recommended Poll Interval: %dmS\n" % poll_interval, flush=True)
else:
    imu = 0

recorder = AccelerometerRecorder(
    #150, # WINDOW_SIZE
    #100, # OVERLAP
    75, # WINDOW_SIZE
    50, # OVERLAP
    0.02, imu) # INTERVAL in secs == 20 ms

print("\n[ACTIVITY RECOGNIZER]\n", flush=True)

print("\t[TRAIN MODE][%d]" % TRAIN, flush=True))
if TRAIN:
    print ("\t[TRAIN LENGTH PER ACTIVITY][%d]" % TRAINING_LENGTH_PER_ACTIVITY, flush=True)

print ("\t[DEBUG MODE][%d]\n" % debug, flush=True)

recorder.printRecorderInfo()

def Recognize(model, test_data):
    global sense
    
    if debug:
        print("\n[Recognize]\n", flush=True)
    
    for index, inst in enumerate(test_data):
        pred = model.classify_instance(inst)
        dist = model.distribution_for_instance(inst)
        print(
            str(index+1) + ": label index=" + str(pred) + 
            ", class distribution=" + str(dist) + 
            ", predicted=" +  inst.class_attribute.value(int(pred)) + 
            ", actual=" + inst.get_string_value(inst.class_index), flush=True)
        if RASPI:
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
               print("[RecordIntancesForClass][num_frames_recorded = " + str(num_frames_recorded) + "]", flush=True)
               print("[RecordIntancesForClass][timer.stop ()]", flush=True)
            break
        
        # consumer thread
        recorder.condition.acquire()
        while True:
            #... get item from resource
            recorder.count_lock.acquire()
            try:
                if recorder.item:
		    if debug:
                       print("[RecordIntancesForClass][NEW FRAME]", flush=True)
                
                    numerical_values = FeatureExtraction(recorder.AccXarray, recorder.AccYarray, recorder.AccZarray, 
							recorder.window_size, recorder.overlap, debug)
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

    print("\n[TRAINING NEW MODEL]", flush=True)
    print("\t[num_samples_per_frame = " + str(num_samples_per_frame) + "]", flush=True)
    print("\t[num_seconds_per_frame = " + str(num_seconds_per_frame) + "]", flush=True)
    print("\t[frames_per_activity = " + str(frames_per_activity) + "]", flush=True)
    
    [train_data, sample_instance] = InitNewDataset()
    target_attribute = train_data.attribute_by_name("activity")
    
    activities = target_attribute.values
    num_training_steps = target_attribute.num_values
    #print activities
        
    for step in range(0, num_training_steps):
    
        print("\n[TRAINING NEW MODEL][STEP " + str(step+1) + " OF " + str(num_training_steps) + "]", flush=True)
        print("[ACTIVITY][" + activities[step] + "]", flush=True)
        print("[press q to quit; press c to continue]", flush=True)
        quit=False
        # loop
        while quit !=True:
            c = getch()
            if (c == "q"):
                quit=True
            elif (c == "c"):
                print("\n[ACTIVITY RECORDING!!!]", flush=True)
                train_data = RecordIntancesForClass(train_data, sample_instance, step, frames_per_activity)
                
                print train_data
                break
        if quit:
            exit(0)
            
    train_data.class_is_last()
    
    # train classifier
    #classifier = Classifier("weka.classifiers.trees.RandomForest",  options=["-I","100","-K","0","-S","1"])
    classifier = Classifier(CLASSIFIER_NAME, options=[option for option in CLASSIFIER_OPTIONS])
        
    classifier.build_classifier(train_data)
    
    # save classifier object
    model_outfile = MODELS_PATH + "raspi_data_mfcc_plp_online_" + CLASSIFIER_NAME + ".model"
    
    print("\n[TrainNewModel][NEW MODEL][%s]\n" % model_outfile, flush=True)
    serialization.write(model_outfile, classifier)
    
    # save arff dataset
    arff_outfile = FEATURES_PATH + "raspi_training_data_mfcc_plp_online_" + datetime.now().strftime('%Y-%m-%d_%H:%M:%S') + ".arff"
    print("\n[TrainNewModel][NEW DATASET][%s]\n" % arff_outfile, flush=True)
    saver = Saver(classname="weka.core.converters.ArffSaver")
    saver.save_file(train_data, arff_outfile)
    
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
                    #print "[CONSUMIDOR][NEW FRAME]"
                    #print "ESTADO ARRAYS"
                    #print AccX_bufferArray
                    #print AccY_bufferArray
                    #print AccZ_bufferArray
                    #print recorder.AccXarray[150:199]
                    #print recorder.AccYarray[150:199]
                    #print recorder.AccZarray[150:199]

                    numerical_values = FeatureExtraction(recorder.AccXarray, recorder.AccYarray, recorder.AccZarray, 
                                                         recorder.window_size, recorder.overlap, debug)

                    test_data = LoadInstanceForRecognition(test_data, numerical_values)
                    #print test_data.get_instance(0)
                    
                    Recognize(model, test_data)
                                        
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
        #jvm.start(max_heap_size="1200m")
        #model = LoadClassifier("./models/online/P_data_mfcc_plp.model")
        #test_data = LoadDataset("./features/online/aux_features.arff")

        if RASPI:
	    #print "[InitializeRTIMU]"
            #imu = InitializeRTIMU()

#	    print("Using settings file " + SETTINGS_FILE + ".ini")
#            if not os.path.exists(SETTINGS_FILE + ".ini"):
#               print("Settings file does not exist, will be created")
#
#    	    s = RTIMU.Settings(SETTINGS_FILE)
#    	    imu = RTIMU.RTIMU(s)


#   	    print("IMU Name: " + imu.IMUName())

#    	    if (not imu.IMUInit()):
#        	print("IMU Init Failed")
#        	sys.exit(1)
#    	    else:
#        	print("IMU Init Succeeded");

#    	    imu.setAccelEnable(True)

#    	    poll_interval = imu.IMUGetPollInterval()
#    	    print("Recommended Poll Interval: %dmS\n" % poll_interval)
            #while(1):
 	    #   time.sleep(1)
	    #   if imu.IMURead():
            #      accelerometer_data = imu.getAccel()
	    #      x = accelerometer_data[0]
            #      y = accelerometer_data[1]
            #      z = accelerometer_data[2]
	    #      print x
            #      print y
	    #      print z
	    #exit(1)

	    print("[InitializeDisplay]", flush=True)
	    sense = InitializeDisplay()
            
        jvm.start(max_heap_size="1200m")
        
        if TRAIN:
            TrainNewModel(TRAINING_LENGTH_PER_ACTIVITY)
        
        model_filename = MODELS_PATH + "raspi_data_mfcc_plp_online_" + CLASSIFIER_NAME + ".model"
        model = LoadClassifier(model_filename)
        
        test_data = LoadDataset("./features/online/aux_features_raspi.arff")
        #model = LoadClassifier("./models/online/P_data_mfcc_plp.model")
        #test_data = LoadDataset("./features/online/aux_features.arff")
        
        main(model, test_data)
    except Exception, e:
        print(traceback.format_exc())
    finally:
        #timer.stop()
        jvm.stop()
        print("\nnum_mini_buffers_recorded = " + str(recorder.num_mini_buffers_recorded), flush=True)
        print("num_samples_recorded = " + str(recorder.num_samples_recorded), flush=True)
        exit(1)
