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
import torch.nn as nn
import numpy as np
from torchvision import models, transforms
import torchvision.transforms as T
from torchvision.models import EfficientNet_B0_Weights, MobileNet_V2_Weights
import cv2
from torchvision import transforms

import json
import imutils
from imutils.video import FPS
import torch.backends.cudnn as cudnn
import matplotlib.pyplot as plt

ON_RASPBERRY_PI = True

if ON_RASPBERRY_PI:
    from sense_hat import SenseHat

window_title = "Image recognition demonstrator"
cam_config = CameraConfig(FPS=30, resolution='highres')

def class_id_to_label(i, labels):
    return labels[i]
    
def tensor_imshow(inp, title=None):
    """Imshow for Tensor."""
    inp = inp.numpy().transpose((1, 2, 0))
    mean = np.array([0.485, 0.456, 0.406])
    std = np.array([0.229, 0.224, 0.225])
    inp = std * inp + mean
    inp = np.clip(inp, 0, 1)
    #plt.imshow(inp)
    cv2.imshow(title, inp)
    if title is not None:
        plt.title(title)
    #plt.pause(0.001)  # pause a bit so that plots are updated

def main():
    # Start camera, use CVCamera if working on a laptop and PICamera in case you are working on a Raspberry PI
    if ON_RASPBERRY_PI:
        cam = PICamera(recording_res=cam_config.resolution)
        sense_hat = SenseHat()
        sense_hat.set_rotation(180)
    else:
        cam = CVCamera(recording_res=cam_config.resolution, index_cam=1)
        sense_hat = None

    model_path = './models/custom_model_ft.pth'
    #model_path = '../models/model_conv.pth'
    
    labels=sorted(['bear', 'caveman', 'dinosaur', 'horse'])
    num_classes = len(labels)

    colors = Colors()
    colors.DefineListRandomColorsForLabels(labels + ['None'])

    cudnn.benchmark = True
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    torch.backends.quantized.engine = 'qnnpack'

    # MobileNet
    preprocess = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((256, 256)),  # Evita distorsión
        #transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    # MobileNet
    #weights =  MobileNet_V2_Weights.IMAGENET1K_V1

    # EfficientNet
    #preprocess = transforms.Compose([
    #        transforms.ToPILImage(),
    #        weights.transforms(),
    #    ])

    # EfficientNet
    #weights = EfficientNet_B0_Weights.IMAGENET1K_V1

    #net = models.quantization.mobilenet_v2(pretrained=True, quantize=True)
    #net = models.efficientnet_b0(weights='DEFAULT')
    net = models.mobilenet_v2(weights=MobileNet_V2_Weights.DEFAULT)

    print(f'\nModifying pre-trained model: last fc layer updated to {num_classes} classes\n')
    for i in range(num_classes):
        print(f'\t[{i}][{labels[i]}]')
    
    num_ftrs = net.classifier[1].in_features
    net.classifier[1] = nn.Linear(num_ftrs, num_classes)
    net.load_state_dict(torch.load(model_path, map_location=device))
    net.eval()

    # jit model to take it from ~20fps to ~30fps
    net = torch.jit.script(net)

    # Start camera
    cam.start()

    started = time.time()
    last_logged = time.time()
    frame_count = 0

    fps = FPS().start()

    pred = 'None'
    conf = 0
    current_fps = 0

    with torch.set_grad_enabled(False):
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
                input_tensor = preprocess(image)

                # create a mini-batch as expected by the model
                input_batch = input_tensor.unsqueeze(0)

                # run model
                output = net(input_batch)
            
                top = list(enumerate(output[0].softmax(dim=0)))
                top.sort(key=lambda x: x[1], reverse=True)
                for idx, val in top[:num_classes]:
                    print(f"{val.item()*100:.2f}% {class_id_to_label(idx, labels)}")
        
                # Recognition result
                predicted_id = top[0][0]
                predicted_conf = top[0][1]
            
                #image = np.ascontiguousarray(image, dtype=np.uint8)
                pred = class_id_to_label(predicted_id, labels)
                conf = predicted_conf * 100
            
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