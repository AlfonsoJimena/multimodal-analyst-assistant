import cv2
import mediapipe as mp
import libcamera
import numpy as np
from picamera2 import Picamera2, Preview
from keras.models import load_model, model_from_json
from landmarksLib import get_XYZ

debug_HAR = False
only_landmarks = False
#pred_mappings="ABCDEFGHIJKLMNOPQRSTUVWXYZ "
pred_mappings=['Five', 'Four', 'Three', ' ']
landmark_values = [[0, 0] for _ in range(21)]

def main():
    large_size = (640, 480)
    small_size =  (320, 200)
    
    # Initialize PiCamera
    picam2 = Picamera2()
    preview_config = picam2.create_preview_configuration(main={"size": large_size}, 
                                                         controls={"AwbEnable": False,
                                                                   #"AwbMode": libcamera.controls.AwbModeEnum.Indoor,
                                                                   "AwbMode": libcamera.controls.AwbModeEnum.Auto,
                                                                   "AnalogueGain": 1.0})
    picam2.configure(preview_config)
    picam2.start_preview(Preview.NULL)
    picam2.start()

    # Initialize Mediapipe
    print('Initializing Mediapipe')
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(static_image_mode=False, 
                           max_num_hands=1, # max_num_hands=2, 
                           min_detection_confidence=0.5)
    
    # load model
    if only_landmarks == False:
        print("LOADING MODEL")

        #weight_path = '../models/poses.h5'
        #json_file = "../models/poses.json"
        weight_path = '../models/Five_Four_Three_CNN1.h5'
        json_file = "../models/Five_Four_Three_CNN1.json"

        with open(json_file) as f:
            loaded_model_json= f.read()

        model = model_from_json(loaded_model_json)
        model.load_weights(weight_path)

        print("LOADED MODEL:",json_file)

    print('Start processing frames')
    num_frames = 0
                
    while True:
        image = picam2.capture_array()
        num_frames=+1
        
        if debug_HAR:
            if num_frames % 25 == 0:
                print('num_frames = %d' % num_frames)
        
        # Convert the image to RGB for Mediapipe
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Process the image and get hand landmarks
        results = hands.process(image_rgb)

        if results.multi_hand_landmarks:
            if debug_HAR:
                print('HAY MANO')
            
            image_rgb, landmark_values = get_XYZ(results, image_rgb)
        
        # Show the processed frame
        if only_landmarks:
            cv2.imshow("Hand Landmarks", image_rgb)
        else:
            if results.multi_hand_landmarks:
                landmarks_nparray = np.array(landmark_values)
                landmarks_nparray = np.reshape(landmarks_nparray, (1,21,2,1))
                pred = pred_mappings[np.argmax(model(landmarks_nparray))]
                cv2.putText(image_rgb, 
                            "Predicted class: "+pred,
                            org=(10, large_size[1]-20), 
                            fontFace=2,
                            fontScale=0.75,
                            color=(0,200,100))
            else:
                cv2.putText(image_rgb, 
                            "Predicted class: none",
                            org=(10, large_size[1]-20), 
                            fontFace=2,
                            fontScale=0.75,
                            color=(0,200,100))
            cv2.imshow("Model prediction", image_rgb)
        
        # Press 'q' to quit the program
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Release resources
    cv2.destroyAllWindows()
    hands.close()
    picam2.close()

if __name__ == "__main__":
    main()
