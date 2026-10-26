# Pipeline Banco

Proyecto de Ingeniería de Datos: pipeline ETL con cuarentena, SQLite y tres pantallas locales. Equipo: **Avilix (integración y transformación), Maki (calidad y limpieza), Leo (validación y persistencia)**.

## Iniciar en Windows

Desde PowerShell, dentro de la carpeta del repositorio, con Python 3.12:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m src.cli cargar --fuente ATM --archivo datasets/transacciones_atm.xlsx --catalogo datasets/catalogo_cuentas.csv
.venv\Scripts\python.exe -m src.cli cargar --fuente DIGITAL --archivo datasets/transferencias_digitales.json
.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8765
```

Abre **http://127.0.0.1:8765**. Mantén esa terminal abierta; Ctrl+C detiene el servidor. No necesitas activar el entorno virtual. También puedes ejecutar `iniciar.cmd` después de instalar las dependencias: carga las fuentes originales de manera idempotente e inicia la aplicación.

El archivo `requirements-lock.txt` registra las versiones verificadas; puedes instalarlo con `-r requirements-lock.txt` para reproducir este entorno.

La base de trabajo queda en `outputs/pipeline.sqlite`. Los originales canónicos están en `datasets/`. Los CSV/JSON de la raíz se conservan por el historial de los compañeros; no son la ruta del inicio rápido. El XLSX entregado por el usuario es la fuente ATM usada para los resultados oficiales; el lector también admite CSV con los mismos encabezados.

## Pantallas

- **Centro de control:** indicadores, gráficas, tabla de limpias, filtros, cuarentena, historial y detalles original/procesado. Los indicadores de filas responden a filtros; el historial aplica solo fuente, origen, ejecución y fecha de procesamiento, como indica la pantalla.
- **Cajero ATM:** operaciones, teclado, corrección, revisión, confirmación y comprobante.
- **Transferencia digital:** cuenta, CLABE, correo opcional, moneda, concepto, resumen y comprobante.

Todas las escrituras usan el mismo pipeline Python. Son simulaciones académicas: no mueven dinero, no consultan saldos ni envían correos. El estado bancario simulado es distinto del resultado de calidad (INSERTADA / EN_CUARENTENA / YA_CARGADA).

## Cargar más datos

En «Cargar archivo» selecciona ATM (`.xlsx`/`.csv`), DIGITAL (`.json`) o CATALOGO (`.csv`). La hoja XLSX debe llamarse `transacciones_atm`. El JSON debe ser una lista de objetos. Los encabezados obligatorios están en `src/lectura.py`. Límite web: 20 MB. Un archivo ilegible se rechaza con un mensaje; una fila inválida dentro de un archivo legible se separa en cuarentena.

Primero carga un catálogo válido, luego lotes de ambas fuentes. Los formularios toman referencias estadísticas de lotes completos de su fuente. No ajustan mediana, IQR ni escala con una sola transacción. Si falta una referencia suficiente, el registro queda en cuarentena (salvo consulta de saldo, que tiene importe cero).

Repetir exactamente un lote confirmado devuelve su resultado previo. Una clave `(fuente, id_transaccion)` ya registrada con el mismo origen se omite; un contenido distinto con esa clave se rechaza. Cambiar solo el nombre del archivo no evade la identidad de carga.

En cuarentena, «Ver» permite revisar errores, corregir el JSON y reprocesar. El original queda conservado y el nuevo intento se vincula al rechazo. Solo se marca resuelto cuando se acepta o se reconoce un duplicado ya válido. Los catálogos se versionan completos: una actualización inválida no sustituye el vigente y no elimina cuentas anteriores.

## Entrega y reproducción

- `entrega/pipeline_banco.sqlite`: base preparada únicamente con las dos fuentes originales.
- `entrega/REPORTE_FINAL.pdf`: metodología, resultados y evidencias.
- `entrega/resultados.json`: perfiles y parámetros completos por ejecución.
- `entrega/SHA256.json`: huellas de fuentes, base y resultados.
- `entrega/pruebas.txt`: salida de la batería de pruebas.
- `docs/DIAGRAMA.md`: flujo editable.
- `docs/CONTRATO_DATOS.md`: módulos, API y persistencia.
- `docs/DEFENSA.md`: recorrido de 5–7 minutos y preguntas por rol.
- `REGLAS_DE_NEGOCIO.md`: decisiones de negocio.

Para reproducir sin sobreescribir la entrega:

```powershell
.venv\Scripts\python.exe -m pytest -q tests
.venv\Scripts\python.exe -m scripts.preparar_entrega --salida outputs/reproduccion
.venv\Scripts\python.exe scripts/generar_reporte.py --carpeta outputs/reproduccion
```

Para inspeccionar una copia de la base entregable con el dashboard, copia la base a otra carpeta y establece `$env:PIPELINE_DB` con esa ruta antes de iniciar Uvicorn. Evita usar la base entregable para la demostración: las operaciones manuales cambiarían sus conteos.

## Alcance y entrega presencial

Lo prioritario es el ETL, pruebas, reglas, diagrama, reporte y base. El dashboard, la API y los simuladores son extras. El mecanismo MCAR/MAR es una hipótesis de trabajo, no una causalidad probada por los datos. El servidor está diseñado para uso local, un proceso y este volumen académico; no incluye autenticación ni despliegue público. Las consultas cargan las filas en memoria.

Las firmas de los tres integrantes en las reglas y la defensa oral deben realizarlas los integrantes; el repositorio no certifica firmas ni sustituye su explicación individual. Conservar el historial de Maki y Leo al integrar sus ramas. Los commits de integración y extras se registran con la identidad Git configurada de Avilix.
