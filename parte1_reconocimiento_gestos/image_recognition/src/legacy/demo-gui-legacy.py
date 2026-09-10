import time

import torch
import numpy as np
from torchvision import models, transforms

import cv2
from PIL import Image

import json

import imutils
from imutils.video import FPS

def class_id_to_label(i):
    return labels[i]

with open('./imagenet-simple-labels/imagenet-simple-labels.json') as f:
    labels = json.load(f)

COLORS = np.random.uniform(0, 255, size=(len(labels), 3))

torch.backends.quantized.engine = 'qnnpack'

cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 224)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 224)
cap.set(cv2.CAP_PROP_FPS, 36)

preprocess = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

net = models.quantization.mobilenet_v2(pretrained=True, quantize=True)
# jit model to take it from ~20fps to ~30fps
net = torch.jit.script(net)

started = time.time()
last_logged = time.time()
frame_count = 0

fps = FPS().start()

with torch.no_grad():
    while True:
        # read frame
        ret, image = cap.read()
        if not ret:
            raise RuntimeError("failed to read frame")

        # convert opencv output from BGR to RGB
        image = image[:, :, [2, 1, 0]]
        permuted = image

        # preprocess
        input_tensor = preprocess(image)

        # create a mini-batch as expected by the model
        input_batch = input_tensor.unsqueeze(0)

        # run model
        output = net(input_batch)
        # do something with output ...

        # log model performance
        frame_count += 1
        now = time.time()
        if now - last_logged > 1:
            print(f"{frame_count / (now-last_logged)} fps")
            last_logged = now
            frame_count = 0
        
            top = list(enumerate(output[0].softmax(dim=0)))
            top.sort(key=lambda x: x[1], reverse=True)
            for idx, val in top[:10]:
                print(f"{val.item()*100:.2f}% {class_id_to_label(idx)}")
            
        
        # draw the prediction on the frame
        image = imutils.resize(image, width=400)
        startX=0
        startY=0
        endX=200
        endY=200
        image = np.ascontiguousarray(image, dtype=np.uint8)
        label = "{}: {:.2f}%".format(class_id_to_label(top[0][0]), top[0][1] * 100)
        #cv2.rectangle(image, (startX, startY), (endX, endY), COLORS[idx], 2)
        y = startY - 15 if startY - 15 > 15 else startY + 15
        pt1 = (int(startX), int(y))
        cv2.putText(image, label, pt1, cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS[idx], 2)
        
        # show the output frame
        cv2.imshow("Frame", image)
        key = cv2.waitKey(1) & 0xFF

        # if the `q` key was pressed, break from the loop
        if key == ord("q"):
            break

        # update the FPS counter
        fps.update()

# stop the timer and display FPS information
fps.stop()
print("[INFO] elapsed time: {:.2f}".format(fps.elapsed()))
print("[INFO] approx. FPS: {:.2f}".format(fps.fps()))

# do a bit of cleanup
cv2.destroyAllWindows()
#cap.stop()
