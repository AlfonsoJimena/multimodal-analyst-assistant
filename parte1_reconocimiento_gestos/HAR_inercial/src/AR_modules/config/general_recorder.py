# -*- coding: utf-8 -*-
"""
Created on Fri Sep 13 2023

@author: ffm
"""

RASPI = 1
debug = 0

# Number of recorded instances per activity
#TRAINING_LENGTH_PER_ACTIVITY=4
TRAINING_LENGTH_PER_ACTIVITY=30

# Directorio donde guardamos los datos del recorder
DATA_PATH="/home/pi/workspace/HAR_inercial/data/raw_data/"

# Number of users to be recorded
NUM_USERS=1

# Name or identifier for each specific action to be recorded separated by _
# Activities are recorded in the same order they are specified
DATA_SET="DRIVE_BACKHAND_SERVE_LOB"

#DATA_SET="UP_SIT_PITCH_ROLL_YAW.arff"
#DATA_SET="RUNNING_STEP_SQUAT_CIRCLES"
#DATA_SET="SHAKE_CIRCLES_TILT"
#DATA_SET="TRIANGLE_CIRCLE_SQUARE_RHOMBUS_PENTAGON.arff"

#RAW_DATA_PATH="/home/pi/H_SMARTPHONE_WATCH_FFM_LITE/scripts/raw_data/online/"
#RAW_DATA_PATH="/var/activityRecognizer/" # CUIDADO!!! UBICACION EN RAM!!! LIMITE 100MB!!! VOLATILIDAD POR REBOOT!!!
