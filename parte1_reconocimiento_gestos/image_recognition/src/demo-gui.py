import sys
import os

# We add the common folder to the path
# This folder contains the libraries that are shared between the different demos
# This way we can import them without duplicating code
lib_path = os.path.abspath("../common/")
sys.path.append(lib_path)

#Ahora puedes importar tus modulos.
from cameras import CVCamera, PICamera, CameraConfig
from gui import Colors, WindowMessage

import time
import torch
import numpy as np
from torchvision import models, transforms
from torchvision.models.quantization import MobileNet_V2_QuantizedWeights

import cv2
from PIL import Image

import json
from imutils.video import FPS

ON_RASPBERRY_PI = False

if ON_RASPBERRY_PI:
    from sense_hat import SenseHat
    
window_title = "Image recognition demonstrator"
if ON_RASPBERRY_PI:
    cam_config = CameraConfig(FPS=30, resolution='large')
else:
    cam_config = CameraConfig(FPS=30, resolution='highres')

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def class_id_to_label(i, labels):
    return labels[i]

def main():
    # Start camera, use CVCamera if working on a laptop and PICamera in case you are working on a Raspberry PI
    if ON_RASPBERRY_PI:
        cam = PICamera(recording_res=cam_config.resolution)
        sense_hat = SenseHat()
        sense_hat.set_rotation(180)
    else:
        cam = CVCamera(recording_res=cam_config.resolution, index_cam=1)
        sense_hat = None

    # Load the labels
    with open('./models/imagenet-simple-labels/imagenet-simple-labels.json') as f:
        labels = json.load(f)

    colors = Colors()
    colors.DefineListRandomColorsForLabels(labels + ['None'])

    preprocess = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize(256),  # Evita distorsión
        transforms.CenterCrop(256),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    # Cargar modelo preentrenado y optimizado
    torch.backends.quantized.engine = 'qnnpack'
    net = models.quantization.mobilenet_v2(weights=MobileNet_V2_QuantizedWeights.DEFAULT, quantize=True)
    net = torch.jit.script(net).to(device) # jit model to take it from ~20fps to ~30fps
    net.eval()
    
    # Start camera
    cam.start()

    started = time.time()
    last_logged = time.time()
    frame_count = 0

    fps = FPS().start()

    pred, conf, current_fps = 'None', 0, 0

    with torch.no_grad():
        while True:
            #read image
            image = cam.read_frame()
            if image is None:
                # Depending the setup, the camera might need approval to activate, so wait until we start receiving images.
                print("Waiting for camera input")
                continue

            # log model performance
            frame_count += 1
            now = time.time()
            if now - last_logged > 1:
                current_fps = frame_count / (now-last_logged)
                print(f"{current_fps} fps")
                
                last_logged = now
                frame_count = 0
            
                # preprocess
                input_tensor = preprocess(image).to(device)

                # create a mini-batch as expected by the model
                input_batch = input_tensor.unsqueeze(0)

                # run model
                output = net(input_batch)

                top = list(enumerate(output[0].softmax(dim=0)))
                top.sort(key=lambda x: x[1], reverse=True)
                for idx, val in top[:10]:
                    print(f"{val.item()*100:.2f}% {class_id_to_label(idx, labels)}")
                
                # Recognition result
                predicted_id = top[0][0]
                predicted_conf = top[0][1]
                
                #image = np.ascontiguousarray(image, dtype=np.uint8)
                pred = class_id_to_label(predicted_id, labels)
                conf = predicted_conf * 100
                
                #cv2.rectangle(image, (startX, startY), (endX, endY), COLORS[idx], 2)
            
            class_msgs = WindowMessage(
                    txt1 = "Predicted class: {} ({:.2f}) - fps: {:.2f}".format(pred, conf, current_fps), pos1 = (10, cam_config.resolution[1]-20), col1 = colors.GetColorForClass(pred),
                    txt2 = "", pos2 = (0, 0), col2 = colors.color['black'],
                    txt3 = "", pos3 = (0, 0), col3 = colors.color['black'])

            class_msgs.ShowWindowMessages(image)
            
            # show the output frame
            cv2.imshow(window_title, image)
            
            # Press 'q' to quit the program
            key = cv2.waitKey(int(1 / cam_config.FPS * 1000)) & 0xFF

            # if the `q` key was pressed, break from the loop
            if key ==  ord('q'):
                if ON_RASPBERRY_PI:
                    sense_hat.clear()
                break

            # update the FPS counter
            fps.update()

    # stop the timer and display FPS information
    fps.stop()
    print("[INFO] elapsed time: {:.2f}".format(fps.elapsed()))
    print("[INFO] approx. FPS: {:.2f}".format(fps.fps()))

    # Release resources
    cam.stop()
    exit()

if __name__ == "__main__":
    main()