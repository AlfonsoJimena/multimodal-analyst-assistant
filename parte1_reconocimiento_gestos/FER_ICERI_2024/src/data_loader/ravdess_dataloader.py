import pandas as pd
import cv2
import sys
import os
import numpy as np

sys.path.append(".")
from src.landmarks_utils import normalize_L0, normalize_size
import mediapipe as mp
import tensorflow as tf
from sklearn.model_selection import train_test_split


class RavdessDataloader:
    def __init__(
        self,
        annot_path,
        split,
        normalizations,
        random_seed,
    ):
        print("[Preparing dataloader]")

        self.annot_path = annot_path
        self.split = split
        print(f"\tSplit: {split}")
        self.random_seed = random_seed

        self.annotations = pd.read_csv(annot_path).sample(
            frac=1, random_state=random_seed
        )
        train, test = train_test_split(self.annotations, random_state=random_seed)

        print(
            f"\tTotal len: {len(self.annotations)}:\n\t\t- Train: {len(train)}\n\t\t- Test: {len(test)}"
        )

        self.data = train if self.split == "train" else test
        self.data_len = len(self.data)

        self.normalizations = normalizations
        print(f"Normalizations used: {normalizations}")

    def apply_normalizations(self, landmarks):
        if "L0" in self.normalizations:
            landmarks = normalize_L0(landmarks)
        if "size" in self.normalizations:
            landmarks = normalize_size(landmarks)
        return landmarks

    def generator(self):
        idx = 0
        while idx < self.data_len:
            frame_annotation = self.data.iloc[idx]
            frame_path = frame_annotation.loc["path"]
            landmarks_path = frame_path.replace("frames", "landmarks").replace(
                "jpg", "npy"
            )
            landmarks = np.load(landmarks_path)
            landmarks = self.apply_normalizations(landmarks)
            emotion_id = frame_annotation.loc["emotion"] - 1  # Emotions in range [0,7]
            yield landmarks, emotion_id
            idx += 1


def preprocess(landmarks, label):
    landmarks = tf.image.convert_image_dtype(
        landmarks[..., tf.newaxis], dtype=tf.float32
    )

    label = tf.cast(label, tf.float32)
    return landmarks, label


def prepare_dataloader(
    annotations_path, split, batch_size, normalization, random_seed=42
):
    dataset = RavdessDataloader(annotations_path, split, normalization, random_seed)
    dataloader = tf.data.Dataset.from_generator(
        generator=dataset.generator,
        output_signature=(
            tf.TensorSpec(
                shape=(478, 2), dtype=tf.float32
            ),  # Shape and type of the landmarks
            tf.TensorSpec(shape=(), dtype=tf.float32),  # Shape and type of the labels
        ),
    )

    dataloader = (
        dataloader.map(preprocess, num_parallel_calls=tf.data.AUTOTUNE)
        .batch(batch_size)
        .prefetch(tf.data.AUTOTUNE)
    )
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
