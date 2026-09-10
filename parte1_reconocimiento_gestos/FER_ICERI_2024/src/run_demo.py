print("Loading dependencies... (It might take a while the first time)")
import keras
import cv2
import os
import time
import numpy as np
import mediapipe as mp
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt
from cameras import CVCamera, PICamera
from landmarks_utils import (
    face_get_XYZ,
    normalize_L0,
    normalize_size,
)

ON_RASPBERRY_PI = False
if ON_RASPBERRY_PI:
    from sense_hat import SenseHat


# RESOLUTIONS
HIGHRES_SIZE = (1280, 720)
LARGE_SIZE = (640, 480)
SMALL_SIZE = (320, 200)

# COLORS
GREEN = (0, 255, 0)
BLUE = (255, 0, 0)
RED = (0, 0, 255)

# FRAME RATE
FPS = 30

MODEL_PATH = "models/FER_finetuned.keras"

# Remember they must keep the same order than the used in training.
# The image is used when using the sense hat. It must be a mask image of 8x8 px.
classes = [
    {"label": "Angry", "image": "hmmm.png"},
    {"label": "Happy", "image": "smiley.png"},
    {"label": "Sad", "image": "sad.png"},
    {"label": "Surprise", "image": "surprise.png"},
]


def get_face_corners(landmarks, image_size):
    maxs = np.squeeze(np.max(landmarks, axis=0))
    mins = np.squeeze(np.min(landmarks, axis=0))
    corner_ul = np.array([mins[0], 1 - maxs[1]])
    corner_br = np.array([maxs[0], 1 - mins[1]])

    for i in range(2):
        corner_ul[i] = int(corner_ul[i] * image_size[i])
        corner_br[i] = int(corner_br[i] * image_size[i])

    corner_ul = corner_ul.astype(np.int32)
    corner_br = corner_br.astype(np.int32)
    return corner_ul, corner_br


def draw_results(image, results, classes, face_corners=None, sense_hat=None):
    """
    Draws the results and graphics on top of the camera's recording.

    Parameters:
        - image: array of the recorded image
        - results: normalized logits obtained from the model
        - face_corners: list with the corners with format [corner_up_left, corner_down_right] == [(x0,y0), (x1,y1)]
    """
    if face_corners[0] == face_corners[1]:
        return image

    prediction_idx = np.argmax(results)
    probability = results[0, prediction_idx] * 100
    label = classes[prediction_idx]["label"]

    image_pil = Image.fromarray(image)
    draw = ImageDraw.Draw(image_pil)

    if ON_RASPBERRY_PI:
        text_font = ImageFont.truetype("NotoMono-Regular.ttf", 16)
    else:
        # This is the font that is showed in the demo.
        # Asjust it to one font of your system.
        text_font = ImageFont.truetype("Arial.ttf", 16)

    draw.text(
        (face_corners[0][0], face_corners[0][1] - 20),
        f"Emotion: {label} ({probability:.2f}%)",
        font=text_font,
        fill=(0, 0, 255, 255),
    )

    if face_corners is not None:
        draw.rectangle(face_corners, outline=(0, 0, 255, 255))

    if sense_hat is not None:
        sense_hat.load_image(
            os.path.join("emoticons", classes[prediction_idx]["image"])
        )

    image_rgb = np.array(image_pil)
    return image_rgb


def main():
    # Load model to use
    print("Loading model...")
    model = keras.models.load_model(MODEL_PATH)
    print("Model loaded!")

    # Load mediapipe Face Mesh utility for landmark extraction
    mp_detector = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
    )

    # Start camera, use CVCamera if working on a laptop and PICamera in case you are working on a Raspberry PI
    if ON_RASPBERRY_PI:
        cam = PICamera(recording_res=HIGHRES_SIZE)
        sense_hat = SenseHat()
        sense_hat.set_rotation(180)
    else:
        cam = CVCamera(recording_res=HIGHRES_SIZE, index_cam=1)
        sense_hat = None

    cam.start()

    now = 0
    last = 0
    predictions = np.zeros((1, len(classes)))

    while True:
        image_rgb = cam.read_frame()
        if image_rgb is None:
            # Depending the setup, the camera might need approval to activate, so wait until we start receiving images.
            print("Waiting for camera input")
            continue

        now = time.time()
        results = mp_detector.process(image_rgb)
        _, landmarks = face_get_XYZ(results=results, image_rgb=None)
        corner_ul, corner_br = get_face_corners(landmarks, HIGHRES_SIZE)

        # Process the image to the model every 0.25s
        if now - last > 0.25 and landmarks.sum() != 0:
            landmarks = landmarks.astype(np.float32)

            # Apply normalizations
            landmarks = normalize_L0(landmarks)
            landmarks = normalize_size(landmarks)

            # Add axis for batch (axis 0) and channels (axis 3)
            landmarks = np.expand_dims(landmarks, (0, 3))

            # Obtain model's prediction
            predictions = model(landmarks)

            last = time.time()

        image_rgb = draw_results(
            image_rgb,
            predictions,
            classes,
            face_corners=[tuple(corner_ul), tuple(corner_br)],
            sense_hat=sense_hat,
        )

        cv2.imshow("Emotions classifier", image_rgb)
        key = cv2.waitKey(int(1 / FPS * 1000)) & 0xFF
        if key == ord("q"):
            if ON_RASPBERRY_PI:
                sense_hat.clear()
            break


if __name__ == "__main__":
    main()
