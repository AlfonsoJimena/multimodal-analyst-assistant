"""
Evalua los modelos con las imagenes de test usando EXACTAMENTE el mismo camino
que el demo (MediaPipe -> landmarks -> normalizacion -> modelo), sin camara.

Uso:
    python3 HAR_mediapipe/src/evaluar-modelos.py --data <ruta>/new_dataset_final/test
    python3 HAR_mediapipe/src/evaluar-modelos.py --data <ruta> --models mlp lstm svm rf --both-norm
"""
import argparse
import importlib.util
import os
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent


def load_demo():
    spec = importlib.util.spec_from_file_location('demo_multimodelo', SRC_DIR / 'demo-multimodelo.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def evaluate(demo, names, samples, normalizer, both_norm=False):
    """samples: lista de (gesto_real, landmark_values). Devuelve una fila por modelo y modo."""
    rows = []
    for name in names:
        print(f'Evaluando {name}...')
        entry = demo.load_model(name)
        default = entry['cfg']['norm']
        for norm in ([True, False] if both_norm else [default]):
            hits = {g: [0, 0] for g in demo.CLASSES[:6]}          # [aciertos, total]
            conf = {}
            for true, lm in samples:
                pred, _ = demo.predict(entry, lm, norm, normalizer)
                hits[true][1] += 1
                conf[(true, pred)] = conf.get((true, pred), 0) + 1
                hits[true][0] += int(pred == true)
            ok = sum(h[0] for h in hits.values())
            tot = sum(h[1] for h in hits.values())
            rows.append(dict(model=name, norm=norm, default=(norm == default),
                             acc=100.0 * ok / max(tot, 1), n=tot,
                             per={g: 100.0 * h[0] / max(h[1], 1) for g, h in hits.items()}, conf=conf))
    return rows


def print_table(rows, classes):
    head = f"{'modelo':<10}{'norm':<7}{'acc %':>7}{'n':>6}  " + "  ".join(f"{g[:8]:>8}" for g in classes)
    print('\n' + head)
    print('-' * len(head))
    for r in rows:
        tag = ('ON' if r['norm'] else 'OFF') + ('' if r['default'] else ' *')
        print(f"{r['model']:<10}{tag:<7}{r['acc']:>7.2f}{r['n']:>6}  "
              + "  ".join(f"{r['per'][g]:>8.1f}" for g in classes))
    if any(not r['default'] for r in rows):
        print('\n* = normalizacion contraria a la usada en el entrenamiento')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True, help='carpeta test/ con una subcarpeta por gesto')
    ap.add_argument('--models', nargs='*', default=None)
    ap.add_argument('--both-norm', action='store_true', help='evalua cada modelo con normalizacion ON y OFF')
    ap.add_argument('--max', type=int, default=0, help='maximo de imagenes por gesto (0 = todas)')
    ap.add_argument('--confusion', action='store_true', help='imprime la matriz de confusion de cada modelo')
    args = ap.parse_args()

    data = Path(args.data).expanduser().resolve()      # antes de cambiar de carpeta
    demo = load_demo()
    names = args.models or demo.ORDER

    os.chdir(demo.WORK_DIR)
    for p in (str(demo.WORK_DIR / 'common'), str(SRC_DIR)):
        if p not in sys.path:
            sys.path.append(p)

    import cv2
    import mediapipe as mp
    from config import ConfigMediapipeDetector
    from landmarksLib import draw_landmarks_on_image, normalize_from_0_landmark

    detector = ConfigMediapipeDetector('HAR_mediapipe/models/hand_landmarker.task')

    samples, skipped = [], 0
    for g in demo.CLASSES[:6]:
        files = sorted((data / g).glob('*.jpg'))
        if args.max:
            files = files[:args.max]
        for f in files:
            img = cv2.imread(str(f))
            if img is None:
                skipped += 1
                continue
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            res = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
            if not res.hand_landmarks:
                skipped += 1
                continue
            _, lm = draw_landmarks_on_image(img, res)     # mismos landmarks que ve el demo
            samples.append((g, lm))
    print(f'{len(samples)} imagenes con mano detectada, {skipped} sin deteccion')

    rows = evaluate(demo, names, samples, normalize_from_0_landmark, args.both_norm)
    print_table(rows, demo.CLASSES[:6])
    if args.confusion:
        for r in rows:
            print(f"\nConfusion: {r['model']} (norm {'ON' if r['norm'] else 'OFF'}) - filas = gesto real, columnas = prediccion")
            print(' ' * 16 + ''.join(f'{c[:8]:>9}' for c in demo.CLASSES))
            for g in demo.CLASSES[:6]:
                print(f'{g:<16}' + ''.join(f"{r['conf'].get((g, c), 0):>9}" for c in demo.CLASSES))


if __name__ == '__main__':
    main()
