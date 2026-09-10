import os
import math
import cv2
import pandas as pd
import numpy as np
import mediapipe as mp
from tqdm import tqdm

DATA_PATH = "data/RAVDESS"
ANNOT_PATH = os.path.join(DATA_PATH, "annotations_frames.csv")
LANDMARKS_SAVE_DIR = os.path.join(DATA_PATH, "landmarks_L0_SizeNorm")

NORM_TYPE = "L0"  # Possible values: "NONE", "L0"
NORM_SIZE = True


def extract_landmarks(frame_path, mp_detector):
    frame = cv2.imread(frame_path)
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = mp_detector.process(frame)
    landmarks_values = [[0, 0] for _ in range(478)]

    for face_landmarks in results.multi_face_landmarks:
        for i in range(len(face_landmarks.landmark)):
            x = face_landmarks.landmark[i].x
            y = 1 - face_landmarks.landmark[i].y
            landmarks_values[i] = [x, y]

    return np.array(landmarks_values)


def normalize_L0(landmarks):
    if np.sum(landmarks) == 0:
        return landmarks

    x_off = landmarks[0, 0]
    y_off = landmarks[0, 1]

    for i in range(len(landmarks)):
        landmarks[i, 0] -= x_off
        landmarks[i, 1] -= y_off

    return landmarks


def normalize_size(landmarks, target_dist=0.25):
    n_points = len(landmarks[:, 0])
    centroid = (landmarks[:, 0].sum() / n_points, landmarks[:, 1].sum() / n_points)

    dist_centr_l0 = math.sqrt(
        math.pow((centroid[0] - landmarks[0, 0]), 2)
        + math.pow((centroid[1] - landmarks[0, 1]), 2)
    )
    scale = target_dist / dist_centr_l0

    return scale * landmarks


def save_landmarks(frame_sub_path, landmarks):
    save_path = os.path.join(LANDMARKS_SAVE_DIR, frame_sub_path)
    os.makedirs(os.path.join(*save_path.split("/")[:-1]), exist_ok=True)
    np.save(save_path, landmarks)


if __name__ == "__main__":
    annotations = pd.read_csv(ANNOT_PATH)
    mp_detector = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
    )
    for _, frame_annot in tqdm(
        annotations.iterrows(), desc="Extracting landmarks", total=len(annotations)
    ):
        frame_path = frame_annot.loc["path"]
        frame_sub_path = os.path.join(*frame_path.split(".")[0].split("/")[-3:])
        landmarks = extract_landmarks(frame_path, mp_detector)
        if NORM_TYPE == "L0":
            landmarks = normalize_L0(landmarks)
        if NORM_SIZE:
            landmarks = normalize_size(landmarks)
        save_landmarks(frame_sub_path, landmarks)
