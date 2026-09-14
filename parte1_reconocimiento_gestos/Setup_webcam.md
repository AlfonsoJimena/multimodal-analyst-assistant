# Guía rápida: poner en marcha HAR_mediapipe en Windows con webcam

Los fixes de código (`gui.py`, `demo-custom-dataset.py`, `landmarksLib.py`) ya están aplicados en el repo. Con hacer `git pull` los tenéis. Aquí solo los pasos de terminal para dejar el entorno funcionando.

---

## 0. Requisitos

- Git y Python 3.11 (64 bits) instalados.
- Usar **PowerShell**.

⚠️ Si vuestro repo está dentro de OneDrive, crear el venv **fuera** de esa carpeta (OneDrive puede corromper/ralentizar el `venv` al intentar sincronizarlo).

---

## 1. Clonar el repo

```powershell
git clone <URL_DEL_REPO>
cd <carpeta_del_repo>
```

## 2. Crear y activar el entorno virtual

```powershell
python -m venv C:\Users\<TU_USUARIO>\venvs\multimodal-analyst-assistant
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& "C:\Users\<TU_USUARIO>\venvs\multimodal-analyst-assistant\Scripts\Activate.ps1"
```

**Comprobar que está activo de verdad:** el prompt debe pasar a
```
(multimodal-analyst-assistant) PS C:\...>
```
Si no aparece, no está activo. Verificación extra:
```powershell
Get-Command python | Select-Object -ExpandProperty Source
```
Debe apuntar al venv, no a `C:\Python311\...`.

## 3. Instalar dependencias

```powershell
python -m ensurepip --upgrade
python -m pip install --upgrade pip

cd "parte1_reconocimiento_gestos"
python -m pip install -r HAR_mediapipe\requirements-HAR_mediapipe.txt --no-cache-dir --only-binary=:all:
```

El flag `--only-binary=:all:` evita que pip intente compilar paquetes sin wheel de Windows (necesitaría Visual Studio Build Tools). Si os sale un `ERROR: Could not find a version that satisfies...` para algún paquete, avisad — hay que ajustar ese pin en el `requirements.txt` (ya hicimos esto con `matplotlib` y `tensorflow-io-gcs-filesystem`, así que si el repo está actualizado no debería pasar).

## 4. Actualizar Keras

```powershell
python -m pip install --upgrade keras
```

(El modelo pre-entrenado del repo se guardó con una Keras más reciente que la fijada en `requirements.txt`.)

## 5. Ejecutar

**Importante:** ejecutar siempre desde `parte1_reconocimiento_gestos` (no desde dentro de `HAR_mediapipe`), porque las rutas del código son relativas a esa carpeta.

```powershell
cd "<ruta_a_tu_repo>\parte1_reconocimiento_gestos"
python HAR_mediapipe\src\demo-custom-dataset.py
```

Debería abrirse la ventana con vuestra webcam, dibujar el esqueleto de la mano y mostrar la predicción de gesto. Pulsar `q` para cerrar.

---

## Checklist

- [ ] `git pull` hecho (para tener los fixes de código)
- [ ] Venv creado fuera de OneDrive
- [ ] Venv activado (prompt con el prefijo entre paréntesis)
- [ ] `pip install -r ... --only-binary=:all:` sin errores
- [ ] `pip install --upgrade keras` ejecutado
- [ ] Ejecutado desde `parte1_reconocimiento_gestos`, no desde `HAR_mediapipe`

## Siguientes pasos

1. Editar `HAR_mediapipe/src/record_dataset.py`: vuestras clases (mín. 5 gestos), carpeta destino, nº de muestras.
2. `python HAR_mediapipe\src\record_dataset.py` para grabar con la webcam.
3. Subir el notebook `HAR_mediapipe/src/notebooks/HAR_mediapipe.ipynb` + dataset a Drive, entrenar en Colab.
4. Descargar el `.keras` entrenado a `HAR_mediapipe/models/`.
5. Duplicar `demo-custom-dataset.py`, apuntar `MODEL_PATH` al nuevo modelo y actualizar `classes` (orden alfabético).
6. Ejecutar vuestro demo.
