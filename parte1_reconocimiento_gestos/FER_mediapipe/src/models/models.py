import keras
from keras import layers
from keras.models import Sequential
from models.VIT import mlp, Patches, PatchEncoder

def define_network_model(
    num_classes,
    network_type,
    input_shape = (478,2,1),
    num_cnn_features=64,
    patch_size = (30,2, 1),
    vit_projection_dim = 64,
    vit_layers = 4,
    vit_n_heads = 4,
    vit_transformer_units = [128, 64],
    vit_mlp_head_units = [256, 128],
    pretrained_model_path = None,
    dropout = 0.1
  ):

  print('Model creation:')
  print(f'\tnetwork_type = {network_type}')
  print(f'\tnum_classes = {num_classes}')
  print(f'\tdropout = {dropout}')

  if (network_type == "CNN"):
    # We start by adding a convolutional layer to our model
    # arg 1: Number of filters (features) that the convolutional layer will learn.
    #   Each filter extracts different features from the input.
    # arg 2: Filter size in the form (height, width). In this case, it's a filter with a height of 5 and a width of 1.
    #   The height usually captures vertical details, and the width captures horizontal details.
    # arg 3: The padding parameter controls how the image border is handled.
    #   'same' ensures that the output size is the same as the input size by padding with zeros if needed.
    # arg 4: This is the shape of the input data. num_channels refers to the number of channels
    #   (typically 1 for grayscale or 3 for RGB color images), and here it's set to one as the landmarks are stored in a (478, 2, 1) tensor.
    # arg 5: This specifies the activation function to use after applying the convolution.
    #   'relu' is a common activation function that sets negative values to zero and leaves positive values unchanged.
    print(f'\tnum_cnn_features = {num_cnn_features}')
    model = Sequential(name = "CNN")
    model.add(layers.Input(shape=input_shape))
    model.add(
        layers.Conv2D(
            filters=num_cnn_features,
            kernel_size=(200, 2),
            padding="same",
            activation="relu",
            data_format="channels_last",
        )
    )
    model.add(layers.MaxPool2D((4, 1), padding="same"))
    model.add(layers.Dropout(dropout))

    model.add(
        layers.Conv2D(filters=num_cnn_features, kernel_size=(60, 2), padding="same", activation="relu")
    )
    model.add(layers.MaxPool2D((4, 1), padding="same"))
    model.add(layers.Dropout(dropout))

    model.add(
        layers.Conv2D(filters=num_cnn_features, kernel_size=(10, 2), padding="same", activation="relu")
    )
    model.add(layers.Dropout(dropout))

    model.add(layers.Flatten())
    model.add(layers.Dense(128))
    model.add(layers.Dropout(dropout))
    model.add(layers.Dense(num_classes, activation="softmax"))
    model.build()

  elif (network_type == "VIT"):
    # Obtain the total number of patches
    num_patches = 1
    for i in range(len(input_shape)):
        num_patches *= input_shape[i] // patch_size[i]

    inputs = keras.Input(shape=input_shape)
    # Create patches.
    patches = Patches(patch_size)(inputs)
    # Encode patches.
    encoded_patches = PatchEncoder(num_patches, vit_projection_dim)(patches)

    # Create multiple layers of the Transformer block.
    for _ in range(vit_layers):
        # Layer normalization 1.
        x1 = layers.LayerNormalization(epsilon=1e-6)(encoded_patches)
        # Create a multi-head attention layer.
        attention_output = layers.MultiHeadAttention(
            num_heads=vit_n_heads, key_dim=vit_projection_dim, dropout=0.1
        )(x1, x1)
        # Skip connection 1.
        x2 = layers.Add()([attention_output, encoded_patches])
        # Layer normalization 2.
        x3 = layers.LayerNormalization(epsilon=1e-6)(x2)
        # MLP.
        x3 = mlp(x3, hidden_units=vit_transformer_units, dropout_rate=0.1)
        # Skip connection 2.
        encoded_patches = layers.Add()([x3, x2])

    # Create a [batch_size, projection_dim] tensor.
    representation = layers.LayerNormalization(epsilon=1e-6)(encoded_patches)
    representation = layers.Flatten()(representation)
    representation = layers.Dropout(0.5)(representation)
    # Add MLP.
    features = mlp(representation, hidden_units=vit_mlp_head_units, dropout_rate=0.5)
    # Classify outputs.
    output = layers.Dense(num_classes, activation="softmax")(features)
    # Create the Keras model.
    model = keras.Model(inputs=inputs, outputs=output)

  elif (network_type == "TL"):
    print(f'\tpretrained model path: {pretrained_model_path}')
    base_model = keras.models.load_model(filepath=pretrained_model_path)
    base_model.trainable=False
    base_model_layers = base_model.layers

    inputs = layers.Input(shape=(478,2,1))
    x = base_model_layers[0](inputs)
    for layer in range(1, len(base_model_layers)-1):
        x = base_model_layers[layer](x)

    outputs = layers.Dense(num_classes, activation="softmax", name="classification_head")(x)
    model = keras.Model(inputs, outputs)

  else:
    raise ValueError("Network type not recognized")


  print('\n[MODEL SUMMARY]')
  model.summary(show_trainable=True)

  return model