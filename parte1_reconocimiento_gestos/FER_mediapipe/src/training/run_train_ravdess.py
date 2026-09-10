# This file was used for the pretraining of some models on a larger set.

import sys
import keras
import numpy as np
from sklearn.metrics import confusion_matrix

sys.path.append(".")

import src.models.CNN as CNN
import src.models_definitions.VIT as VIT

from src.data_loader.ravdess_dataloader import prepare_dataloader

# from src.data_loader.FER_2013_dataloader import prepare_dataloader

ANNOT_PATH = "data/RAVDESS/annotations_frames.csv"
# DATA_PATH = "data/FER-2013"
NORM_TYPE = "L0_Size"
NUM_CLASSES = 8

# VIT HYPERPARAMETERS
PATCH_SIZE = (50, 2, 1)
PROJECTION_DIM = 64
NUM_LAYERS = 4
NUM_HEADS = 4


def create_model(model_name):
    if model_name == "CNN":
        model = CNN.create_cnn(num_classes=NUM_CLASSES)
    elif model_name == "MobileNet":
        model = CNN.create_MobileNet(num_classes=NUM_CLASSES)
    elif model_name == "VIT":
        model = VIT.create_vit_classifier(
            input_shape=(478, 2, 1),
            patch_size=PATCH_SIZE,
            projection_dim=PROJECTION_DIM,
            transformer_layers=NUM_LAYERS,
            num_heads=NUM_HEADS,
            transformer_units=[2 * PROJECTION_DIM, PROJECTION_DIM],
            mlp_head_units=[512, 256],
            num_classes=NUM_CLASSES,
        )
    else:
        raise ValueError("Model name not defined")

    return model


def main():
    trainloader = prepare_dataloader(
        ANNOT_PATH, split="train", batch_size=100, normalization=NORM_TYPE
    )
    testloader = prepare_dataloader(
        ANNOT_PATH, split="test", batch_size=100, normalization=NORM_TYPE
    )

    model = create_model("VIT")

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-4),
        loss=keras.losses.SparseCategoricalCrossentropy(),
        metrics=["accuracy"],
    )

    model.fit(
        x=trainloader,
        epochs=80,
        validation_data=testloader,
    )
    model.save("models/VIT.keras")

    y_true = np.concatenate([y for _, y in testloader], axis=0).astype(int)
    predictions = np.argmax(model.predict(testloader), axis=1).astype(int)

    conf_matrix = confusion_matrix(y_true, predictions)
    print(conf_matrix)


if __name__ == "__main__":
    main()
