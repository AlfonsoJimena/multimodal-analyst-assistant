#!/bin/bash
# merge_dataset.sh
#
# Fusiona las carpetas raw_<persona>/ de cada miembro del equipo en un único
# dataset final, evitando colisiones de nombre de fichero al anteponer el
# nombre de la persona a cada imagen copiada.
#
# Uso:
#   ./merge_dataset.sh <carpeta_salida> <carpeta_persona_1> [<carpeta_persona_2> ...]
#
# Ejemplo (ejecutar desde parte1_reconocimiento_gestos/HAR_mediapipe/data/):
#   ./merge_dataset.sh new_dataset_final \
#       raw_carlos \
#       "Grabaciones PIDS/raw_Antonio" \
#       "Grabaciones PIDS/raw_guille" \
#       "Grabaciones PIDS/raw_Alfonso" \
#       "Grabaciones PIDS/raw_david"
#
# Cada <carpeta_persona_N> debe tener la estructura:
#   <carpeta_persona_N>/train/<gesto>/*.jpg
#   <carpeta_persona_N>/test/<gesto>/*.jpg

set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Uso: $0 <carpeta_salida> <carpeta_persona_1> [<carpeta_persona_2> ...]"
  exit 1
fi

OUT_DIR="$1"
shift
PERSON_DIRS=("$@")

mkdir -p "$OUT_DIR/train" "$OUT_DIR/test"

total_copiadas=0

for persona_dir in "${PERSON_DIRS[@]}"; do
  if [ ! -d "$persona_dir" ]; then
    echo "AVISO: no existe la carpeta '$persona_dir', se omite."
    continue
  fi

  # Nombre corto de la persona: cogemos el último componente de la ruta
  # y le quitamos el prefijo raw_ si lo tiene, para usarlo como prefijo de fichero.
  persona_base=$(basename "$persona_dir")
  persona_tag="${persona_base#raw_}"

  echo "=== Procesando $persona_dir (tag: $persona_tag) ==="

  for split in train test; do
    split_dir="$persona_dir/$split"
    if [ ! -d "$split_dir" ]; then
      echo "  AVISO: no existe $split_dir, se omite este split para esta persona."
      continue
    fi

    for clase_dir in "$split_dir"/*/; do
      [ -d "$clase_dir" ] || continue
      clase=$(basename "$clase_dir")

      dest_dir="$OUT_DIR/$split/$clase"
      mkdir -p "$dest_dir"

      n_clase=0
      for f in "$clase_dir"*.jpg; do
        [ -e "$f" ] || continue
        fname=$(basename "$f")
        cp "$f" "$dest_dir/${persona_tag}_${fname}"
        n_clase=$((n_clase+1))
      done

      echo "  $split/$clase: $n_clase imágenes copiadas"
      total_copiadas=$((total_copiadas+n_clase))
    done
  done
done

echo ""
echo "=== RESUMEN FINAL ($OUT_DIR) ==="
for split in train test; do
  echo "--- $split ---"
  for clase_dir in "$OUT_DIR/$split"/*/; do
    [ -d "$clase_dir" ] || continue
    clase=$(basename "$clase_dir")
    n=$(ls "$clase_dir" | wc -l)
    echo "  $clase: $n imágenes"
  done
done

echo ""
echo "Total de imágenes copiadas: $total_copiadas"
echo "Fusión completada en: $OUT_DIR"
