# -*- coding: utf-8 -*-
"""
Created on Fri Sep 29 12:32:01 2017

@author: ffm
"""

import numpy as np

from AR_modules.config.general import *

from oct2py import octave

if RASPI:
    octave_path = '/home/pi/H_SMARTPHONE_WATCH_FFM_LITE/scripts/octave/'
else:
    octave_path = '/home/ffm/workspace/H_SMARTPHONE_WATCH_FFM/scripts/octave/'

octave.addpath(octave_path)

if debug:
    print("[OCTAVE PATH][%s]" % octave_path) 

def FeatureExtraction(AccX_array, AccY_array, AccZ_array, window_size, overlap, debug):

    aux_AccX_array = AccX_array[np.newaxis, :].T
    aux_AccY_array = AccY_array[np.newaxis, :].T
    aux_AccZ_array = AccZ_array[np.newaxis, :].T
    
    #print(aux_AccX_array)
    #print(aux_AccY_array)
    #print(aux_AccZ_array)

    if debug:
        print("\n[FeatureExtraction]\n")
    
    result = octave.calcula_features_mfcc_plp_online(aux_AccX_array, aux_AccY_array, aux_AccZ_array, window_size, overlap, debug)
    #print result 
    
    return result
