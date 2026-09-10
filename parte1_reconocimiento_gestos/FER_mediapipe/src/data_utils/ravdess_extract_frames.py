import os
import cv2
from tqdm import tqdm
import pandas as pd

DATA_PATH = "data/RAVDESS/videos/"
frames_save_dir = "data/RAVDESS/frames"

annotations = pd.DataFrame([],columns=["path", "emotion", "intensity", "repetition", "actor", "gender"])

for actor in tqdm(os.listdir(DATA_PATH), desc="Processing actors"):
    actor_path = os.path.join(DATA_PATH, actor)
    for video_name in os.listdir(actor_path):
        video_name = video_name.split(".")[0]
        os.makedirs(os.path.join(frames_save_dir, actor, video_name), exist_ok=True)
        video_path = os.path.join(actor_path, f"{video_name}.mp4")
        cap = cv2.VideoCapture(video_path)
        frame_idx = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            filename = os.path.join(frames_save_dir, actor, video_name, f"frame_{frame_idx:0>4}.jpg")
            cv2.imwrite(filename, frame)
            frame_idx += 1