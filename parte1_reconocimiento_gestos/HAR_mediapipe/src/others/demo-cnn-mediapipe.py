import time

import cv2
import os
from keras.models import load_model, model_from_json
import numpy as np

import json
import imutils
from imutils.video import FPS
import torch.backends.cudnn as cudnn
import matplotlib.pyplot as plt
import mediapipe as mp

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

from picamera2 import Picamera2

cmd_debug = 0

pred_mappings="ABCDEFGHIJKLMNOPQRSTUVWXYZ "
#pred_mappings=["one","two","three"]

def normalize_from_0_landmark(data):
    new_data = np.copy(data)
    for i in range(data.shape[0]):
        if ((data[i, 0] + data[i, 1]) != 0):
            x_center = data[i, 0]
            y_center = data[i, 1]
            for k in range(2, data.shape[1], 2):
                new_data[i, k] = data[i, k] - x_center
                new_data[i, k + 1] = data[i, k + 1] - y_center
    return new_data


def extract_plots(mp_hands, IMAGE_FILES, images_symbol_path, out_path_imgs):
    # para poder dibujar después
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles

    with mp_hands.Hands(
            static_image_mode=True,
            max_num_hands=1,
            min_detection_confidence=0.5) as hands:
        for idx, file in enumerate(IMAGE_FILES):
            try:
                path_img = os.path.join(images_symbol_path, file)
                image = cv2.imread(path_img)
                image_height, image_width, _ = image.shape
                # Convert the BGR image to RGB before processing.
                results = hands.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

                annotated_image = image.copy()
                if not results.multi_hand_landmarks is None:
                    for hand_landmarks in results.multi_hand_landmarks:
                        # Draw hands landmarks on the image.
                        mp_drawing.draw_landmarks(
                            annotated_image,
                            hand_landmarks,
                            mp_hands.HAND_CONNECTIONS,
                            landmark_drawing_spec=mp_drawing_styles.get_default_hand_landmarks_style())
                cv2.imwrite(out_path_imgs + file.split(".")[0] + '.png', annotated_image)
            except Exception:
                with open('logs.txt', 'a') as f:
                    print('extract_plots() ', images_symbol_path, ' ', idx + 1, ' ', file, file=f)


def get_XYZ(mp_hands, image):

    # esto para dibujar
    mp_drawing = mp.solutions.drawing_utils
    
    with mp_hands.Hands(
            static_image_mode=True,
            max_num_hands=1,
            min_detection_confidence=0.5) as hands:

        #video_df = pd.DataFrame([], columns=columns + ["label", "frame", "path"])

    
        image_height, image_width, _ = image.shape
        # Convert the BGR image to RGB before processing.
        results = hands.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

        values = []
        
        if results.multi_hand_landmarks is None:
            for i in range(21): # 21 landmarks
                values += [0, 0]
                
        else:
            for hand_landmarks in results.multi_hand_landmarks:
                for i in range(len(hand_landmarks.landmark)):
                    x = hand_landmarks.landmark[i].x  # * image_width
                    y = 1 - hand_landmarks.landmark[i].y  # * image_height (1-y for providing same shape as in image)
                    values += [x, y]

                    # pruebo a dibujar
                    mp_drawing.draw_landmarks(
                            image, hand_landmarks, mp_hands.HAND_CONNECTIONS,
                            mp_drawing.DrawingSpec(color=(255, 255, 0), thickness=4, circle_radius=5),
                            mp_drawing.DrawingSpec(color=(255, 0, 255), thickness=4))
                            
                            # muestro la imagen
        return image, np.array(values)
 

print("LOADING  MEDIAPIPE")
mp_hands = mp.solutions.hands

print("Starting cv2 window")
cv2.startWindowThread()

# load model
print("LOADING MODEL")

weight_path = '../models/poses.h5'
json_file = "../models/poses.json"

#with open(json_file) as f:
#    loaded_model_json= f.read()

#model = model_from_json(loaded_model_json)
#model.load_weights(weight_path)

print("LOADED MODEL:",json_file)

#Camera configuration

print("Starting camera...")
picam2 = Picamera2()

highres_size = (1280, 720)
large_size = (640, 480)
small_size =  (320, 200)

video_config = picam2.create_video_configuration(
    #main={"size": (1280, 720), "format": "RGB888"},
    main={"size": small_size, "format": "RGB888"},
    #main={"size": small_size, "format": "XBGR8888"},
    #main={"size": small_size, "format": "BGR888"},
    lores={"size": small_size, "format": "YUV420"})

#video_config = picam2.create_video_configuration({"size": (640, 480)}, raw=picam2.sensor_modes[4], buffer_count=8, queue=False)

picam2.configure(video_config)
picam2.start()


t = 3 # Ajustar el tiempo entre predicciones
last_logged = time.time()
pred= ""

# Main program
while True:
    
    image = picam2.capture_array("main")
    
    image = cv2.flip(image,1) 
    now = time.time()
    #image,values = get_XYZ(mp_hands,image)
    
    #model prediction SOLO CADA X TIEMPO     
    if now - last_logged > t:
        #prediccion landmarks con modelo de mediapipe
        image,values = get_XYZ(mp_hands,image)
        #values = np.arange(42)
        if cmd_debug:
                print("Values:",values)
        
        values=np.reshape(values,(1,21,2,1))
        
        #aplicar normalizacion
        #values=normalize_from_0_landmark(values)
        
        #pred=np.argmax(model.predict(values))
        
        
        
        pred=pred_mappings[np.argmax(model(values))]
        if cmd_debug:
               print("Prediction:",pred)
        
    # show the output frame
    cv2.putText(image,"Predicted class: "+pred,org=(10, small_size[1]-20), fontFace=2,fontScale=0.75,color=(0,200,100))
    cv2.imshow("Model prediction", image)
    
    key = cv2.waitKey(1) & 0xFF

    # if the `q` key was pressed, break from the loop
    if key == ord("q"):
        break

cv2.destroyAllWindows()
