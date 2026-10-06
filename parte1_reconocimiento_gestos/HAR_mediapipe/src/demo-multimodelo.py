"""
Demo con webcam para probar los 8 modelos de reconocimiento de gestos.

Uso (desde cualquier carpeta):
    python3 HAR_mediapipe/src/demo-multimodelo.py --model ft1
    python3 HAR_mediapipe/src/demo-multimodelo.py --model svm --norm off

Teclas:  m = siguiente modelo   n = alternar normalizacion   q = salir
"""
import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np

SRC_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SRC_DIR.parent              # .../HAR_mediapipe
WORK_DIR = PROJECT_DIR.parent             # .../parte1_reconocimiento_gestos

# Orden alfabetico con el que se entrenaron; la clase 7 es NO_GESTURE ("None").
CLASSES = ['No_Ok', 'OK', 'Perfecto', 'Puno_de_frente', 'Spiderman', 'Uno', 'None']

# kind: keras | sklearn      shape: cnn (1,21,2,1) | flat (1,42) | seq (1,21,2)
# norm: normalizacion por defecto (True = restar la muneca, "L0").
MODELS = {
    'cnn1': dict(path='modelos/PIDS_6gestos_v1_CNN1_L0.keras', kind='keras', shape='cnn', norm=True),
    'cnn2': dict(path='modelos/PIDS_6gestos_v1_CNN2_L0.keras', kind='keras', shape='cnn', norm=True),
    'ft1':  dict(path='modelos/PIDS_6gestos_v1_FINE-TUNING1_L0.keras', kind='keras', shape='cnn', norm=True),
    'ft2':  dict(path='modelos/PIDS_6gestos_v1_FINE-TUNING2_L0.keras', kind='keras', shape='cnn', norm=True),
    'mlp':  dict(path='modelos/modelos_MLP/PIDS_6gestos_v1_MLP_L0.keras', kind='keras', shape='flat', norm=True),
    'svm':  dict(path='modelos/PIDS_6gestos_v1_SVM.pkl', scaler='modelos/PIDS_6gestos_v1_SVM_scaler.pkl',
                 kind='sklearn', shape='flat', norm=True),
    'rf':   dict(path='modelos/modelo_rf/PIDS_6gestos_v1_RANDOM-FOREST.pkl', kind='sklearn', shape='flat', norm=True),
}
ORDER = list(MODELS)


def load_model(name):
    """Carga el modelo (y el scaler si lo tiene) y devuelve un dict listo para predecir."""
    cfg = MODELS[name]
    path = PROJECT_DIR / cfg['path']
    if not path.exists():
        raise FileNotFoundError(f'No existe el modelo: {path}')
    entry = dict(cfg=cfg, scaler=None)
    if cfg['kind'] == 'keras':
        import keras
        entry['model'] = keras.models.load_model(path)
    else:
        import joblib
        entry['model'] = joblib.load(path)
        if 'scaler' in cfg:
            entry['scaler'] = joblib.load(PROJECT_DIR / cfg['scaler'])
    return entry


def prepare_input(landmark_values, shape, normalize, normalizer=None):
    """landmark_values: 21 pares [x, y] -> tensor con la forma que espera el modelo."""
    flat = np.asarray(landmark_values, dtype='float32').reshape(1, 42)   # x0,y0,x1,y1,...
    if normalize:
        flat = normalizer(flat).astype('float32')
    if shape == 'cnn':
        return flat.reshape(1, 21, 2, 1), flat
    if shape == 'seq':
        return flat.reshape(1, 21, 2), flat
    return flat, flat


