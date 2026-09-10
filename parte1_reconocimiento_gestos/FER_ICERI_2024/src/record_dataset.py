import time
import cv2
import os
import numpy as np
import pandas as pd

import sys
import tty
import termios

from cameras import CVCamera, PICamera

use_landmarks = True
if use_landmarks:
    import mediapipe as mp

    sys.path.append(".")
    from src.landmarks_utils import face_get_XYZ

# Array of class names
classes = ["Happy", "Sad", "Angry", "Surprise"]
num_classes = len(classes)

# Recording resolutions
HIGHRES_SIZE = (1280, 720)
LARGE_SIZE = (640, 480)
SMALL_SIZE = (320, 200)

# Base directory where the new dataset is going to be stored
DATASET_DIR = "data/my_faces_dataset_2"

# Total number of images per class in the dataset
NUM_IMAGES_PER_CLASS = 10

# Percentage of the recorded images that will be used for training (rest for test)
TRAINING_TEST_PERCENTAGE = 66

# RGB colors
GREEN = (0, 255, 0)
BLUE = (255, 0, 0)
RED = (0, 0, 255)

ON_RASPBERRY_PI = False


def wait_for_keypress(target_key, exit_key, yes_to_all_key):
    print(
        f"Press '{target_key}' to continue or '{exit_key}' to exit... ('{yes_to_all_key}') if YES to all..."
    )
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    yes_to_all_result = False

    try:
        tty.setraw(sys.stdin.fileno())
        while True:
            char = sys.stdin.read(1)
            if char == target_key:
                break
            elif char == yes_to_all_key:
                print("Yes to all...")
                yes_to_all_result = True
                break
            elif char == exit_key:
                print("Exiting...")
                sys.exit(0)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return yes_to_all_result


def CreateDefaultDatasetFolders(base_dataset_dir):
    yes_to_all_result = False

    # Create default dataset folders
    for c in classes:
        for subset in ["train", "test"]:
            new_dir = os.path.join(base_dataset_dir, "raw", subset, c)
            try:
                os.makedirs(new_dir)
            except:
                if yes_to_all_result:
                    continue

                print("\n[WARNING]\n")
                print("The following directory ALREADY EXISTS!!!!")
                print(new_dir)
                print("\n[WARNING]\n")

                print("Do you want to record more instances?")
                yes_to_all_result = wait_for_keypress("c", "q", "y")


def DisplayPreviewScreen(cam, class_to_record, mp_detector):
    cam.start()

    while True:  # Empieza a mostrar la imagen por pantalla pra que le usuario se prepare. Cuando se presiona la tecla s el sistema compienza a grabar.
        image_rgb = cam.read_frame()

        # Convert the image to RGB for Mediapipe
        # image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        if use_landmarks:
            # Process the image and get hand landmarks
            results = mp_detector.process(image_rgb)

            if results.multi_face_landmarks:
                image_rgb, landmark_values = face_get_XYZ(results, image_rgb)

        # image = cv2.flip(image,+1) #displays image in mirror format

        cv2.putText(
            image_rgb,
            "Class to be recorded: " + class_to_record,
            org=(70, 210),
            fontFace=2,
            fontScale=0.75,
            color=GREEN,
        )
        cv2.putText(
            image_rgb,
            "Get ready and press 's' to start recording",
            org=(70, 260),
            fontFace=2,
            fontScale=0.75,
            color=GREEN,
        )
        cv2.putText(
            image_rgb,
            "or 'q' to exit.",
            org=(70, 300),
            fontFace=2,
            fontScale=0.75,
            color=GREEN,
        )

        cv2.imshow("Gesture Recorder", image_rgb)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("s"):
            cam.stop()
            break
        elif key == ord("q"):
            exit()


def StartRecordingImages(cam, num_images_to_record, mp_detector=None):
    # num of images recorded counter
    n_recorded = 0
    recorded_images = []

    cam.start()

    started = time.time()
    last_save = started

    while True:
        # Read image
        image_rgb = cam.read_frame()

        # image_rgb=cv2.flip(image_rgb,+1) #displays image in mirror format

        now = time.time()

        # We save only one image every second
        if now - last_save > 1:
            image_rgb_nparray = np.ascontiguousarray(image_rgb, dtype=np.uint8)
            saved_image = np.copy(image_rgb_nparray)

            recorded_images.append(saved_image)
            last_save = now

            # We update the count of recorded images
            n_recorded += 1

        if now - last_save > 0.5:
            # Get image dimensions
            height, width, _ = image_rgb.shape

            # Draw bounding rectangle
            bounding_rect = [(10, 10), (width - 20, height - 20)]
            cv2.rectangle(image_rgb, bounding_rect[0], bounding_rect[1], RED, 2)

        if use_landmarks:
            # Process the image and get hand landmarks
            results = mp_detector.process(image_rgb)

            if results.multi_face_landmarks:
                image_rgb, landmark_values = face_get_XYZ(results, image_rgb)

        # add annotations and change frame to color red
        cv2.putText(
            image_rgb,
            "Recording in progress...",
            org=(20, 40),
            fontFace=2,
            fontScale=0.65,
            color=RED,
        )
        cv2.putText(
            image_rgb,
            "Stored images: " + str(n_recorded + 1) + "/" + str(num_images_to_record),
            org=(20, 80),
            fontFace=2,
            fontScale=0.55,
            color=RED,
        )

        cv2.imshow("Gesture Recorder", image_rgb)

        if n_recorded >= num_images_to_record:
            cam.stop()
            time.sleep(1)
            break

        key = cv2.waitKey(1) & 0xFF

        # if the `q` key was pressed, break from the loop
        if key == ord("q"):
            break

    return recorded_images


