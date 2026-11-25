# Verificación para la revisión del 25 de noviembre

| Criterio | Evidencia comprobada | Pendiente para excelente |
|---|---|---|
| Modelos · 25 | Pesos piloto propios. Última época de validación: M2 máscaras mAP50 0,677 y mAP50–95 0,522. M3 puntos mAP50 0,835 y mAP50–95 0,375. En prueba reservada el conteo exacto fue 1/5 y el error absoluto medio 0,8 ejes. OCR CCT acertó 13/13 recortes legibles seleccionados, con tomas repetidas. | Evaluación independiente por vehículo, más ejemplos de minibuses y pesados, OCR sobre video y mejora del conteo. |
| Web, API y BD · 15 | HTTPS público, PostgreSQL, historial protegido y exportación OpenAPI. En una BD aislada se verificaron cobro único con concurrencia, saldo, alertas, corrección y conservación del cobro al ocultar un paso. | Prueba de aceptación de todas las rutas con roles reales. |
| Tiempo real y Google · 10 | Eventos SSE comprobados por HTTP. Firebase confirma el proveedor Google. La cuenta docente especificada tiene rol ADMIN activo en producción. | Grabar el acceso autorizado y el rechazo de una cuenta fuera de lista en los dispositivos. |
| Agente · 20 | La búsqueda directa por placa normalizada consulta la BD; hay sugerencias y ruta de imagen con OCR. Cuatro estados probados con datos controlados por consulta de placa. | Configurar Qwen y comprobar los cuatro estados por ambas modalidades, incluida foto ilegible. |
| Android · 20 | APK disponible de una compilación anterior y capturas de una prueba real compartidas por el operador. | Medir latencia desde captura hasta panel y demostrar ambos modos con el APK final y video en movimiento. |
| Entrega · 10 | README, guion, PDF de avance, APK, JSON de OpenAPI y diagnósticos. | Video de 8–12 minutos, capturas completas, informe final, verificación del acceso docente a la carpeta compartida. |

## Bonificaciones
- Entornos: diagnóstico de API en VPS e inferencia en RunPod en la carpeta de entrega. El equipo de inferencia reportó una RTX 4090 y CUDA 12.8.
- RunPod: se verificó que el servicio responde con los modelos listos. La disponibilidad en la fecha de revisión y la grabación de una petición real siguen siendo necesarias.
- Pasajeros: la detección general de personas incluye peatones. El servicio ya devuelve una estimación por vehículo y la API la guarda y muestra en el panel. Faltan validación con anotaciones humanas y video con varios pasajeros. La evidencia para este bono debe usar solo máscaras o conteos.
- Hardware: falta evidencia de un dispositivo físico.

Los resultados de entrenamiento se incluyen en metricas_m2.csv y metricas_m3.csv. La suma cobrada usa solo pasos PAGADO. Ocultar un paso cambia la vista del panel y conserva sus movimientos de saldo.
