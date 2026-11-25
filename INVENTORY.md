# Inventario de insumos
- El repositorio comenzó vacío. Fuentes verificadas en Descargas y en la ruta indicada de OneDrive.
- Especificación original y transcripción de trabajo en docs/Especificacion.txt.
- notebooks_h4 contiene introducción a Detectron2, servidores Colab y RunPod de pose humana y segmentación de cuatro categorías.
- training/keypoints_llantas_yolo_detectron2_v3.ipynb conserva el ejercicio docente. training/Llantas_LaPaz.ipynb añade importación revisada y descarga.
- FotosDeAutosLaPaz.zip contiene 300 JPEG de 1280 × 562. datasets/inventario.csv conserva nombre, huella y original seleccionado para cada imagen.
- best.tflite y best_int8.tflite de Descargas declaran ulupica como clase en sus metadatos. yolo11s_float32.tflite declara emociones faciales. Queda pendiente localizar el M1 de placas bolivianas.
- Entorno local: Windows, RTX 4060 Laptop de 8188 MiB, Torch CPU, PostgreSQL 18 y Node 22. Compose especifica PostgreSQL 16 para la nube. El comando docker no está disponible en la sesión local.
- Firebase, VPS, RunPod, Qwen y EAS pendientes de vinculación y pruebas externas. No se almacenaron claves en los paquetes.
- Hallazgo posterior dentro de placas-web_v2.zip: detector YOLOv9-t ONNX de 7.771.218 bytes y lector CCT del ejercicio. El detector se recuperó y ejecutó con 279 imágenes. No se estableció que sea un YOLO11 entrenado por el estudiante.
