# Contrato implementado

## Flujo Python

| Módulo | Entrada y salida | Responsable original |
|---|---|---|
| lectura.py | Ruta y fuente → registros crudos, nombre, SHA256 y posición | Avilix |
| calidad.py | Diccionarios → nulos, vacíos, tipos, categorías, duplicados | Maki |
| integracion.py | Normalización, USD/MXN, fechas, catálogo → candidatos/rechazados | Avilix |
| limpieza.py | Candidatos → imputación y capping; parámetros opcionales persistidos | Maki; adaptación de integración por Avilix |
| transformacion.py | Candidatos → MinMax, segmento y referencia | Avilix |
| validation.py | Tipos y validadores Pydantic → registro o lista de errores | Leo |
| persistence.py | Lote → transacción atómica, conteos e identidad | Leo; ampliación de integración por Avilix |
| pipeline.py | Orquesta lotes, manuales y reprocesos bajo un bloqueo local | Avilix |
| catalogo.py | Valida y activa snapshots completos del catálogo | Avilix |
| consultas.py / api.py / web | Consulta y presentación de datos reales persistidos | Avilix |

Los nombres definitivos del repositorio prevalecen sobre nombres propuestos en el plan inicial. Los módulos de Leo usan nombres en inglés.

## Registro canónico

Claves: `fuente`, `id_transaccion`, `id_cuenta`, `fecha`, `fecha_hora`, `tipo_operacion`, `estado_operacion`, `origen_ingreso`. Dinero: `monto_original`, `moneda_original`, `tasa_conversion`, `monto_mxn`, `monto_analitico_mxn`. Evidencias: `original_json`, `registro_origen`, `huella_origen`, `transformaciones`, `_cambios_imputacion`, `parametros_iqr`, `referencia_ejecucion`, `version_catalogo`.

Los importes usan Decimal y redondeo HALF_UP a centavos. SQLite conserva su representación decimal exacta como texto en el JSON `payload`; no se confunde el monto analítico recortado con el monto de la operación. MinMax es float acotado [0,1]. Segmentos: BAJO, MEDIO, ALTO; cortes por terciles del grupo fuente/operación. La fecha ISO se normaliza a UTC-06:00, conservando el origen.

## Persistencia

`transacciones_limpias` tiene unicidad por fuente e ID y payload completo. `cuarentena_errores` contiene original_record, motivo_rechazo_cuarentena, código, campo, detalles, fase y estado de seguimiento. `ejecuciones` registra lectura, aceptación, rechazo y omisiones. `evidencia_lotes` conserva perfiles y parámetros. `filas_omitidas` y `bitacora_duplicados` documentan duplicados. `catalogo_versiones`, `catalogo_cuentas`, `catalogo_activo` documentan el catálogo. `reprocesamientos` vincula los intentos al rechazo original.

Una ejecución se abre antes de la transacción de filas. Al fallar, las filas del lote se revierten y la ejecución queda FALLIDA. Una carga idéntica completada devuelve la ejecución anterior. La suma leídas = insertadas + cuarentena + duplicados internos + ya cargadas debe conciliar.

## API local

| Método / ruta | Uso |
|---|---|
| GET /api/control | Snapshot; filtros q, fuente, origen_ingreso, tipo_operacion, estado_operacion, ejecucion_id, tipo_fecha, desde, hasta |
| GET /api/cuentas | Catálogo activo |
| GET /api/referencias?fuente=ATM | Lotes completados con filas aptas de la fuente |
| POST /api/cargas | Multipart: fuente y archivo |
| POST /api/transacciones | JSON: solicitud_id, fuente, datos_origen, referencia_ejecucion |
| POST /api/cuarentena/{id}/reprocesar | JSON: correccion opcional, referencia_ejecucion opcional |

La clave de solicitud manual debe ser nueva si se cambia el contenido. La respuesta incluye execution_id, conteos, resultado, already_processed y motivos. Validaciones de estructura del archivo o solicitud producen HTTP 422; un rechazo de fila produce HTTP 200 y resultado EN_CUARENTENA. La interfaz distingue ambos casos. `/docs` muestra el contrato OpenAPI.
