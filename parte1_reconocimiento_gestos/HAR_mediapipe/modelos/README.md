# Modelos de reconocimiento de gestos (Parte 1)

Seis gestos (`No_Ok`, `OK`, `Perfecto`, `Puno_de_frente`, `Spiderman`, `Uno`) más la clase `NO_GESTURE` (7 salidas en total). La entrada de todos los modelos son los landmarks de MediaPipe Hands: 21 puntos con coordenadas x e y (42 valores por imagen).

## Resultados

Accuracy sobre las mismas 338 imágenes de test con mano detectada (de 342), con el mismo preprocesado que usa el demo (`src/evaluar-modelos.py`):

| Modelo | Fichero (en `modelos/`) | Preprocesado de entrenamiento | Accuracy test |
|---|---|---|---|
| CNN1 | `PIDS_6gestos_v1_CNN1_L0.keras` | L0 | 99,41 % |
| CNN2 | `PIDS_6gestos_v1_CNN2_L0.keras` | L0 | 89,64 % |
| FINE-TUNING1 | `PIDS_6gestos_v1_FINE-TUNING1_L0.keras` | L0 | 99,41 % |
| FINE-TUNING2 | `PIDS_6gestos_v1_FINE-TUNING2_L0.keras` | L0 | 99,41 % |
| MLP | `modelos_MLP/PIDS_6gestos_v1_MLP_L0.keras` | L0 | 99,41 %* |
| SVM | `PIDS_6gestos_v1_SVM.pkl` + `PIDS_6gestos_v1_SVM_scaler.pkl` | L0 + StandardScaler | 96,15 % |
| Random Forest | `modelo_rf/PIDS_6gestos_v1_RANDOM-FOREST.pkl` | L0 | 94,08 % |

\* MLP: cifra de la matriz de confusión del notebook en Colab sobre estas mismas 338 imágenes (sin contar `NO_GESTURE`), no de `evaluar-modelos.py`. Falta confirmarla con el script.

Acierto por gesto (%). Imágenes por gesto: 57, 55, 56, 57, 57 y 56.

| Modelo | No_Ok | OK | Perfecto | Puno_de_frente | Spiderman | Uno |
|---|---|---|---|---|---|---|
| CNN1 | 100,0 | 98,2 | 100,0 | 100,0 | 100,0 | 98,2 |
| CNN2 | 100,0 | 98,2 | 100,0 | 93,0 | 54,4 | 92,9 |
| FINE-TUNING1 | 100,0 | 98,2 | 100,0 | 100,0 | 100,0 | 98,2 |
| FINE-TUNING2 | 100,0 | 100,0 | 100,0 | 100,0 | 100,0 | 96,4 |
| MLP | 100,0 | 98,2 | 100,0 | 100,0 | 100,0 | 98,2 |
| SVM | 100,0 | 90,9 | 100,0 | 100,0 | 93,0 | 92,9 |
| Random Forest | 100,0 | 92,7 | 92,9 | 100,0 | 87,7 | 91,1 |

## Preprocesado

- **L0:** se resta la posición de la muñeca (landmark 0) al resto de landmarks; la muñeca queda sin cambios (`normalize_from_0_landmark` en `landmarksLib.py`). Un modelo entrenado con L0 se hunde si recibe los datos sin normalizar (comprobado con `evaluar-modelos.py --both-norm`).
- **MLP:** reentrenado con L0 el 5 de octubre de 2026 (#135). El modelo anterior, `modelos_MLP/PIDS_v1_MLP.keras`, se entrenó sin normalizar por la misma errata (99,11 % sin normalizar, 46,75 % normalizando) y se conserva para comparar; el demo ya no lo usa.
- **SVM:** además de L0 usa `StandardScaler`. Hay que cargar siempre `PIDS_6gestos_v1_SVM_scaler.pkl` junto con el modelo.

## Notas

- Los cuatro CNN y el MLP se entrenaron primero sin normalizar por una errata en el notebook (`"LO"` con letra O en lugar de `"L0"`, así que la condición `norm_type == "L0"` nunca se cumplía). Las CNN se reentrenaron con L0 el 4 de octubre de 2026 (#134) y el MLP el 5 (#135). Los ficheros antiguos de las CNN se retiraron (siguen en el historial de git); el del MLP se conserva.
- Cifras de Colab (394 muestras de test, incluidas 56 de `NO_GESTURE` sintéticas que todos aciertan): CNN1, FT1, FT2 y MLP 99,49 %; CNN2 91,12 %.
- Tiempos de entrenamiento en Colab (GPU T4, misma sesión): CNN1 129 s, FT1 62 s, FT2 59 s, CNN2 131 s (300 épocas, `patience = 300`). MLP 43 s (sesión aparte; early stopping con `patience = 50`, paró en la época 173). FT1 y FT2 parten de los pesos de `CNN1_L0`.
- Se evaluó también un LSTM que se descartó: no funcionaba con este preprocesado (10,7 %).

## Limitaciones

- El reparto train/test se hace por orden de captura dentro de cada sesión (el 70 % inicial para train y el 30 % final para test), así que train y test comparten participantes y sesiones. La accuracy mide el acierto con las mismas personas y condiciones, no con personas nuevas.
- El test también se usó como validación para el early stopping de los modelos Keras, por lo que las cifras pueden ser algo optimistas. No hay un tercer conjunto independiente.
- 4 de las 342 imágenes de test no se usan porque MediaPipe no detecta la mano.

## Cómo probarlos

El entorno probado está en `requirements-demo.txt` (Python 3.12, Ubuntu 24.04 en WSL2). El dataset está en Drive (`Grabaciones PIDS/new_dataset_final.zip`). Desde la carpeta `parte1_reconocimiento_gestos/`:

    python3 HAR_mediapipe/src/demo-multimodelo.py --model ft1
    python3 HAR_mediapipe/src/evaluar-modelos.py --data <ruta>/new_dataset_final/test --both-norm

Modelos disponibles: `cnn1`, `cnn2`, `ft1`, `ft2`, `mlp`, `svm`, `rf`. En el demo, `m` pasa al siguiente modelo, `n` activa o desactiva la normalización y `q` sale. En WSL la webcam se comparte con `usbipd attach --wsl --busid <id>` (PowerShell como administrador).

`src/landmarksLib.py` del equipo está adaptada a MediaPipe 0.10 (`mp.solutions`). Con MediaPipe 1.0.x (el del entorno probado) hay que usar la versión de la asignatura, que solo difiere en el dibujo de la mano. Se descarga así y no se sube al repositorio:

    curl -L -o HAR_mediapipe/src/landmarksLib.py https://raw.githubusercontent.com/efhes/IE-workspace/master/HAR_mediapipe/src/landmarksLib.py
