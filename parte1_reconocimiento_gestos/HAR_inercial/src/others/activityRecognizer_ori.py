#!/usr/bin/python

import sys, getopt

sys.path.append('.')
import RTIMU
import os.path
import time
import math

import sys, tty, termios

# The getch method can determine which key has been pressed
# by the user on the keyboard by accessing the system files
# It will then return the pressed key as a variable
def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

SETTINGS_FILE = "RTIMULib"

print("Using settings file " + SETTINGS_FILE + ".ini")
if not os.path.exists(SETTINGS_FILE + ".ini"):
  print("Settings file does not exist, will be created")

s = RTIMU.Settings(SETTINGS_FILE)
imu = RTIMU.RTIMU(s)
pressure = RTIMU.RTPressure(s)
humidity = RTIMU.RTHumidity(s)

print("IMU Name: " + imu.IMUName())

if (not imu.IMUInit()):
    print("IMU Init Failed")
    sys.exit(1)
else:
    print("IMU Init Succeeded");


imu.setAccelEnable(True)

poll_interval = imu.IMUGetPollInterval()
print("Recommended Poll Interval: %dmS\n" % poll_interval)

import threading
import traceback
import time
import numpy as np
#import javabridge

import weka.core.jvm as jvm
from weka.core.converters import Loader
from weka.core.dataset import Instances
from weka.classifiers import Classifier
from weka.core.dataset import Instance
import weka.core.serialization as serialization

from oct2py import octave
octave.addpath('/home/pi/H_SMARTPHONE_WATCH_FFM_LITE/scripts/octave/')

import csv
from collections import defaultdict

import math

RASPI = 1
debug = 0

if RASPI:
    from sense_hat import SenseHat
    sense = SenseHat()

N = [0,0,0] # Black
R = [255,0,0] # Red
W = [255,255,255] # White
G = [0,255,0] # Green
B = [0,0,255] # Blue

pixel_list = [
        N,N,N,N,N,N,N,N,
        N,W,W,N,N,W,W,N,
        N,W,W,N,N,W,W,N,
        N,N,N,N,N,N,N,N,
        W,N,N,N,N,N,N,W,
        N,W,N,N,N,N,W,N,
        N,N,W,W,W,W,N,N,
        N,N,N,N,N,N,N,N]

W = N

stand_pixel_list = [
        W,W,W,W,G,W,W,W,
        W,W,W,W,G,G,W,W,
        W,G,G,G,G,G,G,W,
        W,G,G,G,G,G,G,G,
        W,G,G,G,G,G,G,W,
        W,W,W,W,G,G,W,W,
        W,W,W,W,G,W,W,W,
        W,W,W,W,W,W,W,W]

sit_pixel_list = [
        W,W,W,W,R,W,W,W,
        W,W,W,R,R,R,W,W,
        W,W,R,R,R,R,R,W,
        W,R,R,R,R,R,R,R,
        W,W,W,R,R,R,W,W,
        W,W,W,R,R,R,W,W,
        W,W,W,R,R,R,W,W,
        W,W,W,R,R,R,W,W]

walk_pixel_list = [
        W,W,W,B,B,W,W,W,
        W,W,B,W,W,B,W,W,
        W,B,W,W,W,W,B,W,
        B,W,W,B,B,W,W,B,
        B,W,W,B,B,W,W,B,
        W,B,W,W,W,W,B,W,
        W,W,B,W,W,B,W,W,
        W,W,W,B,B,W,W,W]

W = [255,255,255] # White

columns = defaultdict(list) # each value in each column is appended to a list

item = 0
value = 0
stop = 0
count = 0

GRAVITY_ACCEL = 9.81

WINDOW_SIZE = 150
OVERLAP = 100
MINI_BUFFER_SIZE = WINDOW_SIZE - OVERLAP

print "\n[ACTIVITY RECOGNIZER]\n"
print "\t[WINDOW_SIZE = " + str(WINDOW_SIZE) + "]"
print "\t[OVERLAP = " + str(OVERLAP) + "]"
print "\t[MINI_BUFFER_SIZE = " + str(MINI_BUFFER_SIZE) + "]"

