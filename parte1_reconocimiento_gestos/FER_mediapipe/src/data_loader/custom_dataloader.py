import pandas as pd
import cv2
import sys
import os
import numpy as np
from config import ConfigMediapipeDetector

#sys.path.append(".")
#from src.landmarks_utils import normalize_L0, normalize_size, face_get_XYZ
from landmarks_utils import normalize_L0, normalize_size, face_get_XYZ
import mediapipe as mp
import tensorflow as tf
from sklearn.model_selection import train_test_split

def preprocess(landmarks, label):
    landmarks = tf.image.convert_image_dtype(
        landmarks[..., tf.newaxis], dtype=tf.float32
    )

    label = tf.cast(label, tf.float32)
    return landmarks, label

class MyDataset:
    def __init__(self, data_path, split, use_none_class=False, normalizations=None, extract_landmarks=False):
        """
          Parameters:
            - data_path: path to the dataset root, e.g. .../my_faces_dataset
            - split: Split to load: 'train' or 'test'
            - use_none_class: Reserve an extra None class when no landmarks are detected.
            - normalizations: List of normalizations to apply to the landmarks. Possible values: 'L0', 'size'.
            - extract_landmarks: If True, landmarks are extracted once and saved under a preprocessed folder.
        """

        print(f"\nPreparing {split} dataloader")
        self.data_path = os.path.abspath(data_path)
        self.split = split
        self.split_dir = os.path.join(self.data_path, self.split)

        if not os.path.isdir(self.split_dir):
            raise FileNotFoundError(f"Split directory does not exist: {self.split_dir}")

        self.normalizations = normalizations or []
        self.use_none_class = use_none_class

        self.classes = sorted(
            d for d in os.listdir(self.split_dir)
            if os.path.isdir(os.path.join(self.split_dir, d))
        )

        if not self.classes:
            raise ValueError(f"No class folders found under {self.split_dir}")

        if self.use_none_class:
            self.classes.append("None")

        print(f"The following classes were detected: {self.classes}")
        print(f"Normalizations used: {self.normalizations}")

        self.samples = []
        for class_name in self.classes[:-1] if self.use_none_class else self.classes:
            class_dir = os.path.join(self.split_dir, class_name)
            for image_name in sorted(os.listdir(class_dir)):
                image_path = os.path.join(class_dir, image_name)
                if os.path.isfile(image_path) and image_name.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
                    self.samples.append((image_path, class_name))

        self.len_dataset = len(self.samples)
        print(f"Loaded {self.len_dataset} samples for split '{self.split}'")

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        model_path = os.path.join(project_root, "models", "face_landmarker.task")
        self.mp_detector = ConfigMediapipeDetector(model_path)

        if extract_landmarks:
            print("Performing landmark extraction.")
            self.extract_landmarks(raw_text_needed=True)  # Save landmarks both in .npy format and also in raw text format for inspection
        
    def extract_landmarks(self, raw_text_needed=False):
        os.makedirs(os.path.join(self.data_path, "preprocessed", self.split), exist_ok=True)
        for class_name in self.classes[:-1] if self.use_none_class else self.classes:
            class_dir = os.path.join(self.split_dir, class_name)
            output_dir = os.path.join(self.data_path, "preprocessed", self.split, class_name)
            os.makedirs(output_dir, exist_ok=True)
            
            for image_name in sorted(os.listdir(class_dir)):
                image_path = os.path.join(class_dir, image_name)
                if not os.path.isfile(image_path) or not image_name.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
                    continue
                
                # Load the input image.
                image = mp.Image.create_from_file(image_path)
                if image is None:
                    continue

                results = self.mp_detector.detect(image)
                _, landmarks = face_get_XYZ(results, image_rgb=None)
                
                save_path = os.path.join(output_dir, os.path.splitext(image_name)[0])
                np.save(save_path, landmarks)
                
                # We test if raw text is needed, but we save the landmarks in .npy format for efficiency.
                if raw_text_needed:
                    with open(save_path + ".txt", "w") as f:
                        for point in landmarks:
                            f.write(f"{point[0]} {point[1]}\n")
                            
                        f.close()

    def classes_to_id(self, class_to_translate):
        return self.classes.index(class_to_translate)

    def apply_normalizations(self, landmarks):
        if "L0" in self.normalizations:
            landmarks = normalize_L0(landmarks)
        if "size" in self.normalizations:
            landmarks = normalize_size(landmarks)
        return landmarks

    def _load_landmarks(self, image_path):
        # Load the input image.
        image = mp.Image.create_from_file(image_path)
        if image is None:
            return np.zeros((478, 2), dtype=np.float32)

        results = self.mp_detector.detect(image)
        # We alert when no face is detected, but we still return a zeroed landmarks array for consistency.
        if results.face_landmarks is None and results.multi_face_landmarks is None:
            print(f"\n[WARNING] No face detected in image: {image_path}")
            return np.zeros((478, 2), dtype=np.float32)
        
        _, landmarks = face_get_XYZ(results, image_rgb=None)
        return np.asarray(landmarks, dtype=np.float32)

    def generator(self):
        idx = 0
        while idx < self.len_dataset:
            image_path, class_name = self.samples[idx]
            landmarks = self._load_landmarks(image_path)

            if np.sum(landmarks) == 0 and self.use_none_class:
                class_id = self.classes_to_id("None")
            else:
                class_id = self.classes_to_id(class_name)
                landmarks = self.apply_normalizations(landmarks)

            yield landmarks.astype(np.float32), np.float32(class_id)
            idx += 1


def prepare_my_dataloader(dataset_path, 
                          split="train",
                          batch_size=1, 
                          use_none_class=False, 
                          normalization=None, 
                          extract_landmarks=False):
    normalization = normalization or []

    my_dataset = MyDataset(
        dataset_path,
        split,
        use_none_class,
        normalization,
        extract_landmarks,
    )

    dataset_loader = tf.data.Dataset.from_generator(
        generator=my_dataset.generator,
        output_signature=(
            tf.TensorSpec(shape=(478, 2), dtype=tf.float32),
            tf.TensorSpec(shape=(), dtype=tf.float32),
        )
    )

    dataloader = dataset_loader.batch(batch_size).prefetch(tf.data.AUTOTUNE)
    return dataloader

if __name__ == "__main__":
    ANNOTATION_PATH = "data/RAVDESS/annotations_frames.csv"
    trainloader = prepare_dataloader(
        ANNOTATION_PATH,
        "train",
        4,
    )
    testloader = prepare_dataloader(ANNOTATION_PATH, "test", 4)

    print(next(iter(trainloader)))
    print(next(iter(testloader)))

    print("Dataloader works correctly")
