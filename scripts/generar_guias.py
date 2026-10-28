"""Genera guías de estudio con fragmentos y ubicaciones del código vigente."""
import ast
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Preformatted

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/guias'

# Cada sección explica una responsabilidad y remite a funciones verificadas por AST.
GUIDES = {
 'MAKI': ('Calidad, faltantes y outliers', '#087F79', [
  ('Tu responsabilidad y el recorrido completo', 'src/pipeline.py', '_run', 0, 10, [
   'Tu parte mide la calidad, identifica duplicados y trata faltantes y extremos. Avilix conecta esas funciones con lectura, integración y transformación. Leo define validadores y persistencia. Los roles son responsabilidades del equipo; no significan autoría exclusiva de cada línea.',
   'Lee en este orden: src/calidad.py, src/duplicados.py y src/limpieza.py. Después abre _run en src/pipeline.py para ver dónde se invocan. El proceso es lectura, perfilado, deduplicación, validación, catálogo, imputación, IQR, escalamiento y carga.',
   'Un registro es una fila u objeto. Un lote es un archivo procesado. candidatos contiene filas que pueden continuar; rechazados conserva filas que deben ir a cuarentena; parametros guarda cómo se calcularon los cambios.']),
  ('Perfilado: medir antes de cambiar datos', 'src/calidad.py', 'perfilar', 18, 16, [
   'Entrada: una lista de diccionarios crudos y el nombre de la fuente. Salida: filas, campos, duplicados_exactos y metricas_por_campo. La función no modifica los registros. _tipo_observado identifica tipos Python; _es_vacio distingue espacios de valores presentes.',
   'El bucle recorre cada campo. Un None suma nulos; una cadena vacía o con espacios suma vacios. Counter acumula tipos y categorías. pct_nulos divide nulos entre todas las filas de esa fuente y multiplica por 100; una lista vacía devuelve 0 para evitar división entre cero.',
   'En los originales hay 27 montos ATM nulos de 620 filas: 4.35 %. No son 27 filas necesariamente imputadas: algunas pueden ser duplicadas o rechazadas antes. El perfil queda en evidencia_lotes.datos, dentro de perfil_inicial.']),
  ('Duplicados: conservar una copia y registrar el resto', 'src/duplicados.py', 'separar_exactos', 0, 18, [
   '_clave_exacta usa json.dumps con sort_keys=True: el orden de las claves no cambia la comparación. vistos recuerda la primera posición. Si la clave ya apareció, se registra posicion, referencia_conservada, motivo y original_json en omitidos.',
   'Salida: unicos y omitidos. En _run se usan las posiciones para construir la bitácora antes de añadir metadatos que harían distintas dos copias. Los 620 registros ATM contienen 20 copias adicionales; se conservan 600 candidatos antes de otras validaciones.',
   'detectar_conflictos también existe en este archivo como utilidad probada. El pipeline integrado resuelve conflictos en _run usando huella_origen: mismo ID con contenido distinto va a cuarentena. No deduplicamos solo por monto o cuenta.']),
  ('Imputación: decidir cuándo usar la mediana', 'src/limpieza.py', 'imputar', 0, 15, [
   '_key construye los grupos: monto ATM por operación y estado; monto digital por moneda original y estado; comisión ATM por operación y cajero conocido. Los importes digitales ya están en MXN, pero se conserva el grupo de moneda original.',
   'groups reúne valores observados válidos. median(values) calcula el centro; también se guardan media y tamano_grupo. Se exigen cinco observaciones. Un monto corrupto, negativo o infinito no se convierte en una ausencia imputable.',
   'MCAR significa ausencia independiente de las variables; MAR permite dependencia de variables observadas. El agrupamiento usa una hipótesis MAR operativa, no prueba su causa. La mediana se prefiere por su menor sensibilidad a extremos. No se reconstruyen importes con cantidad por precio porque las fuentes no tienen esos campos.']),
  ('Imputación: aplicar y dejar evidencia', 'src/limpieza.py', 'imputar', 25, 17, [
   'Para cada fila se crea una copia. Si el monto de CONSULTA_SALDO falta, se asigna cero. En otras operaciones se busca la mediana del grupo; si hay menos de cinco observaciones, se registra SIN_BASE_PARA_IMPUTAR. Las comisiones pueden ser cero.',
   'changes conserva campo, antes, despues, regla y grupo. El resultado devuelve candidatos, rechazados y parametros. Algunas etiquetas como DESCONOCIDO y SIN_CONCEPTO se aplican antes en los validadores; el pipeline conserva esas normalizaciones por separado.',
   'Ejemplo oficial ATM-TX-00034: monto original null, operación PAGO_SERVICIOS, estado FALLO_FONDOS. El grupo tiene 19 observaciones, mediana 4000 y media aproximada 5894.74. Se asignan 4000 MXN sin borrar el null original.']),
  ('IQR: limitar la variable analítica', 'src/limpieza.py', 'aplicar_iqr', 0, 16, [
   'Se agrupa por fuente y operación. percentil, en src/transformacion.py, ordena valores e interpola Q1 y Q3. IQR = Q3 - Q1; límites = Q1 - 1.5 IQR y Q3 + 1.5 IQR, con límite inferior al menos cero.',
   'El ajuste excluye consultas de saldo y montos imputados con mediana. Con menos de cinco observaciones o IQR cero se conserva el monto sin recorte y se guarda el motivo. En la segunda mitad de aplicar_iqr, min(hi, max(lo, value)) limita el valor.',
   'Solo cambia monto_analitico_mxn; monto_mxn conserva el importe monetario. SPEI-2026-00003 conserva 552091.22 MXN y obtiene 69304.92 MXN analíticos. es_outlier queda true. Un extremo válido no se elimina ni se considera fraude automáticamente.']),
  ('Comparación, comprobaciones y defensa', 'src/calidad.py', 'comparar_calidad', 0, 14, [
   'comparar_calidad devuelve antes, despues y efecto_por_etapa. La población inicial incluye todas las filas; la final contiene aceptadas. Por eso una caída de nulos no se atribuye solo a imputación: también intervienen rechazos y duplicados.',
   'Pruebas necesarias: tests/test_calidad.py comprueba que el perfilado no altera la entrada y que se conservan duplicados; tests/test_limpieza.py comprueba mediana, grupo insuficiente, consulta cero y capping sin pérdida de filas. Se conservan porque respaldan la rúbrica.',
   'Para practicar: .venv/Scripts/python.exe docs/guias/consultar_ejemplos.py maki. Busca ejemplo_imputacion y ejemplo_iqr. Explica la diferencia entre observado e imputado y reproduce el límite IQR. No memorices cifras de archivos nuevos: estas corresponden a los originales.']),
 ]),
 'AVILIX': ('Lectura, integración y coordinación del pipeline', '#2457C5', [
  ('Tu responsabilidad y mapa de archivos', 'src/pipeline.py', 'ejecutar_lote', 0, 9, [
   'Tu parte convierte fuentes distintas a un esquema común y conecta el ETL. Maki aporta calidad y limpieza; Leo, validación y persistencia. También preparaste el acceso por consola y la interfaz de carga y consulta. Los roles no atribuyen cada línea exclusivamente a una persona.',
   'Mapa: src/lectura.py lee; src/catalogo.py activa cuentas; src/integracion.py normaliza y cruza; src/transformacion.py escala y segmenta; src/pipeline.py coordina; src/cli.py ofrece comandos; src/api.py recibe archivos; src/consultas.py prepara resultados.',
   'ejecutar_lote recibe ruta, fuente, catálogo opcional y ruta de base. LOCK evita ejecutar dos cargas simultáneas en este proceso. Se lee el archivo, se obtiene la versión del catálogo y se calcula la identidad antes de llamar a _run.']),
  ('Lectura: formatos, columnas y origen', 'src/lectura.py', 'leer_fuente', 0, 15, [
   'FIELDS define las columnas por fuente. DIGITAL usa JSON con lista de objetos. ATM admite CSV o XLSX con hoja transacciones_atm. El catálogo de la interfaz es CSV. Los nombres de archivo son libres; la estructura no lo es.',
   'El lector usa UTF-8 con BOM admitido y comprueba encabezados únicos y completos en CSV/XLSX. Una fila con longitud incorrecta queda marcada _fila_invalida. La lectura no limpia ni inventa valores. Un archivo estructuralmente ilegible se rechaza completo.',
   'La salida contiene registros y metadatos: archivo, hash SHA-256, fuente y offset. offset permite conservar números de fila considerando los encabezados. _run añade original_json y fila_origen para rastrear cada resultado.']),
  ('Normalización y conversión de moneda', 'src/integracion.py', 'normalizar', 25, 14, [
   'normalizar llama a validate_atm_record_detailed o validate_digital_record_detailed. Si hay errores, guarda un rechazo; si no, obtiene model_dump y construye nombres comunes: id_transaccion, id_cuenta, fecha_hora, estado_operacion y tipo_operacion.',
   'TASA es Decimal(19.50). money usa quantize y ROUND_HALF_UP para centavos. Un monto USD se multiplica por 19.50; MXN usa factor 1. Se conservan moneda_original, monto_original, tasa_conversion y original_json. Un monto faltante sigue faltante para la etapa de imputación.',
   'Ejemplo SPEI-2026-00003: 28312.37 USD por 19.50 = 552091.215; se guarda 552091.22 MXN. IQR produce después otro campo analítico. No se sustituye el importe real por el recortado. Fechas: validadores interpretan la zona y fecha deriva YYYY-MM-DD.']),
  ('Catálogo y cuentas huérfanas', 'src/integracion.py', 'cruzar_catalogo', 0, 10, [
   'cruzar_catalogo recibe candidatos y un diccionario de cuentas. Busca id_cuenta con get. Si no existe, genera CUENTA_NO_REGISTRADA; si existe, añade cuenta y estado_cuenta. Un cruce no multiplica filas.',
   'src/catalogo.py: activar_catalogo valida claves, titulares, fechas, límites y estados, crea una versión por hash y la activa en una transacción. Un catálogo nuevo no puede omitir cuentas anteriores. obtener_catalogo devuelve versión y cuentas vigentes.',
   'ATM-TX-00009 usa CTA-8997, ausente del catálogo, y va a cuarentena. Una cuenta BLOQUEADA existente puede conservarse porque no conocemos su estado histórico al ocurrir la operación. El pipeline evalúa datos; no autoriza retiros.']),
  ('Min-Max y segmentos', 'src/transformacion.py', 'escalar_segmentar', 18, 15, [
   'Entrada: candidatos después de IQR. Se agrupan por fuente y operación. Se calculan mínimo, máximo y percentiles 1/3 y 2/3 con percentil. Normalizado = (valor - mínimo)/(máximo - mínimo). Si el grupo es constante, el resultado es cero.',
   'La variable usada es monto_analitico_mxn. BAJO llega hasta el primer corte; MEDIO hasta el segundo; ALTO lo supera. Las consultas de saldo quedan en cero y BAJO. AnaliticaFinal valida importes Decimal finitos y escala float entre cero y uno.',
   'ATM-TX-00034: (4000 - 500)/(12000 - 500) = 0.3043478261, segmento MEDIO. El 0.3043 no expresa probabilidad de fraude. Los parámetros se guardan por lote; no compares escalas de lotes distintos sin revisarlos.']),
  ('Orquestación y conciliación', 'src/pipeline.py', '_run', 30, 16, [
   '_run perfila antes de limpiar, separa copias y normaliza. Agrupa por identidad; si las huellas difieren, rechaza el conflicto. Consulta las claves existentes: una operación idéntica ya cargada se omite; una distinta con la misma clave se rechaza.',
   'Después cruza cuentas, imputa, aplica IQR y escala. Acumula todos los rechazos y construye perfil_final, comparacion, parametros y etapas. La igualdad final exige leídas = aceptadas + cuarentena + omitidas.',
   'persist_batch guarda las salidas y la evidencia. Las siete etapas de la página describen poblaciones diferentes: no se suman. reprocesar permite volver a evaluar un rechazo desde la consola conservando el historial.']),
  ('Carga de archivos y página actual', 'src/api.py', 'preview', 0, 15, [
   'create_app construye FastAPI. save_upload comprueba fuente, extensión, tamaño máximo de 20 MB y nombre seguro. preview lee una muestra de cinco filas sin ingerirla y elimina su archivo temporal al terminar. upload activa el catálogo o llama a ejecutar_lote.',
   'Rutas: POST /api/archivos/vista-previa muestra la entrada; POST /api/cargas procesa; POST /api/sesiones crea una base vacía; GET /api/control consulta resultados; GET /api/estado devuelve catálogo y esquemas. Una sesión nueva conserva las bases anteriores.',
   'La página no está escrita solo en Python: web/index.html contiene la estructura; web/base.css el estilo; web/common.js la navegación; web/workflow.js la cola de archivos; web/dashboard.js las gráficas y tablas. La cola procesa primero catálogo y luego lotes. Es apoyo para mostrar el ETL, no una fase exigida por la rúbrica.']),
  ('Consulta de resultados y ejecución', 'src/consultas.py', 'snapshot', 0, 12, [
   'snapshot lee transacciones_limpias, cuarentena_errores, ejecuciones, evidencia_lotes y filas_omitidas. Convierte payload JSON a campos para las tablas. matches aplica filtros. Counter cuenta motivos; una fila puede tener varios, por eso sus sumas no equivalen al total de cuarentena.',
   'Desde la raíz: .venv/Scripts/python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8765. Abre http://127.0.0.1:8765. Mantén la terminal abierta; Ctrl+C detiene el servidor. Ya no existe un lanzador .cmd.',
   'Para practicar divisas y escala: .venv/Scripts/python.exe docs/guias/consultar_ejemplos.py avilix. Para consola, main en src/cli.py implementa cargar, resumen, actualizar-catalogo y reprocesar. Los comandos completos están en README.md.']),
 ]),
 'LEO': ('Validación, cuarentena y persistencia', '#8045A5', [
  ('Tu responsabilidad y mapa del código', 'src/validation.py', 'validate_atm_record_detailed', 0, 10, [
   'Tu parte define qué registros son válidos, explica sus errores y los guarda con seguridad. Maki limpia y calcula parámetros; Avilix integra y coordina. Los módulos se adaptaron en equipo; responsabilidad técnica no equivale a autoría exclusiva de cada línea.',
   'Mapa: src/validation.py contiene ATMTransaction, DigitalTransaction y validadores detallados. src/persistence.py crea tablas y guarda lotes. tests/test_validation_and_persistence.py comprueba reglas, duplicados, catálogo y rollback. src/pipeline.py reúne candidatos y rechazos.',
   'La función mostrada intenta construir el modelo. Si Pydantic lanza ValidationError, lo convierte en detalles y devuelve None junto con esos detalles. Así el código que recorre el lote puede continuar con la siguiente fila.']),
  ('Modelos y validadores por campo', 'src/validation.py', 'DigitalTransaction', 0, 15, [
   'BaseModel declara los campos y tipos. @field_validator conecta una función con un campo. mode=before permite normalizar antes de la conversión de tipo. ATMTransaction representa campos del cajero; DigitalTransaction representa transfer_id, account_id, amount, currency y demás campos digitales.',
   '_as_optional_decimal convierte importes y rechaza booleanos, texto corrupto y valores no finitos. Se permite monto ausente para que la imputación decida después. Consulta de saldo admite cero; las otras operaciones monetarias requieren monto positivo. Comisión admite cero, no negativos.',
   'Los modelos de entrada permiten conversiones controladas, no strict=True global. AnaliticaFinal en src/transformacion.py sí usa ConfigDict(strict=True) para los valores calculados. No afirmes que todos los campos de todo el pipeline son estrictos de la misma manera.']),
  ('CLABE, correo, fechas y categorías', 'src/validation.py', '_validate_clabe', 0, 9, [
   'DigitalTransaction._validate_clabe exige exactamente 18 dígitos ASCII y conserva el dato como texto. Los ceros iniciales no se pierden. El formato no acredita que la cuenta bancaria exista ni comprueba el dígito de control de la CLABE.',
   'notification_email es opcional: vacío o ausente queda None; si tiene contenido, EmailStr valida el formato. No se consulta que el buzón exista. _parse_digital_datetime admite ISO con zona o Unix en segundos; _parse_atm_datetime admite los formatos definidos y aplica UTC-06:00 cuando corresponde.',
   'Moneda admite MXN y USD; categorías inválidas producen códigos estables. Fechas ambiguas, imposibles y números infinitos se rechazan. DESCONOCIDO y SIN_CONCEPTO son etiquetas controladas para algunos campos categóricos ausentes.']),
  ('Errores y cuarentena con explicación', 'src/validation.py', 'validate_digital_record_detailed', 0, 10, [
   '_validation_error_details traduce errores de Pydantic en codigo, campo y descripcion. normalizar, en src/integracion.py, envuelve estos detalles con el original y la fase VALIDACION. Los huérfanos se detectan después, en INTEGRACION; no todo rechazo viene de Pydantic.',
   'insert_quarantine_record en src/persistence.py guarda original_record, motivo_rechazo_cuarentena, codigo_error, detalles_errores, fase y ejecución. Puede conservar varios motivos en una fila. estado_seguimiento permite distinguir ABIERTA de RESUELTA.',
   'ATM-TX-00009 se rechaza por cuenta ausente. En cambio SPEI-2026-00003 puede estar limpia aunque su estado bancario sea RECHAZADA: limpia significa datos válidos, no operación aprobada. Nunca mezcles estos conceptos.']),
  ('Tablas y registros completos', 'src/persistence.py', 'insert_clean_record', 0, 12, [
   'initialize_database crea el esquema y habilita claves foráneas. Las dos tablas obligatorias son transacciones_limpias y cuarentena_errores. También hay ejecuciones, evidencia_lotes, catálogo versionado y bitácora de omitidos para explicar lo ocurrido.',
   'insert_clean_record escribe identificadores y payload. payload es texto JSON con el registro completo; _json_dumps serializa Decimal como cadenas para preservar exactitud. Para encontrar una moneda no busques necesariamente una columna SQL: usa json_extract(payload, ...).',
   'La identidad de operación es fuente más ID. _source_fingerprint calcula la huella del contenido original normalizado. build_load_identity incorpora hashes de archivos y versiones. Mismo contenido evita insertar dos veces; mismo ID con contenido distinto va a cuarentena.']),
  ('Commit y rollback: guardar todo el lote', 'src/persistence.py', 'transactional_connection', 0, 14, [
   'El context manager abre una conexión y comienza BEGIN. yield entrega la conexión al bloque de guardado. Si termina bien, commit confirma. Si ocurre una excepción, rollback deshace las escrituras y raise conserva el error. finally cierra la conexión.',
   'persist_batch registra primero la ejecución EN_PROCESO. Luego guarda aceptadas, cuarentena, omitidas, evidencia y cierre del lote en una transacción. Ante fallo, una conexión independiente registra FALLIDA. Esto evita que un error deje media carga guardada.',
   'Una transacción SQL es un conjunto de escrituras atómicas; no es una transferencia bancaria. Los fallos de infraestructura pueden propagarse: lo probado es rollback y trazabilidad, no que el sistema nunca pueda detenerse por cualquier causa.']),
  ('Pruebas necesarias para la rúbrica', 'tests/test_validation_and_persistence.py', 'test_batch_rolls_back_and_records_failed_execution', 0, 15, [
   'Esta prueba crea una base temporal e instala un trigger que falla en ATM-SECOND. Intenta guardar dos filas. Comprueba que no quede ninguna limpia y que la ejecución sea FALLIDA. Espera sqlite3.IntegrityError: la excepción del caso es deliberada.',
   'El mismo archivo verifica montos no finitos, CLABE, correo, fechas, faltantes imputables, duplicados, recargas y claves foráneas. tests/test_pipeline.py prueba originales, repetición y reproceso. tests/test_api.py conserva la prueba de XLSX/JSON corruptos antes ubicada en test_entrega.py.',
   'Ejecutar: .venv/Scripts/python.exe -m pytest -q. La evidencia actual está en docs/evidencia/pruebas.txt. Eliminar estas pruebas impediría respaldar la exigencia de resiliencia del profesor; los casos sintéticos se crean en carpetas temporales, no en la base de entrega.']),
  ('Cómo comprobar y defender la salida', 'src/persistence.py', 'fetch_summary', 0, 12, [
   'La base oficial es entrega/pipeline_banco.sqlite. Las bases de la interfaz viven en outputs/ y pueden tener otros archivos. Para la entrega original: ATM 568 limpias, 32 cuarentena y 20 omitidas; DIGITAL 504 limpias y 96 cuarentena. Total: 1220 = 1072 + 128 + 20.',
   'Ejecuta .venv/Scripts/python.exe docs/guias/consultar_ejemplos.py leo. Abre la base en solo lectura, muestra conteos, ejemplo de rechazo, PRAGMA integrity_check y foreign_key_check. Se espera ok y ninguna referencia incumplida.',
   'En un visor SQLite: SELECT COUNT(*) FROM transacciones_limpias; y SELECT COUNT(*) FROM cuarentena_errores;. Explica dónde queda el original, cómo leer motivos y por qué una fila puede tener varios errores. Revisa el test de rollback y señala las líneas commit y rollback sin depender de memoria.']),
 ])
}

