# Video de hasta un minuto

Preparación: iniciar el servidor con el comando del README; navegador a 100 %, ventana maximizada, cerrar notificaciones. Crear una sesión vacía y seleccionar los archivos antes de grabar. No hace falta narrar mientras se reproduce: el equipo explica las diapositivas después. El video aún debe grabarse; este documento es su guion.

| Tiempo | Acción | Qué demuestra |
|---|---|---|
| 0–10 s | Mostrar una muestra original ATM con monto null | Entrada sin limpiar |
| 10–18 s | Cerrar muestra y pulsar Ejecutar pipeline | Procesamiento real de archivos |
| 18–35 s | Recorrer las etapas confirmadas de ATM y DIGITAL | Diagnóstico, validación, catálogo, mediana, IQR y transformación |
| 35–45 s | Abrir Resultados y mostrar gráficas y tabla | 1,072 limpias, 128 cuarentena y 20 omitidas |
| 45–55 s | Buscar ATM-TX-00034 y abrir Ver | Original null y monto procesado 4,000 |
| 55–60 s | Cerrar detalle, quitar búsqueda y abrir Cuarentena | Rechazos con motivo conservado |

Si el equipo tarda más, ensayar el recorrido antes de grabar. No acelerar hasta volver ilegibles los textos ni fingir tiempos del pipeline. Las etapas aparecen al completar los lotes, no simulan avance en vivo. Para repetir desde cero, crear una sesión vacía y seleccionar de nuevo los archivos.

## Exposición de cinco minutos

- Maki: entrada y problemas, 40 segundos; reproducir video, 60 segundos.
- Avilix: técnicas y decisiones, 90 segundos. Imputación con mediana, IQR sobre monto analítico, USD × 19.50, MinMax y segmentos.
- Leo: salida, cuarentena, validación y commit/rollback, 60 segundos.
- Margen: 50 segundos para transición y cierre.


No decir que todos los nulos desaparecen, que un outlier se elimina, que limpio significa operación bancaria exitosa o que se comprobó estadísticamente MAR.

La página admite archivos elegidos por el usuario. Los conteos de este guion corresponden únicamente a los archivos originales del profesor. La selección requiere las columnas mostradas en Entrada; no interpreta automáticamente cualquier esquema arbitrario.
