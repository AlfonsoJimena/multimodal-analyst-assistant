import os
import sys

# 1. Cambiar al directorio raíz del proyecto
# Load ~/workspace/IE-workspace/ directory
os.chdir('/Users/ffm/workspace/IE-workspace/')


# 2. Definir rutas ABSOLUTAS para evitar ambigüedades
root_path = os.getcwd()
path_har = os.path.join(root_path, "FER_mediapipe", "src")
path_common = os.path.join(root_path, "common")

# 3. Añadirlas al path y verificar si existen
for p in [path_har, path_common]:
    if p not in sys.path:
        sys.path.append(p)
    if not os.path.exists(p):
        print(f"⚠️ ¡OJO! La ruta no existe: {p}")
    else:
        print(f"✅ Ruta añadida: {p}")

# 4. Intentar la importación
try:
    import landmarks_utils
    print("🚀 landmarks_utils importado con éxito")
except ModuleNotFoundError as e:
    print(f"❌ Error: {e}")

try:
    import data_utils.ravdess_extract_landmarks
    print("🚀 data_utils.ravdess_extract_landmarks importado con éxito")
except ModuleNotFoundError as e:
    print(f"❌ Error: {e}")
    
try:
    import data_loader.custom_dataloader
    print("🚀 data_loader.custom_dataloader importado con éxito")
except ModuleNotFoundError as e:
    print(f"❌ Error: {e}")
    
    
root_path = r'FER_mediapipe/' # r'/content/IE-workspace/FER_mediapipe/'

# Folder where the input data is saved
data_path = root_path + r'data/'
new_dataset_path = data_path + r'my_faces_dataset/' # Change 'my_faces_dataset' as needed
new_dataset_annotations_path = new_dataset_path + r'annotations/'
new_dataset_landmarks_path = new_dataset_path + r'landmarks/'
dataset_path = {}
dataset_path['train'] = new_dataset_path + r'train/'
dataset_path['test'] = new_dataset_path + r'test/'

# Folder where the models are stored
models_path = root_path + r'models/'

# SUMMARY
print('data_path = ', data_path)
print('new_dataset_path = ', new_dataset_path)
print('new_dataset_annotations_path = ', new_dataset_annotations_path)
print('new_dataset_landmarks_path = ', new_dataset_landmarks_path)
print('dataset_path[train] = ', dataset_path['train'])
print('dataset_path[test] = ', dataset_path['test'])
print('models_path = ', models_path)


from data_loader.custom_dataloader import prepare_my_dataloader 

print("[Preparing dataloaders]")
# Prepare the dataloaders
batch_size = 8
use_none_class = False #True
normalization = ["L0", "size"]
#normalization = []

train_dataloader = prepare_my_dataloader(new_dataset_path, 
                                         split='train', 
                                         batch_size=batch_size, 
                                         use_none_class=use_none_class, 
                                         normalization=normalization, 
                                         extract_landmarks=False)
test_dataloader = prepare_my_dataloader(new_dataset_path, 
                                        split='test',
                                        batch_size=batch_size, 
                                        use_none_class=use_none_class,
                                        normalization=normalization,
                                        extract_landmarks=False)

from models.VIT import mlp, Patches, PatchEncoder
from models.models import define_network_model

import keras
import time
import numpy as np
from sklearn.metrics import confusion_matrix, accuracy_score, f1_score, roc_curve, auc
from keras.optimizers import AdamW
from keras.callbacks import EarlyStopping

print('\n[DefineNetworkModel]')

# Types: "CNN, VIT, TL (Transfer Learning)"
network_type = "CNN" 
#network_type = "VIT"
epochs = 30
models_folder = os.path.join(root_path, "models")
num_classes = len(os.listdir(os.path.join(new_dataset_path, 'train')))
num_cnn_features = 64
num_channels = 1
learning_rate=0.001

pretrained_model_path = os.path.join(models_folder, "cnn_size.keras")

