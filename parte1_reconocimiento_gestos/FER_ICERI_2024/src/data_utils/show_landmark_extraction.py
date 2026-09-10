from IPython.core.pylabtools import figsize
import matplotlib.pyplot as plt
import mediapipe as mp
import numpy as np
from PIL import Image

import sys

sys.path.append(".")
from src.landmarks_utils import face_get_XYZ

mp_detector = mp.solutions.face_mesh.FaceMesh(
    static_image_mode=False,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
)

fig, axs = plt.subplots(
    ncols=2,
    nrows=1,
    figsize=(8, 3),
    layout="constrained",
)

with Image.open(
    "/Users/josebravopacheco/Documents/DeepLearning/FER_ICERI_2024/figures/frame_0189.jpg"
) as img:
    axs[0].imshow(img.convert("RGB"))
    axs[0].set_title("Original image")
    image_rgb = np.array(img)
    results = mp_detector.process(image_rgb)
    blank_image = 255 * np.ones_like(image_rgb)
    img_landmarks, landmarks = face_get_XYZ(results, blank_image)
    axs[1].imshow(img_landmarks)
    axs[1].set_title("Landmarks extracted")

fig.suptitle("Face landmarks extraction", fontsize="x-large")
plt.show()
