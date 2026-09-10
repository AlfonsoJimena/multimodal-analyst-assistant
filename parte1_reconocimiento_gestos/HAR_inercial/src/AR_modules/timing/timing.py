# -*- coding: utf-8 -*-
"""
Created on Fri Sep 29 12:29:50 2017

@author: ffm
"""

from AR_modules.config.general import *
from AR_modules.config.general import debug

import time
import threading
import numpy as np

from threading import Event, Thread

class AccelerometerRecorder:
    # Constants    
    GRAVITY_ACCEL = 9.81

    # Parameters
    window_size = 0
    overlap = 0
    mini_buffer_size = 0    
    interval = 0
    
    # Accelerometer handle
    #imu = 0
    
    # Aux variables
    count_lock = threading.Lock()
    condition = threading.Condition() # represents the addition of an item to a resource
    
    num_mini_buffers_per_frame = 0
    num_mini_buffers = 0
    buffer_size = 0
    
    p_recording_buffer = 0
    p_item_in_recording_buffer = 0
    p_processing_buffer = 0
    
    num_mini_buffers_recorded = 0
    num_samples_recorded = 0
    
    count = 0
    item = 0

    AccX_bufferArray = 0 # np.zeros((NUM_MINI_BUFFERS, recorder.mini_buffer_size), dtype=np.float64)
    AccY_bufferArray = 0 # np.zeros((NUM_MINI_BUFFERS, recorder.mini_buffer_size), dtype=np.float64)
    AccZ_bufferArray = 0 # np.zeros((NUM_MINI_BUFFERS, recorder.mini_buffer_size), dtype=np.float64)
    
    AccXarray = 0
    AccYarray = 0
    AccZarray = 0
    
    def __init__(self, window_size, overlap, interval, imu, *args, **kwargs):
        self.window_size = window_size
        self.overlap = overlap
        self.mini_buffer_size = window_size - overlap
        self.interval = interval
        self.imu = imu
        
        if self.mini_buffer_size <= 0:
            print("\n[WRONG MINI-BUFFER SIZE (" + str(self.mini_buffer_size) + ")!!!]")
            print("[window_size = " + str(self.window_size) + "]")
            print("[overlap = " + str(self.overlap) + "]")
            exit(0)
            
        if self.window_size % self.mini_buffer_size != 0:
            print("\n[WRONG MINI-BUFFER SIZE (" + str(self.mini_buffer_size) + ")!!!]")
            print("[REMAINDER OF WINDOW SIZE / self.mini_buffer_size MUST BE ZERO (" + str(self.window_size) + " / " + str(self.mini_buffer_size) + "]\n")
            print("[PLEASE, RECONSIDER EITHER WINDOW SIZE OR THE OVERLAP VALUE]\n")
            exit(0)
        else:
            self.num_mini_buffers_per_frame = int(self.window_size / self.mini_buffer_size) + 1 # 1 EXTRA MINI_BUFFER FOR THE OVERLAP
            self.num_mini_buffers = self.num_mini_buffers_per_frame + 30 # ALWAYS ADD AN EXTRA MINI_BUFFER TO MATCH TIMING EXPECTATIONS; 1 MAY BE NOT ENOUGH TO AVOID EVENTUAL BLOCKS!!!!

        self.buffer_size = self.window_size + self.mini_buffer_size
        
        print("num buffers",self.num_mini_buffers)
        print("mini buffer size",self.mini_buffer_size)
        
        self.AccX_bufferArray = np.zeros((self.num_mini_buffers, self.mini_buffer_size),dtype=np.float64)
        self.AccY_bufferArray = np.zeros((self.num_mini_buffers, self.mini_buffer_size),dtype=np.float64)
        self.AccZ_bufferArray = np.zeros((self.num_mini_buffers, self.mini_buffer_size),dtype=np.float64)
        
        # These are the arrays that are ultimately passed to the feature extraction module
        # Size is defined to fit a frame
        
        self.AccXarray = np.zeros(self.buffer_size, dtype=np.float64)
        self.AccYarray = np.zeros(self.buffer_size, dtype=np.float64)
        self.AccZarray = np.zeros(self.buffer_size, dtype=np.float64)

    def printRecorderInfo(self):
        print("\t[GRAVITY_ACCEL = " + str(self.GRAVITY_ACCEL) + "]")
        print("\t[window_size = " + str(self.window_size) + "]")
        print("\t[overlap = " + str(self.overlap) + "]")
        print("\t[mini_buffer_size = " + str(self.mini_buffer_size) + "]")
        print("\t[buffer_size = " + str(self.buffer_size) + " (num_mini_buffers_per_frame = " + str(self.num_mini_buffers_per_frame) + ")]")
        print("\t[num_mini_buffers = " + str(self.num_mini_buffers) + "]\n")

    def ResetRecordingParameters(self):
        self.p_recording_buffer = 0
        self.p_item_in_recording_buffer = 0
        self.p_processing_buffer = 0
    
        self.num_mini_buffers_recorded = 0
        self.num_samples_recorded = 0
        
    def ReadAccelerometer (self):  
        global timer
        global sense
    
        self.count_lock.acquire()
        try:
            self.count = self.count + 1 # access shared resource
            
            self.num_samples_recorded = self.num_samples_recorded + 1
    
            #sense = SenseHat()
            #accelerometer_data = sense.get_accelerometer_raw()
            if RASPI:
                self.imu.IMURead()
                accelerometer_data = self.imu.getAccel()
                
                x = accelerometer_data[0] * self.GRAVITY_ACCEL
                y = accelerometer_data[1] * self.GRAVITY_ACCEL
                z = accelerometer_data[2] * self.GRAVITY_ACCEL
    
                if debug:            
                    if np.isnan(x) or np.isinf(x):
                        x = 0
                        print("\n[PROBLEMAS CON ACELEROMETROS!!!][x]\n")
                        print(accelerometer_data)
            
                    if np.isnan(y) or np.isinf(y):
                        y = 0
                        print("\n[PROBLEMAS CON ACELEROMETROS!!!][y]\n")
                        print(accelerometer_data)
            
                    if np.isnan(z) or np.isinf(z):
                        z = 0
                        print("\n[PROBLEMAS CON ACELEROMETROS!!!][z]\n")
                        print(accelerometer_data)
            else:
                x = self.count            
                y = self.count
                z = self.count
            
            self.AccX_bufferArray[self.p_recording_buffer, self.p_item_in_recording_buffer] = x
            self.AccY_bufferArray[self.p_recording_buffer, self.p_item_in_recording_buffer] = y
            self.AccZ_bufferArray[self.p_recording_buffer, self.p_item_in_recording_buffer] = z
            
            #print AccX_bufferArray
    
            self.p_item_in_recording_buffer = self.p_item_in_recording_buffer + 1
            
            if self.p_item_in_recording_buffer >= self.mini_buffer_size:
                # Se ha agotado el buffer actual...
    
                # se incrementa el numero de buffers grabados ...
                self.num_mini_buffers_recorded = self.num_mini_buffers_recorded + 1
    
                # y pasamos al siguiente buffer
                self.p_item_in_recording_buffer = 0
                self.p_recording_buffer = self.p_recording_buffer + 1
            
                # buffer grande circular a partir de mini-buffers: si se agota el ultimo mini-buffer volvemos a usar el primero
                if self.p_recording_buffer >= self.num_mini_buffers:
                    self.p_recording_buffer = 0
    
                if debug:
                    print("KKKKKKKKKKKKKKKKKKKKKKKKK")
                    print("[num_mini_buffers_recorded][" + str(self.num_mini_buffers_recorded) + "]")
                    print("[p_recording_buffer][" + str(self.p_recording_buffer) + "]\n")
    
                if self.p_recording_buffer == self.p_processing_buffer:
                    print("\n[ReadAccelerometer][FATAL ERROR!!!]\n")
                    exit(0)
                
                if self.num_samples_recorded >= self.buffer_size:                
                    # producer thread
                    #... generate item
                    self.condition.acquire()
                    #... add item to resource
                    self.item = 1
       
                    # Copiamos los mini-buffers correspondientes en el buffer grande
                    p_aux_item = 0
                    for value in range(0, self.num_mini_buffers_per_frame):
                        p_aux_buffer = self.p_processing_buffer+value
                        if p_aux_buffer >= self.num_mini_buffers:
                            p_aux_buffer = self.p_processing_buffer+value-self.num_mini_buffers
                        
                        self.AccXarray[p_aux_item:p_aux_item+self.mini_buffer_size] = self.AccX_bufferArray[p_aux_buffer, :]
                        self.AccYarray[p_aux_item:p_aux_item+self.mini_buffer_size] = self.AccY_bufferArray[p_aux_buffer, :]
                        self.AccZarray[p_aux_item:p_aux_item+self.mini_buffer_size] = self.AccZ_bufferArray[p_aux_buffer, :]
       
    
                        p_aux_item = p_aux_item+self.mini_buffer_size
                    
                    if debug:
                        print(self.AccXarray)
    
                    self.p_processing_buffer = self.p_processing_buffer + 1
    
                    if self.p_processing_buffer >= self.num_mini_buffers:
                        self.p_processing_buffer = 0
                    
                    self.condition.notify() # signal that a new item is available
                    self.condition.release()
            if debug:
                print("[p_processing_buffer][" + str(self.p_processing_buffer) + "]\n")
    
        finally:
            self.count_lock.release() # release lock, no matter what

        
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
        print("\n[STOP PERIODICAL TASK]\n")