if MINI_BUFFER_SIZE <= 0:
    print "\n[WRONG MINI-BUFFER SIZE (" + str(MINI_BUFFER_SIZE) + ")!!!][WINDOW SIZE = " + str(WINDOW_SIZE) + "][OVERLAP = " + str(OVERLAP) + "]\n"
    exit(0)

if WINDOW_SIZE % MINI_BUFFER_SIZE != 0:
    print "\n[WRONG MINI-BUFFER SIZE (" + str(MINI_BUFFER_SIZE) + ")!!!]"
    print "[REMAINDER OF WINDOW SIZE / MINI_BUFFER_SIZE MUST BE ZERO (" + str(WINDOW_SIZE) + " / " + str(MINI_BUFFER_SIZE) + "]\n"
    print "[PLEASE, RECONSIDER EITHER WINDOW SIZE OR THE OVERLAP VALUE]\n"
    exit(0)
else:
    NUM_MINI_BUFFERS_PER_FRAME = (WINDOW_SIZE / MINI_BUFFER_SIZE) + 1 # 1 EXTRA MINI_BUFFER FOR THE OVERLAP
    NUM_MINI_BUFFERS = NUM_MINI_BUFFERS_PER_FRAME + 1 # ALWAYS ADD AN EXTRA MINI_BUFFER TO MATCH TIMING EXPECTATIONS

BUFFER_SIZE = WINDOW_SIZE + MINI_BUFFER_SIZE

print "\t[BUFFER_SIZE = " + str(BUFFER_SIZE) + " (" + str(NUM_MINI_BUFFERS_PER_FRAME) + " MINI_BUFFERS)]\n"
print "\t[NUM MINI BUFFERS = " + str(NUM_MINI_BUFFERS) + "]"

#WINDOW_SIZE = 4
#MAX_ITEMS_BUFFER = 2

#NUM_BUFFERS_WINDOW = 4

#if NUM_BUFFERS_WINDOW > NUM_BUFFERS:
#    print "\n[ERROR!!!][NUM_BUFFERS_WINDOW (" + str(NUM_BUFFERS_WINDOW) + ") > NUM_BUFFERS (" + str(NUM_BUFFERS) + ")!!!]\n"
#    exit(0)

#AccX_bufferArray = np.zeros((NUM_BUFFERS, MAX_ITEMS_BUFFER), dtype=float)
#AccY_bufferArray = np.zeros((NUM_BUFFERS, MAX_ITEMS_BUFFER), dtype=float)
#AccZ_bufferArray = np.zeros((NUM_BUFFERS, MAX_ITEMS_BUFFER), dtype=float)

AccX_bufferArray = np.zeros((NUM_MINI_BUFFERS, MINI_BUFFER_SIZE), dtype=np.float64)
AccY_bufferArray = np.zeros((NUM_MINI_BUFFERS, MINI_BUFFER_SIZE), dtype=np.float64)
AccZ_bufferArray = np.zeros((NUM_MINI_BUFFERS, MINI_BUFFER_SIZE), dtype=np.float64)

#AccXarray = np.zeros(WINDOW_SIZE, dtype=float)
#AccYarray = np.zeros(WINDOW_SIZE, dtype=float)
#AccZarray = np.zeros(WINDOW_SIZE, dtype=float)

AccXarray = np.zeros(BUFFER_SIZE, dtype=np.float64)
AccYarray = np.zeros(BUFFER_SIZE, dtype=np.float64)
AccZarray = np.zeros(BUFFER_SIZE, dtype=np.float64)

p_recording_buffer = 0
p_item_in_recording_buffer = 0
p_processing_buffer = 0

num_mini_buffers_recorded = 0
num_samples_recorded = 0

stop_lock = threading.Lock()
count_lock = threading.Lock()

# represents the addition of an item to a resource
condition = threading.Condition()

