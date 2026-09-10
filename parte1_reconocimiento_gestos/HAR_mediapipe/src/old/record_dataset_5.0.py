import time
import cv2
from picamera2 import Picamera2
import os

import numpy as np


classes = ["One","Two","Three"]

dataset_dir = 'my_hands_dataset'

photos_per_class = 10 # TOTAL TRAINING IMAGES + TEST IMAGES
n_training_images = 8 # TOTAL TRAINING IMAGES

def record_instance(i,im_class,data_mode="train"):

    filename=os.path.join(dataset_dir,data_mode,im_class,f'photo_{i}.jpg')
    # save image in dataset
    cv2.imwrite(filename,image)
    print("Recorded frame",i,"from class",im_class,data_mode)


# Create dataset folders
for c in classes:
    try:
        os.makedirs(os.path.join(dataset_dir,"train",c))
        os.makedirs(os.path.join(dataset_dir,"test",c))

    except:
        print("Warning: A directory for class",c,"already exists. The images that you are about to record will replace the old dataset.") 

cv2.startWindowThread()

picam2 = Picamera2()

lsize = (640, 480)
video_config = picam2.create_video_configuration(
    #main={"size": (1280, 720), "format": "RGB888"},
    main={"size": lsize, "format": "RGB888"},
    lores={"size": lsize, "format": "YUV420"})

print("starting config")
picam2.configure(video_config)
print("starting camera")
picam2.start()

started = time.time()
last_logged = time.time()

# Main loop
for c in classes:
    
    i=0 #contador para imágenes

    print("\nPREPARING TO RECORD CLASS:",c)
    print("NUMBER OF TRAINGING IMAGES:",photos_per_class)
    print("NUMBER OF TEST IMAGES:",photos_per_class-n_training_images)
    input("Press any key to start recording \n")
    while True:
        #read image 
        image = picam2.capture_array("main")
        now = time.time()
        
        image = np.ascontiguousarray(image, dtype=np.uint8)
        cv2.imshow("Result", image)
        
        if now - last_logged > 1: # Guarda imagen solo cada segundo
            if i<n_training_images:
                record_instance(i,c,"train")
            else:
                record_instance(i,c,"test")
            last_logged = now
            i+=1
        
        if i==photos_per_class:
            #cv2.destroyAllWindows()
            break
        
        key = cv2.waitKey(1) & 0xFF

        # if the `q` key was pressed, break from the loop
        if key == ord("q"):
            cv2.destroyAllWindows()
            break
    
            



