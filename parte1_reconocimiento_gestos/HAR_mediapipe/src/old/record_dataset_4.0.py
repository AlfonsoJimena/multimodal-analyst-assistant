import time
import cv2
from picamera2 import Picamera2
import os
  
import numpy as np


classes = ["Three","Four","Five"]

dataset_dir = '../data/my_hands_dataset'

photos_per_class = 10 # TOTAL TRAINING IMAGES + TEST IMAGES

n_training_images = 8 # TOTAL TRAINING IMAGES

def record_instance(image,im_class,data_mode="train"):
    filename=os.path.join(dataset_dir,data_mode,im_class,f'photo_{i}.jpg')
    # save image in dataset
    cv2.imwrite(filename, image)
    print("Recorded frame",i,"from class",im_class,data_mode)

def StartRecordingImages(num_images_to_record):
    
    recorded_images = []

    started = time.time()
    last_logged = time.time()
    
    i=0 #contador para imágenes
    
    while True:
        #read image 
        image = picam2.capture_array("main")
        image=cv2.flip(image,+1) #displays image in mirror format
        
        now = time.time()
        
        image = np.ascontiguousarray(image, dtype=np.uint8)
        saved_image = np.copy(image)
        
        if now - last_logged > 1: # Guarda imagen solo cada segundo
            recorded_images.append(saved_image)
            last_logged = now
            i+=1
        
        #add annotations and change frame to color red
        cv2.putText(image,"Recording in progress...",org=(20,40), fontFace=2,fontScale=0.65,color=(0,0,200))
        cv2.putText(image,"Stored images: "+str(i)+"/"+str(num_images_to_record),org=(20,80), fontFace=2,fontScale=0.55,color=(0,0,200))
        
        cv2.imshow("Result", image)
        
        if i==num_images_to_record:
            break
        
        key = cv2.waitKey(1) & 0xFF

        # if the `q` key was pressed, break from the loop
        if key == ord("q"):
            break

    return recorded_images 

# Create dataset folders
for c in classes:
    try:
        os.makedirs(os.path.join(dataset_dir,"train",c))
        os.makedirs(os.path.join(dataset_dir,"test",c))

    except:
        print("Warning: A directory for class",c,"already exists. The images that you are about to record will replace the old dataset.") 

cv2.startWindowThread()

picam2 = Picamera2()

highres_size = (1280, 720)
large_size = (640, 480)
small_size =  (320, 200)

video_config = picam2.create_video_configuration(main = {"size": large_size, "format": "RGB888"})

print("starting config")
picam2.configure(video_config)
print("starting camera")
picam2.start()

# Main loop
for c in classes:

    print("\nPREPARING TO RECORD CLASS:",c)
    print("NUMBER OF TRAINGING IMAGES:",n_training_images)
    print("NUMBER OF TEST IMAGES:",photos_per_class-n_training_images)
    print("\nCheck the cv2 Result window !")
    
    while True: #Empieza a mostrar la imagen por pantalla pra que le usuario se prepare. Cuando se presiona la tecla s el sistema compienza a grabar.
        image = picam2.capture_array("main")
        
        image=cv2.flip(image,+1) #displays image in mirror format
        
        cv2.putText(image,"Next class: "+c,org=(70,210), fontFace=2,fontScale=0.75,color=(0,200,0))
        cv2.putText(image,"Get ready and press \'s\' to start recording",org=(70,260), fontFace=2,fontScale=0.75,color=(0,200,0))
        cv2.putText(image,"or \'q\' to exit.",org=(70,300), fontFace=2,fontScale=0.75,color=(0,200,0))
        
        cv2.imshow("Result", image)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord("s"):
            break
        elif key ==  ord('q'):
	        exit()
	        
    recorded_images = StartRecordingImages(num_images_to_record=photos_per_class)
    
    data_mode="train"
    
    for i in range(photos_per_class):
        name = c + '_' + f'{i+1:05d}' + '.jpg'
        filename=os.path.join(dataset_dir, data_mode, c, name)
        # save image in dataset
        cv2.imwrite(filename, recorded_images[i])
        print("Recorded ", filename)
        if i==n_training_images-1:
            data_mode="test"

print("\nFinnished reccording succesfully.")
cv2.destroyAllWindows()



