from keras import Sequential
from keras.layers import Input, Conv2D, DepthwiseConv2D, Dropout, Flatten, MaxPool2D, Dense  # type: ignore
import keras


class MobileConv(keras.layers.Layer):
    def __init__(self, filters, kernel_size, padding, activation, **kwargs):
        super().__init__(**kwargs)
        self.dwconv = DepthwiseConv2D(
            kernel_size=kernel_size, padding=padding, activation=activation
        )
        self.pwconv = Conv2D(
            filters=filters, kernel_size=1, padding=padding, activation=activation
        )

    def call(self, x):
        x1 = self.dwconv(x)
        x2 = self.pwconv(x1)
        return x2


def create_cnn(num_classes, dropout_rate=0.1):
    model = Sequential()
    model.add(
        Conv2D(
            filters=128,
            kernel_size=(200, 2),
            padding="same",
            activation="relu",
            input_shape=(478, 2, 1),
            data_format="channels_last",
        )
    )
    model.add(MaxPool2D((4, 1), padding="same"))
    model.add(Dropout(dropout_rate))

    model.add(
        Conv2D(filters=128, kernel_size=(60, 2), padding="same", activation="relu")
    )
    model.add(MaxPool2D((4, 1), padding="same"))
    model.add(Dropout(dropout_rate))

    model.add(
        Conv2D(filters=128, kernel_size=(10, 2), padding="same", activation="relu")
    )

    model.add(Flatten())
    model.add(Dense(128))
    model.add(Dropout(dropout_rate))
    model.add(Dense(num_classes, activation="softmax"))

    model.build()

    print("[MODEL SUMMARY]")
    model.summary()

    return model


def create_MobileNet(num_classes, dropout_rate=0.1):
    model = Sequential()
    model.add(Input(shape=(478, 2, 1)))
    model.add(
        MobileConv(filters=128, kernel_size=(200, 2), padding="same", activation="relu")
    )
    model.add(MaxPool2D(pool_size=(4, 1), padding="same"))
    model.add(Dropout(dropout_rate))

    model.add(
        MobileConv(filters=128, kernel_size=(60, 2), padding="same", activation="relu")
    )
    model.add(MaxPool2D(pool_size=(4, 1), padding="same"))
    model.add(Dropout(dropout_rate))

    model.add(
        MobileConv(filters=128, kernel_size=(10, 2), padding="same", activation="relu")
    )
    model.add(MaxPool2D(pool_size=(4, 1), padding="same"))
    model.add(Dropout(dropout_rate))

    model.add(Flatten())
    model.add(Dense(128))
    model.add(Dropout(dropout_rate))
    model.add(Dense(num_classes, activation="softmax"))

    model.build()

    print("[MODEL SUMMARY]")
    model.summary()

    return model