def predict(entry, landmark_values, normalize, normalizer=None):
    """Devuelve (nombre_clase, confianza o None)."""
    cfg, model = entry['cfg'], entry['model']
    x, flat = prepare_input(landmark_values, cfg['shape'], normalize, normalizer)
    if cfg['kind'] == 'keras':
        probs = np.asarray(model(x, training=False))[0]
        return CLASSES[int(np.argmax(probs))], float(np.max(probs))
    if entry['scaler'] is not None:
        x = entry['scaler'].transform(x)
    label = int(model.predict(x)[0])
    idx = label - 1 if int(min(model.classes_)) == 1 else label
    conf = None
    try:
        conf = float(np.max(model.predict_proba(x)))
    except Exception:
        pass
    return CLASSES[idx], conf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', default='ft1', choices=ORDER)
    ap.add_argument('--norm', default='auto', choices=['auto', 'on', 'off'],
                    help='auto = la normalizacion con la que se entreno cada modelo')
    ap.add_argument('--debug', action='store_true')
    args = ap.parse_args()

    # Las rutas del proyecto son relativas a parte1_reconocimiento_gestos/
    os.chdir(WORK_DIR)
    for p in (str(WORK_DIR / 'common'), str(SRC_DIR)):
        if p not in sys.path:
            sys.path.append(p)

    import cv2
    import mediapipe as mp
    from cameras import CVCamera, CameraConfig
    from config import ConfigMediapipeDetector
    from gui import Colors, WindowMessage
    from landmarksLib import draw_landmarks_on_image, normalize_from_0_landmark

    colors = Colors()
    colors.SelectRandomColorFromListForClasses(CLASSES)
    cam_config = CameraConfig(FPS=15, resolution='highres')
    detector = ConfigMediapipeDetector('HAR_mediapipe/models/hand_landmarker.task')
    cam = CVCamera(recording_res=cam_config.resolution, index_cam=0)

    cache = {}
    current = args.model
    norm_override = {'auto': None, 'on': True, 'off': False}[args.norm]
    initial_override = norm_override   # lo que pidio el usuario con --norm

    def get_entry(name):
        if name not in cache:
            print(f'Cargando {name}...')
            cache[name] = load_model(name)
        return cache[name]

    entry = get_entry(current)
    cam.start()
    window_title = 'Demo multimodelo - gestos'
    pred, conf, last = 'None', 1.0, 0.0
    landmark_values = [[0, 0] for _ in range(21)]

    while True:
        image = cam.read_frame()
        if image is None:
            print('Waiting for camera input')
            continue

        normalize = entry['cfg']['norm'] if norm_override is None else norm_override

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        result = detector.detect(mp_image)

        if result.hand_landmarks:
            image, landmark_values = draw_landmarks_on_image(image, result)
            now = time.time()
            if now - last > 0.25:
                pred, conf = predict(entry, landmark_values, normalize, normalize_from_0_landmark)
                if args.debug:
                    arr = np.asarray(landmark_values, dtype='float32')
                    print(f'{current} norm={normalize} rango=[{arr.min():.2f},{arr.max():.2f}] -> {pred} {conf}')
                last = now
        else:
            pred, conf = 'None', None

        color = colors.color['black'] if pred == 'None' else colors.GetColorForClass(pred)
        conf_txt = '' if conf is None else ' (%0.2f)' % conf
        WindowMessage(
            txt1='Prediccion: ' + pred + conf_txt, pos1=(10, cam_config.resolution[1] - 20), col1=color,
            txt2='Modelo: %s | normalizacion: %s' % (current, 'ON' if normalize else 'OFF'),
            pos2=(10, 30), col2=colors.color['green'],
            txt3='m: modelo   n: normalizacion   q: salir', pos3=(10, 60), col3=colors.color['green'],
        ).ShowWindowMessages(image)
        cv2.imshow(window_title, image)

        key = cv2.waitKey(int(1 / cam_config.FPS * 1000)) & 0xFF
        if key == ord('q'):
            break
        if key == ord('m'):
            current = ORDER[(ORDER.index(current) + 1) % len(ORDER)]
            entry = get_entry(current)
            pred, conf = 'None', None
            norm_override = initial_override   # el toggle 'n' no se arrastra al modelo siguiente
        if key == ord('n'):
            norm_override = (not normalize)

    cam.stop()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
