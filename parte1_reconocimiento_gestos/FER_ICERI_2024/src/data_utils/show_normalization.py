# %% Cell1
from typing_extensions import Text
from IPython.core.pylabtools import figsize
from matplotlib import markers
import matplotlib
import matplotlib.pyplot as plt
import mediapipe as mp
import numpy as np
import cv2
import sys
import math

from numpy.core.multiarray import array

sys.path.append("/Users/josebravopacheco/Documents/DeepLearning/FER_ICERI_2024/")
from src.landmarks_utils import face_get_XYZ, normalize_L0, normalize_size


def draw_landmarks(landmarks, ax=None, title=""):
    n_points = len(landmarks[:, 0])
    centroid = (landmarks[:, 0].sum() / n_points, landmarks[:, 1].sum() / n_points)
    ctr_l0_vec = landmarks[0] - np.array(centroid)
    ctr_l0_dist = math.sqrt(ctr_l0_vec[0] ** 2 + ctr_l0_vec[1] ** 2)

    if ax is None:
        plt.scatter(x=landmarks[:, 0], y=landmarks[:, 1])
    else:
        ax.set_box_aspect(1)
        ax.scatter(x=(1280 / 720) * landmarks[:, 0], y=landmarks[:, 1], s=1)
        ax.scatter(x=centroid[0], y=centroid[1], c="r", marker="2")
        ax.annotate(
            text="Centroid",
            xy=centroid,
            xytext=(0.15, 0.25),
            fontsize=12,
            arrowprops={"arrowstyle": "->", "color": "r", "linewidth": 1.5},
            color="r",
        )
        ax.annotate(
            text="Landmark 0",
            xy=landmarks[0],
            xytext=(0.15, 0),
            color="blue",
            fontsize=12,
            arrowprops=dict(arrowstyle="->", color="blue", lw=1.5),
        )
        ax.arrow(
            x=centroid[0],
            y=centroid[1],
            dx=ctr_l0_vec[0],
            dy=ctr_l0_vec[1],
            width=0.0015,
        )
        ax.text(
            x=(centroid[0] + landmarks[0, 0]) / 2 - 0.01,
            y=(centroid[1] + landmarks[0, 1]) / 2,
            s=f"Distance: {ctr_l0_dist:.2f}",
            horizontalalignment="right",
            fontsize=12,
        )
        ax.set_title(title)


mp_detector = mp.solutions.face_mesh.FaceMesh(
    static_image_mode=False,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
)

image = cv2.imread(
    "/Users/josebravopacheco/Documents/DeepLearning/FER_ICERI_2024/data/my_faces_dataset/raw/test/Happy/Happy_test_00004.jpg"
)
results = mp_detector.process(image)
image, landmarks = face_get_XYZ(results)
landmarks = normalize_L0(landmarks)
target_dist = 0.1
landmarks_size_norm = normalize_size(landmarks, target_dist=target_dist)

fig, axs = plt.subplots(
    nrows=1,
    ncols=2,
    sharex=True,
    sharey=True,
    # subplot_kw={"aspect": "equal"},
    figsize=(10, 5),
    layout="constrained",
)

draw_landmarks(landmarks, axs[0], title="Without normalization")
draw_landmarks(landmarks_size_norm, axs[1], title=f"Normalized to d={target_dist:.2f}")
axs[0].set_xbound(-0.3, 0.3)
fig.suptitle("Distance normalization", fontsize="x-large")
plt.savefig("../../figures/normalization.png")
plt.show()
