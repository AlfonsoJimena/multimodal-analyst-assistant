# -*- coding: utf-8 -*-
"""
Created on Wed Sep 13 2023

@author: ffm
"""

RASPI = 1
debug = 0

# Folder where we can find the models
MODELS_PATH="/home/pi/workspace/HAR_inercial/models/"

# Model name (root filename preceding your .h5 and .json files)
MODEL_NAME="DRIVE_BACKHAND_SERVE_LOB-LSTM_from_raw"

# Ordered list of defined classes
CLASSES = "DRIVE_BACKHAND_SERVE_LOB"
#CLASSES="UP_SIT_PITCH_ROLL_YAW"
#CLASSES="RUN_STEP_SQUAT_CIRCLES"
#CLASSES="SHAKE_CIRCLES_TILT"
#CLASSES="TRIANGLE_CIRCLE_SQUARE_RHOMBUS_PENTAGON"

#RAW_DATA_PATH="/home/pi/H_SMARTPHONE_WATCH_FFM_LITE/scripts/raw_data/online/"
#RAW_DATA_PATH="/var/activityRecognizer/" # CUIDADO!!! UBICACION EN RAM!!! LIMITE 100MB!!! VOLATILIDAD POR REBOOT!!!