def excerpt(path, symbol, offset, length):
    source = (ROOT/path).read_text(encoding='utf-8')
    matches = [n for n in ast.walk(ast.parse(source)) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == symbol]
    if len(matches) != 1:
        raise ValueError(f'Ubicación ambigua o ausente: {path}:{symbol}')
    node = matches[0]
    start = min(node.lineno + offset, node.end_lineno)
    end = min(start + length - 1, node.end_lineno)
    lines = source.splitlines()
    snippet = []
    for number in range(start, end+1):
        parts = textwrap.wrap(lines[number-1], width=92, replace_whitespace=False, drop_whitespace=False) or ['']
        snippet.append(f'{number:>3} {parts[0]}')
        snippet.extend('    '+part for part in parts[1:])
    return node.lineno, start, end, '\n'.join(snippet)

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for role, (specialty, color, sections) in GUIDES.items():
        accent = colors.HexColor(color)
        styles = {
            'title': ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=21, leading=25, textColor=accent, spaceAfter=14),
            'body': ParagraphStyle('body', fontName='Helvetica', fontSize=10.2, leading=15, spaceAfter=11),
            'small': ParagraphStyle('small', fontName='Helvetica', fontSize=8.2, leading=11, spaceAfter=9, textColor=colors.HexColor('#425268')),
            'code': ParagraphStyle('code', fontName='Courier', fontSize=7.2, leading=9.5, backColor=colors.HexColor('#F1F4F8'), borderPadding=7, spaceAfter=12),
        }
        story=[]
        def paragraph(text, kind='body'):
            return Paragraph(escape(text), styles[kind])
        markdown=[f'# Guía de {role.title()}\n\n{specialty}\n\nActualizada: 28 de octubre de 2026.\n']
        for index,(title,path,symbol,offset,length,paragraphs) in enumerate(sections,1):
            if index>1: story.append(PageBreak())
            line,start,end,code=excerpt(path,symbol,offset,length)
            story.extend([paragraph(f'{role} / {specialty} / {index:02}', 'small'),paragraph(title,'title')])
            location=f'Archivo: {path} | Función o clase: {symbol} | Inicio: línea {line}'
            story.append(paragraph(location,'small'))
            story.extend(paragraph(t) for t in paragraphs)
            story.append(paragraph(f'Fragmento real, líneas {start}-{end}. Las líneas largas se continúan sin número; consulta el archivo para ver la función completa.','small'))
            story.append(Preformatted(code,styles['code']))
            markdown.extend([f'## {index}. {title}\n\n{location}\n', *[t+'\n' for t in paragraphs],f'```python\n{code}\n```\n'])
        story.append(PageBreak())
        story.append(paragraph('Repaso y archivos para entregar','title'))
        closing=[
            'ETL significa extraer, transformar y cargar. Puedes explicar tu módulo indicando su entrada, la decisión que toma, su salida y la evidencia que conserva. No basta con leer nombres de técnicas.',
            'Los ejemplos de estas guías corresponden a datasets/catalogo_cuentas.csv, datasets/transacciones_atm.xlsx y datasets/transferencias_digitales.json. Con archivos nuevos cambian las estadísticas y resultados. La tasa académica USD/MXN es fija: 19.50.',
            'Entrega al profesor: enlace al repositorio Git, entrega/pipeline_banco.sqlite y entrega/REPORTE_FINAL.pdf. Dentro del repositorio quedan reglas, diagrama, código y pruebas de resiliencia. Las guías de docs/guias son material de estudio del equipo.',
            'El video y la presentación indicados posteriormente por el profesor se preparan aparte; esta guía no equivale a haber grabado o expuesto. docs/GUION_VIDEO.md propone el recorrido. La interfaz es un apoyo visual para demostrar el pipeline.',
            'Para localizar el código, abre el archivo .py en el editor y busca el nombre de función indicado. Las líneas corresponden a esta versión y pueden moverse con futuros cambios. Los fragmentos se extraen del código al regenerar las guías; no son pseudocódigo.',
            'Referencias: guía del profesor, puntos 4 y 6; REGLAS_DE_NEGOCIO.md; docs/CONTRATO_DATOS.md; código y pruebas citados; docs/evidencia/resultados.json; base SQLite de entrega. Regla vigente 1.5, proceso 2.1.'
        ]
        story.extend(paragraph(t) for t in closing)
        markdown.extend(['## Repaso y entrega\n', *closing])
        def footer(canvas, doc, role=role, accent=accent):
            canvas.setStrokeColor(accent);canvas.line(45,43,A4[0]-45,43)
            canvas.setFont('Helvetica',8);canvas.setFillColor(accent)
            canvas.drawString(45,29,f'PIPELINE BANCO / {role} / 28 OCT 2026')
            canvas.drawRightString(A4[0]-45,29,str(doc.page))
        path=OUT/f'GUIA_{role}_ETL.pdf'
        SimpleDocTemplate(str(path),pagesize=A4,leftMargin=45,rightMargin=45,topMargin=42,bottomMargin=58,title=f'Guía de {role.title()} - Pipeline Banco',author='Avilix, Maki y Leo').build(story,onFirstPage=footer,onLaterPages=footer)
        content = '\n\n'.join(markdown)
        (OUT/f'GUIA_{role}_ETL.md').write_text('\n'.join(line.rstrip() for line in content.splitlines())+'\n',encoding='utf-8')
        print(path)

if __name__ == '__main__':
    main()