def TrainModel():
    # load a dataset
    #iris_file = helper.get_data_dir() + os.sep + "iris.arff"
    train_file = "./features/TOTAL_A_P.arff"
    print("Loading dataset: " + train_file)
    loader = Loader("weka.core.converters.ArffLoader")
    train_data = loader.load_file(train_file)
    train_data.class_is_last()
    
    # train classifier
    classifier = Classifier("weka.classifiers.trees.RandomForest",  options=["-I","100","-K","0","-S","1"])
    classifier.build_classifier(train_data)
    
    # save classifier object
    print("\n[TrainModel]\n\n")
    #outfile = tempfile.gettempdir() + os.sep + "j48.model"
    outfile ="./models/online/P_data_mfcc_plp.model"
    serialization.write(outfile, classifier)

def FeatureExtraction(AccX_array, AccY_array, AccZ_array):

    aux_AccX_array = AccX_array[np.newaxis, :].T
    aux_AccY_array = AccY_array[np.newaxis, :].T
    aux_AccZ_array = AccZ_array[np.newaxis, :].T
    
    #print(aux_AccX_array)
    #print(aux_AccY_array)
    #print(aux_AccZ_array)

    if debug:
        print("\n[FeatureExtraction]\n")
    result = octave.calcula_features_mfcc_plp_online(aux_AccX_array, aux_AccY_array, aux_AccZ_array)
    #print result 
    
    return result
    
def LoadClassifier(classifier_file):
    print("\n[LoadClassifier][" + classifier_file + "]\n")

    # read classifier object    
    model = Classifier(jobject=serialization.read(classifier_file))
    
    print(model)

    return model

def LoadDataset(dataset_file):
    print("\n[LoadDataset]\ninput file = " + dataset_file + "\n")
    loader = Loader("weka.core.converters.ArffLoader")
    dataset = loader.load_file(dataset_file)
    dataset.class_is_last()
    
    return dataset

def InitNewDataset():
    aux_dataset = LoadDataset("./features/online/aux_features_raspi.arff")
    sample_instance = aux_dataset.get_instance(0)
    new_dataset = aux_dataset
    new_dataset.delete()
    return [new_dataset, sample_instance]
                        
def LoadInstanceForTraining(dataset, sample_instance, numerical_values, p_class):
    
    inst = sample_instance
    num_attributes = len(numerical_values);
    for index in range(0, num_attributes):
        inst.set_value(index, numerical_values[0,index])

    target_attribute = dataset.attribute_by_name("activity") 
    
    #print "target_attribute.index = " + str(target_attribute.index)
    #print "dataset.class_index = " + str(dataset.class_index)
    #print target_attribute.values
    #inst.set_value(target_attribute.index, float(target_attribute.values.index(3)))
    inst.set_value(target_attribute.index, float(p_class))
    dataset.add_instance(inst)
    #print inst
    num_instances = dataset.num_instances
    print "[LoadInstanceForTraining][num_instances = " + str(num_instances) + "]"
                
    return dataset
    
def LoadInstanceForRecognition(dataset, numerical_values):
    inst = dataset.get_instance(0)
    num_attributes = len(numerical_values);
    for index in range(0, num_attributes):
        inst.set_value(index, numerical_values[0,index])
    dataset.set_instance(0, inst)
                    
    return dataset
    
def Recognize(model, test_data):
    print("\n[Recognize]\n")
    
    for index, inst in enumerate(test_data):
	pred = model.classify_instance(inst)
	dist = model.distribution_for_instance(inst)
	print(
	   str(index+1) + ": label index=" + str(pred) + 
            ", class distribution=" + str(dist) + 
            ", predicted=" +  inst.class_attribute.value(int(pred)) + 
            ", actual=" + inst.get_string_value(inst.class_index))
	if int(pred) == 0:
	   sense.set_pixels(stand_pixel_list)
	elif int(pred) == 1:
	   sense.set_pixels(sit_pixel_list)
	else:
	   sense.set_pixels(walk_pixel_list)
    
def do_every (interval, worker_func, iterations = 0):
    global stop
    #print(stop)
    if stop == 0:
        if iterations != 1:
            timer = threading.Timer (
                interval,
                do_every, 
                [interval, worker_func, 0 if iterations == 0 else iterations-1]
                ).start ()
        worker_func ()
    else:
        print "\n[STOP PERIODICAL TASK]\n"
    

def print_hw ():
  print "hello world"

def print_so ():
  print "stackoverflow"
  
