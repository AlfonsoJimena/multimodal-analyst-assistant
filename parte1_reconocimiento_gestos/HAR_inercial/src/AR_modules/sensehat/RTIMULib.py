# -*- coding: utf-8 -*-
"""
Created on Fri Sep 29 10:54:47 2017

@author: ffm
"""
import sys, getopt

#sys.path.append('.')

import RTIMU
import os.path


#SETTINGS_FILE = "RTIMULib"

def InitializeRTIMU():
    SETTINGS_FILE = "RTIMULib"

    #sys.path.append('.')

    print("Using settings file " + SETTINGS_FILE + ".ini")
    if not os.path.exists(SETTINGS_FILE + ".ini"):
        print("Settings file does not exist, will be created")

    s = RTIMU.Settings(SETTINGS_FILE)
    imu = RTIMU.RTIMU(s)
    #pressure = RTIMU.RTPressure(s)
    #humidity = RTIMU.RTHumidity(s)

    print("IMU Name: " + imu.IMUName())

    if (not imu.IMUInit()):
        print("IMU Init Failed")
        sys.exit(1)
    else:
        print("IMU Init Succeeded");


    imu.setAccelEnable(True)

    poll_interval = imu.IMUGetPollInterval()
    print("Recommended Poll Interval: %dmS\n" % poll_interval)

    return imu
