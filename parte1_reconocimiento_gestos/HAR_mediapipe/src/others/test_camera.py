#!/usr/bin/python3

import cv2

from picamera2 import Picamera2

cv2.startWindowThread()

picam2 = Picamera2()
lsize = (640, 480)
video_config = picam2.create_video_configuration(
    #main={"size": (1280, 720), "format": "RGB888"},
    main={"size": lsize, "format": "RGB888"},
    lores={"size": lsize, "format": "YUV420"})

picam2.configure(video_config)
picam2.start()

while True:
    #yuv420 = picam2.capture_array("lores")
    #print(yuv420)
    #rgb = cv2.cvtColor(yuv420, cv2.COLOR_YUV420p2RGB)
    rgb = picam2.capture_array("main")
    cv2.imshow("Camera", rgb)
    cv2.waitKey(0) # waits until a key is pressed
    