def ReadAccelerometer ():
    global AccX_bufferArray
    global AccY_bufferArray
    global AccZ_bufferArray    
    global AccXarray
    global AccYarray
    global AccZarray
    global p_recording_buffer
    global p_item_in_recording_buffer
    global count
    global item
    global num_mini_buffers_recorded
    global num_samples_recorded
    global p_processing_buffer
    global timer
    global sense

    count_lock.acquire()
    try:
        count = count + 1 # access shared resource
        
        num_samples_recorded = num_samples_recorded + 1

        #sense = SenseHat()
        #accelerometer_data = sense.get_accelerometer_raw()
        imu.IMURead()
	accelerometer_data = imu.getAccel()
        x = accelerometer_data[0]
        y = accelerometer_data[1]
        z = accelerometer_data[2]

        if np.isnan(x) or np.isinf(x):
	    x = 0
	    #print "\n[PROBLEMAS CON ACELEROMETROS!!!][x]\n"
	    #print accelerometer_data

	if np.isnan(y) or np.isinf(y):
            y = 0
            #print "\n[PROBLEMAS CON ACELEROMETROS!!!][y]\n"
	    #print accelerometer_data

	if np.isnan(z):
            z = 0
            #print "\n[PROBLEMAS CON ACELEROMETROS!!!][z]\n"
	    #print accelerometer_data

        #print "x=" + str(x)
        #print "y=" + str(y)
        #print accelerometer_data

        if RASPI == 0:
            x = count            
            y = count
            z = count

        AccX_bufferArray[p_recording_buffer, p_item_in_recording_buffer] = x * GRAVITY_ACCEL
        AccY_bufferArray[p_recording_buffer, p_item_in_recording_buffer] = y * GRAVITY_ACCEL
        AccZ_bufferArray[p_recording_buffer, p_item_in_recording_buffer] = z * GRAVITY_ACCEL
        
        #print AccX_bufferArray

        p_item_in_recording_buffer = p_item_in_recording_buffer + 1
        
        if p_item_in_recording_buffer >= MINI_BUFFER_SIZE:
            # Se ha agotado el buffer actual...

            # se incrementa el numero de buffers grabados ...
            num_mini_buffers_recorded = num_mini_buffers_recorded + 1

            # y pasamos al siguiente buffer
            p_item_in_recording_buffer = 0
            p_recording_buffer = p_recording_buffer + 1
        
            # buffer grande circular a partir de mini-buffers: si se agota el ultimo mini-buffer volvemos a usar el primero
            if p_recording_buffer >= NUM_MINI_BUFFERS:
                p_recording_buffer = 0

	    if debug:
	        print "[num_mini_buffers_recorded][" + str(num_mini_buffers_recorded) + "]"
	        print "[p_recording_buffer][" + str(p_recording_buffer) + "]\n"

	    if p_recording_buffer == p_processing_buffer:
	        print "\n[ReadAccelerometer][FATAL ERROR!!!]\n"
	        exit(0)
            
            if num_samples_recorded >= BUFFER_SIZE:                
                # producer thread
                #... generate item
                condition.acquire()
                #... add item to resource
                item = 1
                value = 1
   
                # Copiamos los mini-buffers correspondientes en el buffer grande
                p_aux_item = 0
                for value in range(0, NUM_MINI_BUFFERS_PER_FRAME):
                    p_aux_buffer = p_processing_buffer+value
                    if p_aux_buffer >= NUM_MINI_BUFFERS:
                        p_aux_buffer = p_processing_buffer+value-NUM_MINI_BUFFERS
                    
                    AccXarray[p_aux_item:p_aux_item+MINI_BUFFER_SIZE] = AccX_bufferArray[p_aux_buffer, :]
                    AccYarray[p_aux_item:p_aux_item+MINI_BUFFER_SIZE] = AccY_bufferArray[p_aux_buffer, :]
                    AccZarray[p_aux_item:p_aux_item+MINI_BUFFER_SIZE] = AccZ_bufferArray[p_aux_buffer, :]

		    #print AccXarray

                    p_aux_item = p_aux_item+MINI_BUFFER_SIZE

                p_processing_buffer = p_processing_buffer + 1

                if p_processing_buffer >= NUM_MINI_BUFFERS:
                    p_processing_buffer = 0
                
                condition.notify() # signal that a new item is available
                condition.release()

	    if debug:
	        print "[p_processing_buffer][" + str(p_processing_buffer) + "]\n"

    finally:
        count_lock.release() # release lock, no matter what

    #timer.run ()

