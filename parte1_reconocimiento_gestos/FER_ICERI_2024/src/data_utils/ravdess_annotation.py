import os
from tqdm import tqdm
import pandas as pd

DATA_PATH = "data/RAVDESS/videos/"
annot_save_path = "data/RAVDESS/annotations.csv"

annotations = pd.DataFrame([],columns=["path", "emotion", "intensity", "repetition", "actor", "gender"])

for actor in tqdm(os.listdir(DATA_PATH), desc="Processing actors"):
    actor_path = os.path.join(DATA_PATH, actor)
    for video_name in os.listdir(actor_path):
        video_annotations = video_name.split(".")[0].split("-")
        
        if int(video_annotations[0]) != 2:
            continue
        
        video_path = os.path.join(actor_path, video_name)
        emotion = int(video_annotations[2])
        intensity = int(video_annotations[3])
        repetition = int(video_annotations[5])
        actor = int(video_annotations[6])
        gender = "Female" if actor % 2 == 0 else "Male"
        video_data = pd.Series({
            "path": video_path,
            "emotion": emotion,
            "intensity": intensity,
            "repetition": repetition,
            "actor": actor,
            "gender": gender
        })
        annotations = pd.concat((annotations, video_data.to_frame().T), ignore_index=True)
        
annotations.to_csv(annot_save_path, index=False)
