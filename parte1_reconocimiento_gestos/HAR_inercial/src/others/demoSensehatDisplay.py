import time
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

sense.set_pixels(pixel_list)
#sense.set_pixels(stand_pixel_list)
#sense.set_pixels(sit_pixel_list)
#sense.set_pixels(walk_pixel_list)
time.sleep(1)
sense.show_message("3... 2... 1...", text_colour=W, scroll_speed=0.05)
sense.show_message("GO!!!", text_colour=R, scroll_speed=0.05)