interval = 0.02 # in secs == 20 ms
#timer = threading.Timer (interval, ReadAccelerometer)

import time
from threading import Event, Thread

class RepeatedTimer:

    """Repeat `function` every `interval` seconds."""

    def __init__(self, interval, function, *args, **kwargs):
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.start = time.time()
        self.event = Event()
        self.thread = Thread(target=self._target)
        self.thread.start()

    def _target(self):
        while not self.event.wait(self._time):
            self.function(*self.args, **self.kwargs)

    @property
    def _time(self):
        return self.interval - ((time.time() - self.start) % self.interval)

    def stop(self):
        self.event.set()
        self.thread.join()

def ResetRecordingParameters():
    global p_recording_buffer
    global p_item_in_recording_buffer
    global p_processing_buffer
    global num_mini_buffers_recorded
    global num_samples_recorded

    p_recording_buffer = 0
    p_item_in_recording_buffer = 0
    p_processing_buffer = 0

    num_mini_buffers_recorded = 0
    num_samples_recorded = 0

def RecordIntancesForClass(dataset, sample_instance, training_step, num_frames_to_record):
    global item
    item = 0

    ResetRecordingParameters()
    
    timer = RepeatedTimer(0.02, ReadAccelerometer) 
    num_frames_recorded = 0
    while(1):
        if (num_frames_recorded >= num_frames_to_record):
            timer.stop ()
            print "[RecordIntancesForClass][num_frames_recorded = " + str(num_frames_recorded) + "]"
            print "[RecordIntancesForClass][timer.stop ()]"
            break
        
        # consumer thread
        condition.acquire()
        while True:
            #... get item from resource
            count_lock.acquire()
            try:
                if item:
                    print "[RecordIntancesForClass][NEW FRAME]"
                
                    numerical_values = FeatureExtraction(AccXarray, AccYarray, AccZarray)
                    dataset = LoadInstanceForTraining(dataset, sample_instance, numerical_values, training_step)
                    #print dataset
                    
                    num_frames_recorded = num_frames_recorded + 1
                    
                    item = 0
                    break
            finally:
                count_lock.release() # release lock, no matter what
            
            condition.wait() # sleep until item becomes available
        condition.release()
        #... process item
        value = 0
    return dataset

def TrainNewModel(outfile, seconds_per_activity):
       
    #seconds_per_activity = 30
    num_samples_per_frame = (WINDOW_SIZE - OVERLAP) # every "num_samples_per_frame" samples we have a new frame
    num_seconds_per_frame = interval*num_samples_per_frame # we take one sample per "interval" seconds
    frames_per_activity = round(seconds_per_activity / num_seconds_per_frame)
    
    print "frames_per_activity = " + str(frames_per_activity)
    [train_data, sample_instance] = InitNewDataset()
    target_attribute = train_data.attribute_by_name("activity")
    
    activities = target_attribute.values
    num_training_steps = target_attribute.num_values
    #print activities
        
    for step in range(0, num_training_steps):
    
        print "\n[TRAINING NEW MODEL][STEP " + str(step+1) + " OF " + str(num_training_steps) + "]"
        print "[ACTIVITY][" + activities[step] + "]"
        print "[press q to quit; press c to continue]"
        quit=False
        # loop
        while quit !=True:
            c = getch()
            if (c == "q"):
                quit=True
            elif (c == "c"):
                print "\n[ACTIVITY RECORDING!!!]"
                train_data = RecordIntancesForClass(train_data, sample_instance, step, frames_per_activity)
                
                print train_data
                break
        if quit:
            exit(0)
            
    train_data.class_is_last()
    
    # train classifier
    classifier = Classifier("weka.classifiers.trees.RandomForest",  options=["-I","100","-K","0","-S","1"])
    classifier.build_classifier(train_data)
    
    # save classifier object
    print("\n[TrainNewModel][outfile]\n")    
    serialization.write(outfile, classifier)
 