if use_none_class: # REMEMBER: num_classes + 1 is to include the NO GESTURE class
    num_classes += 1

model = define_network_model(num_classes = num_classes, network_type = network_type, num_cnn_features = num_cnn_features, pretrained_model_path = pretrained_model_path)

# tf.keras.optimizers.SGD(lr=0.01, momentum=0.0, decay=0.0, nesterov=False)
# opt=tf.keras.optimizers.SGD(lr=0.001)
# opt=tf.keras.optimizers.RMSprop(lr=0.0005, rho=0.9, epsilon=1e-08, decay=0.0)
#opt = keras.optimizers.Adam(learning_rate=learning_rate)
#model.compile(loss="sparse_categorical_crossentropy", 
#              optimizer=opt,
#              metrics=['accuracy'])

opt = AdamW(learning_rate=0.001, weight_decay=1e-4)  # Ajusta el weight decay según el problema
model.compile(loss='categorical_crossentropy', optimizer=opt, metrics=['accuracy'])

print('\n[model.fit][Training starts!]\n')
start_time = time.time()
history = model.fit(train_dataloader,
                    epochs=epochs,
                    verbose=1)
end_time = time.time()
execution_time = end_time - start_time
print(f"\Training finished, execution time: {execution_time:.2f} s")


print('\n[PERFORMANCE ANALYSIS]')
print('[SETUP]')
#print('\t[Normalization: %s]' % norm_type)
print('\t[Type of network: %s]' % network_type)
print('\t[Num classes: %d]' % num_classes)

# For train data
print('=============================================\n')
print('[TRAIN]')
predictions = model.predict(train_dataloader, verbose = 1)
y_pred_train = np.argmax(predictions, axis=1)
y_true_train =np.concatenate([y for _, y in train_dataloader], axis=0).astype(int)
print('y_pred_train', y_pred_train)
print('y_true_train', y_true_train)
matrix = confusion_matrix(y_true_train, y_pred_train) #, labels=np.arange(1, num_classes + 1))

print('[Number of training examples = %d]' % matrix.sum())
print('\n[Confusion matrix for training data]')
print(matrix)
print('\n[Train accuracy = %0.4f]' % accuracy_score(y_true_train, y_pred_train))
print('[Train unweighted f-measure = %0.4f]' % f1_score(y_true_train, y_pred_train, average='macro'))
print('[Train weighted f-measure = %0.4f]' % f1_score(y_true_train, y_pred_train, average='weighted'))

# For test data
print('=============================================\n')
print('[TEST]')
prediction = model.predict(x = test_dataloader, verbose = 1)
y_pred_test = np.argmax(prediction, axis=1)
y_true_test = np.concatenate([y for _, y in test_dataloader], axis=0).astype(int)
num_test_samples = len(y_true_test)
print('y_pred_test', y_pred_test)
print('y_true_test', y_true_test)
matrix = confusion_matrix(y_true_test, y_pred_test) #, labels=np.arange(1, num_classes+1))

print('[Number of test examples = %d]' % matrix.sum())
print('\n[Confusion matrix for test data]')
print(matrix)
print('\n[Test accuracy = %0.4f]' % accuracy_score(y_true_test, y_pred_test))
print('[Test unweighted f-measure = %0.4f]' % f1_score(y_true_test, y_pred_test, average='macro'))
print('[Test weighted f-measure = %0.4f]' % f1_score(y_true_test, y_pred_test, average='weighted'))

try:
  if model_results:
    pass
except NameError:
  model_results = []

model_results.append({
    "model_type": network_type,
    "norm_type": normalization,
    "test_accuracy": accuracy_score(y_true_test, y_pred_test),
    "f-measure_unweighted": f1_score(y_true_test, y_pred_test, average='macro'),
    "f-measure_weighted": f1_score(y_true_test, y_pred_test, average='weighted'),
    "execution_time": execution_time,
    "num_test_samples": num_test_samples
  })

print("\n", model_results)