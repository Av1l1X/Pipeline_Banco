# Pipeline Banco

Pipeline ETL académico de Avilix, Maki y Leo: archivos → validación y limpieza → transformación → SQLite → resultados. Los datos ATM y digitales son fuentes; no hay simuladores ni ingreso individual de operaciones.

## Abrir la página

Con Python 3.12, solo la primera vez:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

Desde la carpeta del proyecto, ejecuta:

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8765
```

Abre http://127.0.0.1:8765. Mantén la terminal abierta. Ctrl+C detiene el servidor. Si ya tienes un servidor anterior activo, detenlo antes de reiniciar con este código.

## Entrada, Proceso y Resultados

La barra lateral comienza compacta. El botón de menú la abre y la cierra. Las tres vistas también se seleccionan con los pasos superiores.

1. En **Entrada**, elige el tipo de datos y arrastra o selecciona tus propios archivos. Puedes agregar varios lotes y revisar una muestra de cada uno.
2. Si la sesión no tiene catálogo, agrega uno de tipo **Catálogo de cuentas**. Puedes usar cualquier nombre de archivo, respetando las columnas indicadas en la interfaz.
3. Pulsa **Ejecutar pipeline**. Se procesa primero el catálogo y después cada lote. Si un archivo falla, se detiene la cola y las cargas anteriores confirmadas se conservan. Puedes retirar el archivo incorrecto o reintentar los pendientes.
4. En **Proceso**, selecciona un lote para consultar sus siete etapas y parámetros reales. El estado en curso es por archivo; las etapas aparecen al confirmar el lote.
5. En **Resultados**, revisa las gráficas de destino, motivos de rechazo y segmentos, además de la tabla y el detalle original/procesado. Búsqueda y fuente filtran las gráficas; el historial y el total de lotes filtran solo por fuente.

**Crear una sesión vacía** conserva las bases anteriores y vacía la cola de selección. No carga archivos del profesor automáticamente. Cada sesión queda en `outputs/sesiones/<id>/pipeline.sqlite`. La selección dura mientras el servidor está activo; al reiniciar se usa `outputs/pipeline.sqlite`, salvo configuración PIPELINE_DB.

Los archivos originales de datasets/ siguen disponibles si quieres usarlos como ejemplo. Su resultado de referencia es 1,220 leídas = 1,072 limpias + 128 en cuarentena + 20 duplicados omitidos. Con otros archivos, los resultados dependerán de su contenido.

## Cargar otros archivos

Usa la vista **Entrada**. Primero el catálogo CSV, luego ATM XLSX/CSV o DIGITAL JSON con el mismo esquema de `datasets/`. Máximo 20 MB. La hoja XLSX se llama `transacciones_atm`; el JSON es una lista de objetos. Una recarga idéntica se reconoce sin duplicar registros.

Desde consola, en una base separada:

```powershell
.\.venv\Scripts\python.exe -m src.cli cargar --fuente ATM --archivo datasets/transacciones_atm.xlsx --catalogo datasets/catalogo_cuentas.csv --bd outputs/practica.sqlite
.\.venv\Scripts\python.exe -m src.cli cargar --fuente DIGITAL --archivo datasets/transferencias_digitales.json --bd outputs/practica.sqlite
.\.venv\Scripts\python.exe -m src.cli resumen --bd outputs/practica.sqlite
```

## Exposición y evidencia

Según los puntos 5 y 6 de la guía, la entrega final es el enlace al repositorio Git, `entrega/pipeline_banco.sqlite` y `entrega/REPORTE_FINAL.pdf`. El repositorio incluye reglas de negocio, diagrama, código y pruebas de datos corruptos y rollback. La presentación y el video indicados posteriormente por el profesor se preparan aparte; aún deben grabarse/exponerse.

- `docs/GUION_VIDEO.md`: recorrido de hasta un minuto y reparto de exposición.
- `docs/DIAGRAMA.md`: flujo editable.
- `REGLAS_DE_NEGOCIO.md`: reglas 1.5.
- `docs/CONTRATO_DATOS.md`: módulos, campos y API.
- `docs/guias/`: explicación por integrante.
- `entrega/`: únicamente la base SQLite y el reporte PDF requeridos.
- `docs/evidencia/`: resultados, huellas y salida de las pruebas que respaldan el reporte.

Pruebas y reproducción en una carpeta nueva:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.preparar_entrega --salida outputs/reproduccion
.\.venv\Scripts\python.exe scripts/generar_reporte.py --carpeta outputs/reproduccion
```

No sobrescribe una entrega existente. MCAR/MAR son hipótesis operativas, no causalidad demostrada. El servicio está diseñado para uso local, un proceso y el volumen académico del proyecto.

La reproducción guarda JSON y huellas en `outputs/reproduccion_evidencia/`, separados de la base y el PDF. Ambos scripts aceptan `--evidencia` para elegir otra carpeta. Las guías se regeneran con `python scripts/generar_guias.py` usando el entorno del proyecto.