def main(model, test_data):
    global stop
    global AccX_bufferArray
    global AccY_bufferArray
    global AccZ_bufferArray
    global AccXarray
    global AccYarray
    global AccZarray    
    global p_recording_buffer
    global p_item_in_recording_buffer
    global count
    global item
    global num_mini_buffers_recorded
    global num_samples_recorded
    global p_processing_buffer
    global timer
    
    # call print_so every second, 5 times total
    #do_every (1, print_so, 5)
    #demoArray = np.array([[1, 2, 3],[4,5,6],[7,8,9]], dtype=float)
    #sense.flip_v()
    sense.set_rotation(180)
    sense.set_pixels(pixel_list)
    time.sleep(1)
    sense.show_message("3... 2... 1...", text_colour=W, scroll_speed=0.05)
    sense.show_message("GO!!!", text_colour=R, scroll_speed=0.05)
    #sense.flip_v()
    sense.set_rotation(0)

    stop_lock.acquire()
    try:
        stop = 0 # access shared resource
    finally:
        stop_lock.release() # release lock, no matter what
    
    count_lock.acquire()
    try:
        count = 0 # access shared resource
    finally:
        count_lock.release() # release lock, no matter what
        
    item = 0
    # call print_hw two times per second, forever
    #do_every (0.02, ReadAccelerometer)
    #do_every (1, ReadAccelerometer)
    #timer.start ()
    timer = RepeatedTimer(0.02, ReadAccelerometer)
            
    while(1):
        # consumer thread
        condition.acquire()
        while True:
            #... get item from resource
            count_lock.acquire()
            try:
                if item:
                    #print "[CONSUMIDOR][NEW FRAME]"
                    #print "ESTADO ARRAYS"
                    #print AccX_bufferArray
                    #print AccY_bufferArray
                    #print AccZ_bufferArray
                    #print AccXarray[150:199]
                    #print AccYarray[150:199]
		    #print AccZarray[150:199]

                    numerical_values = FeatureExtraction(AccXarray, AccYarray, AccZarray)

                    test_data = LoadInstanceForRecognition(test_data, numerical_values)
                    #print test_data.get_instance(0)
                    
                    Recognize(model, test_data)
                                        
                    item = 0
                    break
            finally:
                count_lock.release() # release lock, no matter what
                
            condition.wait() # sleep until item becomes available
        condition.release()
        #... process item
        value = 0

#    while(1):
#        time.sleep(1)
#        print "."

if __name__ == "__main__":
    try:
        #jvm.start(max_heap_size="1200m")
        #model = LoadClassifier("./models/online/P_data_mfcc_plp.model")
        #test_data = LoadDataset("./features/online/aux_features.arff")

        #if RASPI:
        #sense = SenseHat()
        #accelerometer_data = sense.get_accelerometer_raw()

        #x = accelerometer_data['x']
        #y = accelerometer_data['y']
        #z = accelerometer_data['z']

        #print "x=" + str(x)
        #print "y=" + str(y)
        #print accelerometer_data
    
        jvm.start(max_heap_size="1200m")
	#TrainNewModel("./models/online/raspi_data_mfcc_plp_online.model", 45)
	model = LoadClassifier("./models/online/raspi_data_mfcc_plp_online.model")
        test_data = LoadDataset("./features/online/aux_features_raspi.arff")
        #model = LoadClassifier("./models/online/P_data_mfcc_plp.model")
        #test_data = LoadDataset("./features/online/aux_features.arff")
        
        main(model, test_data)
    except Exception, e:
        print(traceback.format_exc())
    finally:
        timer.stop()
        jvm.stop()
        print("\nnum_mini_buffers_recorded = " + str(num_mini_buffers_recorded) + "\nnum_samples_recorded = " + str(num_samples_recorded) + "\n")
        stop_lock.acquire()
        try:
            stop = 1 # access shared resource
        finally:
            stop_lock.release() # release lock, no matter what
        
        #timer.cancel()
        #timer.join() 
        exit(1)
