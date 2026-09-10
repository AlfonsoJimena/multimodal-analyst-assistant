from time import sleep
import cv2
#from picamera import PiCamera
from picamera2 import Picamera2
import os
import imutils
from imutils.video import FPS
import torch
import numpy as np
from torchvision import models, transforms

classes = ["One","Two","Three"]

dataset_dir = 'my_hands_dataset'

photos_per_class = 10
n_training_images = 8

def record_instance(i,im_class,data_mode="train"):
    #ret,frame=camera.read()     
    #read image
    image = picam2.capture_array("main")
    filename=os.path.join(dataset_dir,data_mode,im_class,f'photo_{i}.jpg')
    cv2.imwrite(filename,image)
    image = np.ascontiguousarray(image, dtype=np.uint8)
    # show the output frame
    cv2.imshow("Result", image)
    print("Recorded frame",i)
    sleep(1)

    
for c in classes:
    try:
        os.makedirs(os.path.join(dataset_dir,"train",c))
        os.makedirs(os.path.join(dataset_dir,"test",c))

    except:
        pass
        #print("Warning: A directory for class",c,"already exists. The images that you are about to record won't replace the old images but will be added to the existing dataset.") 


#camera = cv2.VideoCapture(0)
#sleep(2)

cv2.startWindowThread()

picam2 = Picamera2()
lsize = (640, 480)
video_config = picam2.create_video_configuration(
    #main={"size": (1280, 720), "format": "RGB888"},
    main={"size": lsize, "format": "RGB888"},
    lores={"size": lsize, "format": "YUV420"})

picam2.configure(video_config)
picam2.start()

preprocess = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

#for c in classes:
    
#    print("PREPARING TO RECORD CLASS:",c)
#    #sleep(10) #give enough time for the camera to get ready
i=0
fps = FPS().start()
while 1:
    image = picam2.capture_array("main")
    # preprocess
    input_tensor = preprocess(image)
    #filename=os.path.join(dataset_dir,data_mode,im_class,f'photo_{i}.jpg')
    #cv2.imwrite(filename,image)
    image = np.ascontiguousarray(image, dtype=np.uint8)
    # show the output frame
    cv2.imshow("Result", image)
    print("Recorded frame",i)
    i = i + 1
    #sleep(1)
    # update the FPS counter
    fps.update()

    #for i in range(n_training_images):      
    #    record_instance(i,c,"train")
   
    #for i in range(n_training_images,photos_per_class):      
    #    record_instance(i,c,"test")