def SaveRecordedImagesToDisk(recorded_images, class_to_save, num_samples_per_class):
    for subset in ["train", "test"]:
        if subset == "train":
            ini = 0
            end = num_samples_per_class["train"]
        else:
            ini = num_samples_per_class["train"]
            end = num_samples_per_class["train"] + num_samples_per_class["test"]

        saved_images = sorted(
            os.listdir(os.path.join(DATASET_DIR, "raw", subset, class_to_save))
        )
        if len(saved_images) > 0:
            last_saved_idx = int(saved_images[-1].split(".")[0].split("_")[-1])
        else:
            last_saved_idx = 0

        annot_path = os.path.join(DATASET_DIR, f"{subset}_annotations.csv")
        if os.path.isfile(
            annot_path
        ):  # If exists, append new data to the existing file
            annotations = pd.read_csv(annot_path)
        else:
            annotations = pd.DataFrame(columns=["path", "class"])

        for i in range(ini, end):
            name = (
                class_to_save
                + "_"
                + subset
                + "_"
                + f"{last_saved_idx+i-ini+1:05d}"
                + ".jpg"
            )
            filename = os.path.join(DATASET_DIR, "raw", subset, class_to_save, name)
            # save image in dataset
            cv2.imwrite(filename, recorded_images[i])
            new_row = pd.Series(
                {
                    "path": os.path.join(subset, class_to_save, name),
                    "class": class_to_save,
                }
            )
            annotations = pd.concat(
                [annotations, new_row.to_frame().T], ignore_index=True
            )
            print("Recorded ", filename)

        annotations.to_csv(annot_path, index=False)


def main():
    num_samples_per_class = {}
    num_samples_per_class["train"] = int(
        NUM_IMAGES_PER_CLASS * TRAINING_TEST_PERCENTAGE / 100
    )
    num_samples_per_class["test"] = (
        NUM_IMAGES_PER_CLASS - num_samples_per_class["train"]
    )
    num_samples_per_class["total"] = NUM_IMAGES_PER_CLASS

    print("\n[NEW DATASET RECORDING]")
    print("\t- %d classes: " % num_classes, classes)
    print(
        "\t- %d samples per class (%d samples in TOTAL)"
        % (num_samples_per_class["total"], num_classes * num_samples_per_class["total"])
    )
    print(
        "\t- %d samples for training (i.e. %0.2f%%) and %d for testing (i.e. %0.2f%%)"
        % (
            num_samples_per_class["train"],
            TRAINING_TEST_PERCENTAGE,
            num_samples_per_class["test"],
            100 - TRAINING_TEST_PERCENTAGE,
        )
    )

    CreateDefaultDatasetFolders(DATASET_DIR)
    # cv2.startWindowThread()

    if use_landmarks:
        # Initialize Mediapipe
        print("Initializing Mediapipe")
        mp_face = mp.solutions.face_mesh
        mp_detector = mp_face.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
        )
    else:
        mp_detector = None

    # Start camera, use CVCamera if working on a laptop and PICamera in case you are working on a Raspberry PI
    if ON_RASPBERRY_PI:
        cam = PICamera(recording_res=HIGHRES_SIZE)
    else:
        cam = CVCamera(recording_res=HIGHRES_SIZE, index_cam=1)

    # Main loop
    for c in classes:
        print("\nPREPARING TO RECORD CLASS:", c)

        DisplayPreviewScreen(cam, c, mp_detector=mp_detector)

        recorded_images = StartRecordingImages(
            cam,
            num_images_to_record=num_samples_per_class["total"],
            mp_detector=mp_detector,
        )

        SaveRecordedImagesToDisk(recorded_images, c, num_samples_per_class)

    print("\n[RECORDING FINISHED SUCCESSFULLY!!!]\n")

    # Release resources
    cv2.destroyAllWindows()
    if use_landmarks:
        mp_detector.close()
    cam.close()


if __name__ == "__main__":
    main()
