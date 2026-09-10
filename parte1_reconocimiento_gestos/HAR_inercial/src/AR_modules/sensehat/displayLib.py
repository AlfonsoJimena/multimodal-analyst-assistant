# -*- coding: utf-8 -*-
"""
Created on Fri Sep 29 13:04:03 2017

@author: ffm
"""

import time

from sense_hat import SenseHat

def InitializeDisplay():
    sense = SenseHat()
    return sense
    
def ShowInitialMsg(sense):
    #sense.flip_v()
    sense.set_rotation(180)
    sense.set_pixels(pixel_list)
    time.sleep(1)
    sense.show_message("3... 2... 1...", text_colour=W, scroll_speed=0.05)
    sense.show_message("GO!!!", text_colour=R, scroll_speed=0.05)
    #sense.flip_v()
    sense.set_rotation(0)
        

N = [0,0,0] # Black
R = [255,0,0] # Red
W = [255,255,255] # White
G = [0,255,0] # Green
B = [0,0,255] # Blue
V = [255,0,255] # Purple
Y = [255,255,0] # Yellow

colour_array = [R,W,G,B,V,Y]

RECORDING = [
	N,N,N,N,N,N,N,N,
	N,N,N,N,N,N,N,N,
	N,N,N,R,R,N,N,N,
	N,N,R,R,R,R,N,N,
	N,N,R,R,R,R,N,N,
	N,N,N,R,R,N,N,N,
	N,N,N,N,N,N,N,N,
	N,N,N,N,N,N,N,N]

OFF = [
	N,N,N,N,N,N,N,N,
	N,N,N,N,N,N,N,N,
	N,N,N,N,N,N,N,N,
	N,N,N,N,N,N,N,N,
	N,N,N,N,N,N,N,N,
	N,N,N,N,N,N,N,N,
	N,N,N,N,N,N,N,N,
	N,N,N,N,N,N,N,N]
 
UP_list = [
	W,W,W,W,N,N,N,N,
	W,N,N,N,N,G,N,N,
	W,W,W,W,N,G,G,N,
	N,N,G,G,G,G,G,G,
	W,W,W,W,N,G,G,N,
	N,W,N,W,N,G,N,N,
	N,N,W,N,N,N,N,N,
	N,N,N,N,N,N,N,N]

SIT_list = [
	N,R,N,N,R,N,R,R,
	N,R,N,N,R,N,R,N,
	N,R,N,N,R,N,R,R,
	N,R,N,N,R,N,N,R,
	R,R,R,N,N,N,R,R,
	N,N,N,N,R,N,N,N,
	N,N,N,R,R,R,N,N,
	N,N,N,N,R,N,N,N]

PITCH_list = [
	N,N,N,N,N,N,N,N,
	V,V,V,V,V,V,V,N,
	V,V,V,V,V,V,V,N,
	N,N,N,V,N,N,V,N,
	N,N,N,V,N,N,V,N,
	N,N,N,V,V,V,V,N,
	N,N,N,N,V,V,N,N,
	N,N,N,N,N,N,N,N]

ROLL_list = [
	N,N,N,N,N,N,N,N,
	B,B,B,B,B,B,B,N,
	B,B,B,B,B,B,B,N,
	N,N,N,B,N,N,B,N,
	N,N,N,B,N,N,B,N,
	B,B,B,B,B,B,B,N,
	B,B,B,N,B,B,N,N,
	N,N,N,N,N,N,N,N]

YAW_list = [
	N,N,N,N,N,N,N,N,
	N,N,N,Y,Y,Y,Y,N,
	N,N,Y,Y,Y,Y,Y,N,
	Y,Y,Y,Y,N,N,N,N,
	Y,Y,Y,Y,N,N,N,N,
	N,N,Y,Y,Y,Y,Y,N,
	N,N,N,Y,Y,Y,Y,N,
	N,N,N,N,N,N,N,N]

pixel_list = [
        N,N,N,N,N,N,N,N,
        N,W,W,N,N,W,W,N,
        N,W,W,N,N,W,W,N,
        N,N,N,N,N,N,N,N,
        W,N,N,N,N,N,N,W,
        N,W,N,N,N,N,W,N,
        N,N,W,W,W,W,N,N,
        N,N,N,N,N,N,N,N]

stand_pixel_list = [
        N,N,N,N,G,N,N,N,
        N,N,N,N,G,G,N,N,
        N,G,G,G,G,G,G,N,
        N,G,G,G,G,G,G,G,
        N,G,G,G,G,G,G,N,
        N,N,N,N,G,G,N,N,
        N,N,N,N,G,N,N,N,
        N,N,N,N,N,N,N,N]

sit_pixel_list = [
        N,N,N,N,R,N,N,N,
        N,N,N,R,R,R,N,N,
        N,N,R,R,R,R,R,N,
        N,R,R,R,R,R,R,R,
        N,N,N,R,R,R,N,N,
        N,N,N,R,R,R,N,N,
        N,N,N,R,R,R,N,N,
        N,N,N,R,R,R,N,N]

walk_pixel_list = [
        N,N,N,B,B,N,N,N,
        N,N,B,N,N,B,N,N,
        N,B,N,N,N,N,B,N,
        B,N,N,B,B,N,N,B,
        B,N,N,B,B,N,N,B,
        N,B,N,N,N,N,B,N,
        N,N,B,N,N,B,N,N,
        N,N,N,B,B,N,N,N]

DRIVE_list = [
        N,N,N,N,N,N,N,N,
        N,N,G,G,G,G,N,N,
        N,G,N,N,N,N,G,N,
        G,N,N,N,N,N,N,G,
        G,N,N,N,N,N,N,G,
        G,N,N,N,N,N,N,G,
        G,G,G,G,G,G,G,G,
        N,N,N,N,N,N,N,N
]

BACKHAND_list = [
        N,N,N,N,N,N,N,N,
        N,R,R,N,R,R,R,N,
        R,N,N,R,R,N,N,R,
        R,N,N,R,R,N,N,R,
        R,N,N,R,R,N,N,R,
        R,N,N,R,R,N,N,R,
        R,R,R,R,R,R,R,R,
        N,N,N,N,N,N,N,N
]

LOB_list = [
        N,N,N,W,N,N,N,N,
        N,N,W,W,N,N,N,N,
        N,W,W,W,W,W,W,W,
        W,W,W,W,W,W,W,W,
        N,W,W,W,W,W,W,W,
        N,N,W,W,N,N,N,N,
        N,N,N,W,N,N,N,N,
        N,N,N,N,N,N,N,N
]

SERVE_list = [
        N,N,N,N,B,N,N,N,
        N,N,N,N,B,B,N,N,
        B,B,B,B,B,B,B,N,
        B,B,B,B,B,B,B,B,
        B,B,B,B,B,B,B,N,
        N,N,N,N,B,B,N,N,
        N,N,N,N,B,N,N,N,
        N,N,N,N,N,N,N,N
]


