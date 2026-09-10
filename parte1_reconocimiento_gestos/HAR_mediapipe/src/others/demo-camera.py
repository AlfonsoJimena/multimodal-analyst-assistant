#!/usr/bin/python3

# The QtPreview uses software rendering and thus makes more use of the
# CPU, but it does work with X forwarding, unlike the QtGlPreview.

import time

from picamera2 import Picamera2, Preview
from libcamera import ColorSpace

picam2 = Picamera2()
picam2.start_preview(Preview.QT)

#preview_config = picam2.create_preview_configuration(colour_space=ColorSpace.Sycc())
#preview_config = picam2.create_preview_configuration(colour_space=ColorSpace.Rec709())
preview_config = picam2.create_preview_configuration(lores={"size": (320, 240)}, display="lores", buffer_count=10, queue=False)

preview_config = picam2.create_video_configuration(main={"size": (2048, 1536)}, lores={"size": (320, 240)}, 
                                                   display="lores", encode="lores")

#[{'format': SRGGB10_CSI2P, 'unpacked': 'SRGGB10', 'bit_depth': 10, 'size': (640, 480), 'fps': 103.33, 'crop_limits': (1000, 752, 1280, 960), 'exposure_limits': (75, None)}, 
#{'format': SRGGB10_CSI2P, 'unpacked': 'SRGGB10', 'bit_depth': 10, 'size': (1640, 1232), 'fps': 41.85, 'crop_limits': (0, 0, 3280, 2464), 'exposure_limits': (75, 11766829, None)}, 
#{'format': SRGGB10_CSI2P, 'unpacked': 'SRGGB10', 'bit_depth': 10, 'size': (1920, 1080), 'fps': 47.57, 'crop_limits': (680, 692, 1920, 1080), 'exposure_limits': (75, 11766829, None)}, 
#{'format': SRGGB10_CSI2P, 'unpacked': 'SRGGB10', 'bit_depth': 10, 'size': (3280, 2464), 'fps': 21.19, 'crop_limits': (0, 0, 3280, 2464), 'exposure_limits': (75, 11766829, None)}, 
#{'format': SRGGB8, 'unpacked': 'SRGGB8', 'bit_depth': 8, 'size': (640, 480), 'fps': 103.33, 'crop_limits': (1000, 752, 1280, 960), 'exposure_limits': (75, 11766829, None)}, 
#{'format': SRGGB8, 'unpacked': 'SRGGB8', 'bit_depth': 8, 'size': (1640, 1232), 'fps': 41.85, 'crop_limits': (0, 0, 3280, 2464), 'exposure_limits': (75, 11766829, None)}, 
#{'format': SRGGB8, 'unpacked': 'SRGGB8', 'bit_depth': 8, 'size': (1920, 1080), 'fps': 47.57, 'crop_limits': (680, 692, 1920, 1080), 'exposure_limits': (75, 11766829, None)}, 
#{'format': SRGGB8, 'unpacked': 'SRGGB8', 'bit_depth': 8, 'size': (3280, 2464), 'fps': 21.19, 'crop_limits': (0, 0, 3280, 2464), 'exposure_limits': (75, 11766829, None)}]

# If you wanted a 25 frames-per-second video you could use:
# controls={"FrameDurationLimits": (40000, 40000)}
preview_config = picam2.create_preview_configuration({"size": (640, 480)}, raw=picam2.sensor_modes[4], controls={"FrameDurationLimits": (40000, 40000)})

print(preview_config["main"])
print(preview_config["lores"])
print(picam2.sensor_modes)
picam2.configure(preview_config)

picam2.start()
time.sleep(5)