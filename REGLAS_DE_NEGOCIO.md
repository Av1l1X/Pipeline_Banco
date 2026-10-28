# Reglas de negocio del pipeline ETL bancario

**Materia:** Ingeniería de Datos (ATD-2602), Unidad 2.
**Dominio:** Fintech y transacciones bancarias, Grupo 2 (LCNT).
**Fecha:** 27 de octubre de 2026.
**Versión:** 1.5.

## 1. Objetivo y alcance

Integrar las transacciones de cajeros ATM y transferencias digitales con el catálogo de cuentas. El proceso debe diagnosticar la calidad, transformar los datos y separar los registros conformes de los que requieren cuarentena, sin detener todo el lote por un registro incorrecto.

El sistema admite los archivos del proyecto y nuevos lotes con la misma estructura. Cada carga agrega únicamente operaciones válidas que aún no existen en la base de datos. El procesamiento puede ejecutarse desde consola. La interfaz permite cargar archivos, observar las etapas confirmadas y consultar resultados. El alcance no incluye ingreso individual de operaciones ni simuladores.

Este documento establece las reglas de limpieza, integración, transformación, validación y persistencia del proyecto, junto con su justificación técnica y los criterios para verificar su cumplimiento.

La guía exige perfilado, imputación, IQR con factor 1.5, conversión USD a MXN a 19.50, integración, Min-Max, segmentación, Pydantic y persistencia transaccional. Aunque el encabezado menciona seis fases, enumera siete; se contemplan las siete.

## 2. Fuentes y diagnóstico de referencia

| Archivo | Función | Registros originales |
|---|---|---:|
| `catalogo_cuentas.csv` | Catálogo maestro de cuentas | 50 |
| `transacciones_atm.xlsx` | Operaciones de cajeros, hoja `transacciones_atm` | 620 |
| `transferencias_digitales.json` | Transferencias por canales digitales | 600 |

La guía menciona un archivo ATM en CSV, pero el archivo recibido es XLSX. Se leerá el Excel directamente y se documentará esta diferencia.

Hallazgos iniciales, antes de cualquier limpieza:

- Catálogo: 50 identificadores únicos, sin nulos ni duplicados exactos; 30 cuentas activas, 10 bloqueadas y 10 suspendidas.
- ATM: 20 duplicados exactos adicionales, 32 registros con cuenta ausente del catálogo, 27 montos faltantes y 44 identificadores de cajero faltantes. Montos y comisiones están almacenados como texto. No se encontraron montos negativos ni comisiones nulas.
- ATM: 101 montos cero, todos correspondientes a `CONSULTA_SALDO`.
- Digital: 600 identificadores únicos, 29 cuentas huérfanas y 46 CLABEs de cinco dígitos. Hay 8 correos nulos, 8 vacíos y 30 no vacíos con formato incorrecto.
- Digital: 466 operaciones en MXN y 134 en USD; 405 fechas ISO y 195 marcas de tiempo Unix en segundos.

Estos conteos son controles de referencia. Las anomalías pueden coincidir en una fila, por lo que no deben sumarse para estimar la cuarentena. Las pruebas con datos inyectados se contabilizarán por separado.

## 3. Conservación y trazabilidad

1. Los archivos originales no se sobrescriben.
2. Cada fila recibe `fuente`, `archivo_origen`, `fila_origen` o índice JSON y `id_lote` antes de transformarse.
3. Se conserva el registro original serializado y se registran las transformaciones aplicadas. Las fechas originales de Excel se serializan sin perder su hora.
4. Un importe imputado, convertido o recortado nunca reemplaza la evidencia de su valor original.
5. Cada fila procesada debe terminar como nueva operación limpia, en cuarentena, duplicado dentro del lote o repetición de una operación ya cargada. Los destinos son excluyentes y quedan registrados. No habrá descartes silenciosos.

## 4. Esquema común e integración

| Campo común | ATM | Transferencias digitales |
|---|---|---|
| `id_transaccion` | `id_transaccion` | `transfer_id` |
| `id_cuenta` | `id_cuenta` | `account_id` |
| `fecha_hora` | `fecha_hora` | `timestamp` |
| `tipo_operacion` | Valor de origen normalizado | `TRANSFERENCIA` |
| `monto_original` | `monto_mxn` | `amount` |
| `moneda_original` | `MXN` | `currency` |
| `estado_operacion` | `resultado` | `status` |

Se conservarán los campos específicos: cajero y comisión para ATM; CLABE, correo, concepto y plataforma para transferencias. Un campo que no aplica a una fuente queda nulo por diseño, identificado como no aplicable; no se contabiliza como dato faltante de esa fuente.

La clave de operación será `(fuente, id_transaccion)`. El cruce con el catálogo será de muchas transacciones a una cuenta, sin multiplicar filas. Un catálogo con claves duplicadas o contradictorias constituye un error de la fuente maestra que debe resolverse antes del cruce.

## 5. Perfilado previo

Antes de transformar, calcular por fuente:

- Número de filas y columnas, tipos observados y tipos inferidos.
- Nulos, cadenas vacías y cadenas de espacios por columna, con porcentajes.
- Duplicados exactos e identificadores repetidos, distinguiendo ambos conceptos.
- Categorías, formatos de fechas y monedas presentes.
- Estadísticas numéricas calculadas sobre una vista temporal convertible, sin alterar el original.

El porcentaje de faltantes usa como denominador las filas de la fuente a las que aplica el campo. Se informan por separado los valores presentes pero no convertibles.

## 6. Normalización y duplicados

### 6.1 Textos y tipos

- Recortar espacios en los extremos y normalizar a mayúsculas los identificadores, monedas y estados.
- Mantener nombres, conceptos y otros textos descriptivos con sus acentos.
- Tratar identificadores y CLABEs como texto. No convertir CLABEs a número ni completar sus dígitos por suposición.
- Convertir importes y comisiones con precisión decimal; rechazar valores no numéricos, infinitos o no finitos. Una cadena corrupta no se tratará como un simple nulo imputable.
- Conservar los centavos y redondear importes monetarios a dos decimales con `ROUND_HALF_UP`.

### 6.2 Duplicados

- Un duplicado exacto coincide en todas las columnas originales, antes de añadir metadatos.
- Conservar la primera aparición según el orden del archivo y registrar las apariciones adicionales en una bitácora persistente de duplicados.
- Si dos filas del mismo lote comparten `(fuente, id_transaccion)` pero difieren en sus datos de origen normalizados, enviar todas las versiones no descartadas como duplicado exacto a cuarentena como `ID_DUPLICADO_CONFLICTIVO`.
- No deduplicar solo por cuenta, fecha o monto: pueden existir operaciones legítimas con esos valores iguales.

### 6.3 Duplicados entre lotes

- Consultar la clave global `(fuente, id_transaccion)` antes de insertar en `transacciones_limpias`.
- Si la clave ya existe y los datos de origen normalizados coinciden, registrar la fila como `YA_CARGADA`, enlazarla con la operación existente y no insertarla nuevamente.
- Si la clave existe pero su contenido difiere, conservar la operación almacenada y enviar la nueva fila a cuarentena como `ID_DUPLICADO_CONFLICTIVO`. Esto incluye cambios de estado: una carga no actualiza automáticamente una operación anterior.
- Comparar todos los campos de origen definidos en el esquema, con orden estable, fechas y números normalizados y vacíos representados de forma uniforme. Excluir nombres de archivo, posiciones, identificadores de lote, datos enriquecidos del catálogo y resultados de imputación, capping o escalamiento.
- Conservar una huella SHA-256 de esa representación anterior a las imputaciones. Un faltante original no equivale al valor que se imputó posteriormente. Si un campo no puede normalizarse, registrar su error de validación y no clasificar la fila como repetición válida.
- Los registros que solo existen en cuarentena no impiden una futura inserción válida. Todos los intentos mantienen su trazabilidad.

## 7. Faltantes e imputación

No se afirmará que un faltante es MCAR o MAR únicamente por observar un valor nulo. Se compararán tasas de ausencia por operación, cajero, estado y fuente. La clasificación se documentará como hipótesis con evidencia y limitaciones; si no hay evidencia suficiente, se registrará como mecanismo indeterminado.

| Campo | Regla | Justificación |
|---|---|---|
| Identificador de transacción, cuenta o fecha | Cuarentena si falta | No se puede reconstruir una identidad o fecha confiable |
| Monto ATM en consulta de saldo | Si falta, asignar 0 y registrar la regla | La operación consulta información, no mueve un importe |
| Monto ATM en otra operación | Mediana por tipo de operación y resultado normalizado | Reduce la influencia de extremos y evita mezclar operaciones distintas |
| Monto digital | Si falta, mediana por moneda y estado normalizado | Evita mezclar divisas y estados al imputar |
| Comisión ATM | Si falta, mediana por tipo de operación y cajero conocido | Conserva diferencias operativas cuando hay evidencia |
| Cajero ATM | `DESCONOCIDO` si falta | Conserva la operación sin inventar su ubicación |
| Correo digital | Nulo controlado si está vacío o ausente | Es un dato opcional de notificación y no identifica la operación |
| Concepto digital | `SIN_CONCEPTO` si falta | Etiqueta controlada para un campo descriptivo |
| CLABE digital o moneda | Cuarentena si falta | No se pueden inferir de forma confiable |

Las medianas se calculan sobre registros únicos, observados, convertibles y compatibles con las reglas básicas; nunca sobre valores ya imputados. Para montos se usan valores positivos; para comisiones se admiten ceros. Cada grupo debe tener al menos cinco observaciones elegibles. Si no alcanza ese mínimo, se envía el faltante a cuarentena como `SIN_BASE_PARA_IMPUTAR`; no se aplica una mediana global de respaldo.

En cargas de archivos, las estadísticas se calculan con los registros nuevos elegibles de la ejecución actual, sin incorporar operaciones ya cargadas ni el historial de la base de datos. La misma población se utiliza para ajustar los parámetros de IQR, Min-Max y segmentación, respetando las exclusiones propias de cada técnica. Si no hay registros elegibles, no se calculan parámetros y se registra el grupo vacío.

El mínimo de cinco es un criterio operativo para evitar imputaciones basadas en grupos demasiado pequeños; no constituye una garantía estadística. Se guardan tamaño del grupo, mediana, campo imputado y cantidad de filas afectadas. La mediana se prefiere a la media por los extremos observados; el reporte compara ambas en los grupos utilizados.

No se reconstruirá el monto usando fórmulas de ventas, porque estas fuentes no contienen cantidad y precio unitario. No se inventarán comisiones para transferencias digitales.

## 8. Fechas, monedas y montos

### 8.1 Fechas

- ATM contiene fechas de Excel con hora. Se interpretan, como supuesto del proyecto, en un desplazamiento fijo UTC-06:00.
- Las fechas ISO digitales conservarán su desplazamiento al interpretarse y después se normalizarán a UTC-06:00.
- Las marcas Unix se interpretan en segundos desde UTC y se convierten a UTC-06:00 antes de obtener la fecha.
- Se conservará `fecha_hora` con zona y se derivará `fecha` en formato `YYYY-MM-DD`, sin perder la hora original.
- Fechas inexistentes o no interpretables van a cuarentena. No se adivinan formatos ambiguos.

### 8.2 Monedas

- Solo se admiten `MXN` y `USD` en transferencias; ATM se considera MXN por definición de su campo.
- Se aplica la tasa fija académica de la guía: **1 USD = 19.50 MXN**. No representa una cotización de mercado consultada.
- `monto_mxn = monto_original` para MXN; `monto_mxn = monto_original * 19.50` para USD.
- Se conserva moneda, monto original y tasa aplicada. Monedas desconocidas van a cuarentena.

### 8.3 Validez de montos y comisiones

- `CONSULTA_SALDO` admite exclusivamente monto cero.
- `RETIRO`, `DEPOSITO`, `PAGO_SERVICIOS` y `TRANSFERENCIA` requieren un monto positivo.
- Los montos negativos y las comisiones negativas van a cuarentena. No se corrigen con valor absoluto ni con capping.
- Las comisiones cero son válidas. Una comisión ausente no equivale a cero.
- La regla genérica de la guía sobre cantidades menores o iguales a cero se adapta al dominio: estas fuentes no tienen cantidad y una consulta de saldo con cero sí es válida.

## 9. Cuentas, estados y validación de contacto

- Toda cuenta referenciada debe existir en el catálogo. Una cuenta huérfana va a cuarentena como `CUENTA_NO_REGISTRADA`; no se crea automáticamente.
- Se conservará `estado_cuenta` del catálogo. `BLOQUEADA` y `SUSPENDIDA` generan una observación, no rechazo automático: no hay historial para demostrar el estado de la cuenta en la fecha de la operación.
- El límite de crédito no se utilizará como saldo disponible ni como límite universal de transferencias o retiros.
- ATM admite `EXITOSA`, `FALLO_FONDOS` y `FALLO_CONEXION`. Digital admite `LIQUIDADA`, `PENDIENTE`, `RECHAZADA` y `DEVUELTA`. Las variantes en minúsculas se normalizan; estados desconocidos van a cuarentena.
- Una operación fallida, pendiente, rechazada o devuelta puede ser un registro válido. La tabla limpia representa calidad de datos, no únicamente movimientos liquidados.
- Una CLABE digital debe contener exactamente 18 dígitos ASCII. Una CLABE corta o con caracteres no permitidos va a cuarentena. Esta validación académica no comprueba titularidad, existencia bancaria ni dígito verificador.
- El correo digital es un campo opcional. Si está presente, debe pasar la validación sintáctica de `EmailStr` de Pydantic; si falla, el registro va a cuarentena. No se verifica que el buzón exista.

## 10. Outliers, escalamiento y segmentación

### 10.1 IQR y capping

El capping se usa para cumplir el objetivo académico y generar variables analíticas, sin alterar el importe monetario de referencia.

1. Convertir primero a MXN y excluir del cálculo duplicados, registros con defectos básicos y consultas de saldo.
2. Calcular Q1 y Q3 con interpolación lineal por `(fuente, tipo_operacion)`, usando montos observados positivos; excluir imputaciones del ajuste.
3. Calcular `IQR = Q3 - Q1`, `limite_inferior = max(0, Q1 - 1.5 * IQR)` y `limite_superior = Q3 + 1.5 * IQR`.
4. Generar `monto_analitico_mxn` mediante recorte a esos límites y marcar `es_outlier`. Aplicar los límites también a montos imputados, sin usarlos para estimarlos.
5. Conservar `monto_mxn`, el importe original, los límites y la diferencia del recorte para auditoría.

Si el grupo tiene menos de cinco observaciones elegibles o IQR igual a cero, conservar el monto analítico sin recorte y registrar la causa. Las consultas conservan cero y quedan fuera del ajuste. Los importes grandes no se consideran fraude por su tamaño y no se eliminan solo por ser extremos.

### 10.2 Min-Max

Sobre los registros que superaron la validación, calcular por `(fuente, tipo_operacion)`:

`monto_normalizado = (monto_analitico_mxn - minimo) / (maximo - minimo)`

Guardar los parámetros por lote. Si máximo y mínimo coinciden, asignar 0 y registrar `RANGO_CONSTANTE`. El resultado debe ser finito y estar entre 0 y 1. La escala permite comparar valores dentro del grupo; no mide la misma magnitud absoluta entre grupos distintos.

Cada nueva carga conserva sus propios parámetros. No se recalculan automáticamente las variables de operaciones anteriores. Los valores normalizados y segmentos de distintos lotes no se interpretan como una escala común; las comparaciones monetarias entre lotes usan `monto_mxn`.

### 10.3 Segmentos

Calcular los cuantiles 1/3 y 2/3 del monto analítico, con interpolación lineal, dentro del mismo grupo válido:

- `BAJO`: monto menor o igual al primer corte.
- `MEDIO`: monto mayor al primer corte y menor o igual al segundo.
- `ALTO`: monto mayor al segundo corte.

Si los cortes coinciden, mantener estas reglas y aceptar segmentos vacíos; no forzar tres grupos artificialmente. Las consultas de saldo quedan como `BAJO`, con la observación de que no representan movimiento de dinero. Los segmentos expresan posición relativa, no riesgo financiero.

## 11. Pydantic y cuarentena

Se utilizará Pydantic v2 con modelos por fuente y un modelo final común. Las conversiones se realizan explícitamente antes de la validación estricta. Los validadores de campo y de modelo deben comprobar formatos, categorías y relaciones entre campos, incluida la regla de monto según operación.

Los errores de validación se capturan por registro con `ValidationError`. Los errores previstos de conversión también se registran por fila. No se utilizará un bloque general que oculte errores de programación como si fueran errores de datos.

Cada registro rechazado conservará:

- Fuente, archivo, posición, lote e identificadores disponibles.
- Registro original serializado.
- `motivo_rechazo_cuarentena`, con todas las causas detectadas, no solo la primera.
- Campo afectado, código estable de error y descripción.
- Fase del rechazo y fecha/hora de procesamiento.

Códigos mínimos: `CAMPO_OBLIGATORIO_AUSENTE`, `FORMATO_NUMERICO_INVALIDO`, `FECHA_INVALIDA`, `MONEDA_NO_ADMITIDA`, `MONTO_INVALIDO`, `COMISION_INVALIDA`, `CUENTA_NO_REGISTRADA`, `CLABE_INVALIDA`, `CORREO_INVALIDO`, `ESTADO_NO_ADMITIDO`, `OPERACION_NO_ADMITIDA`, `ID_DUPLICADO_CONFLICTIVO` y `SIN_BASE_PARA_IMPUTAR`.

Los rechazos no se eliminan. Una falla de archivo completo o del catálogo se reporta como error de fuente; no se presenta como procesamiento exitoso de cero filas.

## 12. Persistencia y repetición de ejecuciones

Se utiliza SQLite por su portabilidad y porque permite entregar la base de datos en un único archivo. Las tablas obligatorias son:

- `transacciones_limpias`: registros conformes con datos originales relevantes, transformaciones y variables analíticas.
- `cuarentena_errores`: registros rechazados y sus causas.

Se utilizan tablas auxiliares para el catálogo, sus versiones, el control de ejecuciones y la bitácora de filas omitidas. Cada registro limpio conserva el identificador de la ejecución que lo incorporó. Las dos tablas obligatorias, la bitácora y el cierre exitoso de la ejecución se cargan dentro de la misma transacción.

- Usar consultas parametrizadas, `commit` al terminar la carga y `rollback` ante fallas de persistencia.
- Habilitar las claves foráneas de SQLite y validar las relaciones con catálogo y ejecuciones.
- Identificar una carga por tipo de fuente, hashes SHA-256 del contenido de sus archivos, versión del catálogo, versión de reglas y versión del proceso. El nombre del archivo no determina su identidad.
- Omitir una carga idéntica ya confirmada y mostrar su resumen anterior. No volver a insertar sus filas ni sus rechazos.
- Una nueva versión de archivos, catálogo o reglas permite una ejecución distinta, pero no duplica operaciones limpias: la tabla impone `UNIQUE(fuente, id_transaccion)` para toda la base de datos.
- Los fallos de carga dejan el lote sin inserciones parciales. El estado `FALLIDA` se registra después del rollback mediante una transacción independiente; una ejecución fallida puede reintentarse.
- No sustituir registros de ejecuciones anteriores de forma silenciosa. Una violación inesperada de unicidad durante la inserción provoca rollback; nunca se ignora silenciosamente.

### 12.1 Carga de nuevos archivos

El usuario selecciona el tipo de fuente e indica la ruta del archivo. Se permiten nombres distintos de los archivos iniciales; el reconocimiento depende del formato y del esquema.

| Fuente | Formato admitido | Estructura requerida |
|---|---|---|
| ATM | `.xlsx` o `.csv` | `id_transaccion`, `fecha_hora`, `id_cuenta`, `tipo_operacion`, `monto_mxn`, `id_cajero`, `resultado`, `comision_aplicada` |
| Digital | `.json` | Lista de objetos con `transfer_id`, `timestamp`, `account_id`, `amount`, `currency`, `beneficiary_clabe`, `notification_email`, `concept`, `status`, `platform` |
| Catálogo | `.csv` | `id_cuenta`, `titular`, `tipo_cuenta`, `limite_credito_mxn`, `fecha_apertura`, `estado_cuenta` |

- CSV y JSON usan UTF-8, admitiendo BOM; el CSV usa coma como separador y encabezados únicos.
- En Excel se lee la hoja `transacciones_atm`. No se ejecutan macros ni fórmulas; una fórmula en un campo de datos se trata como valor no admitido y su fila se rechaza.
- El orden de columnas o claves puede variar. Se recortan espacios exteriores de los encabezados, sin admitir nombres duplicados después de ese ajuste.
- Todos los encabezados de CSV/XLSX son obligatorios, aunque un campo permita valores vacíos. En JSON, cada elemento debe ser un objeto; claves faltantes se tratan como valores ausentes y se evalúan con las reglas del campo. Los elementos que no sean objetos van a cuarentena con su índice original.
- Los campos adicionales se conservan en la evidencia original y se reportan, pero no se usan para transformar ni comparar la identidad de una operación.
- ATM admite fechas de Excel o texto ISO `YYYY-MM-DD` / `YYYY-MM-DDTHH:MM:SS`, con desplazamiento opcional. Una fecha sin hora se interpreta a las 00:00:00 y una fecha sin zona usa UTC-06:00. Digital admite ISO con zona o Unix en segundos. No se deduce si una fecha ambigua usa día/mes o mes/día.
- Si el archivo no existe, no puede leerse, tiene extensión no admitida, carece de encabezados requeridos, contiene JSON inválido o su raíz JSON no es una lista, se rechaza la carga completa antes de insertar transacciones.
- Un archivo estructuralmente válido sin registros se informa como `SIN_REGISTROS` y no modifica las tablas de transacciones.
- Cada archivo de transacciones constituye un lote independiente. Una ejecución inicial conjunta puede agrupar ATM y digital; los controles se presentan por fuente y para el total.
- El resumen presenta ejecución, fuente, filas leídas, nuevas operaciones insertadas, filas en cuarentena, duplicados internos, operaciones ya cargadas y estado de la carga.

### 12.2 Actualización del catálogo

La actualización del catálogo es una opción separada de la carga de transacciones. Se valida el archivo completo antes de activarlo: claves no vacías y únicas, titulares y tipos de cuenta no vacíos, fechas de apertura válidas en `YYYY-MM-DD`, límites de crédito numéricos finitos no negativos y estados `ACTIVA`, `BLOQUEADA` o `SUSPENDIDA`.

El catálogo actualizado representa una versión completa que conserva todas las cuentas existentes y puede agregar nuevas cuentas o cambiar sus atributos. La ausencia de una cuenta anterior, claves duplicadas o cualquier fila inválida rechazan toda la actualización; el catálogo anterior permanece activo. Una cuenta cerrada o restringida no se elimina por omisión del archivo.

Cada versión conserva su hash, fecha de carga y contenido. Las transacciones mantienen la versión y los atributos del catálogo utilizados durante su procesamiento; una actualización no cambia retroactivamente su evidencia ni crea cuentas a partir de transacciones huérfanas.

### 12.3 Reprocesamiento de cuarentena

La opción de reprocesar permite seleccionar registros no resueltos y volver a evaluar su contenido original contra el catálogo y las reglas vigentes. Esto permite recuperar cuentas huérfanas después de una actualización del catálogo. Una corrección del contenido se presenta mediante un nuevo archivo y referencia al identificador del rechazo anterior; no se edita ni elimina el original.

Cada intento genera una nueva ejecución enlazada con el rechazo anterior. Si el registro es válido, se inserta únicamente si su clave global no existe; si coincide con una operación existente, se registra como `YA_CARGADA`. Si presenta un conflicto, permanece en cuarentena.

Los rechazos conservan su historial y un estado de seguimiento `ABIERTA` o `RESUELTA`. Un rechazo se marca como resuelto únicamente cuando el intento enlazado termina correctamente como inserción o repetición idéntica. Esta actualización se confirma en la misma transacción que el resultado del reprocesamiento. Para rechazos de archivos, los parámetros estadísticos se calculan con el lote seleccionado, sin usar silenciosamente las filas históricas.

## 13. Orden acordado del proceso

1. Validar el formato de entrada, identificar la carga y comprobar si ya fue confirmada; leer fuentes, conservar originales y añadir trazabilidad.
2. Generar el diagnóstico inicial.
3. Separar duplicados exactos; normalizar datos de origen para detectar conflictos de identificador y repeticiones de operaciones ya almacenadas.
4. Normalizar textos, tipos, fechas y monedas; cruzar con el catálogo.
5. Identificar defectos básicos, imputar solo faltantes autorizados y validar las reglas por fuente.
6. Calcular capping, Min-Max y segmentos sobre la población elegible definida arriba.
7. Validar el esquema final, consolidar motivos de cuarentena y cargar ambas salidas transaccionalmente.
8. Generar métricas finales y reconciliar todos los destinos.

El orden técnico se justifica porque no es válido comparar monedas distintas, corregir negativos mediante capping ni estimar parámetros con registros ya rechazados. Todas las fases exigidas por la guía quedan cubiertas.

## 14. Criterios de aceptación y pruebas

- Para cada ejecución procesada y confirmada: `filas_leidas = nuevas_limpias + cuarentena + duplicados_internos + ya_cargadas`. Cada fila cuenta en un solo destino. Una carga omitida por identidad de archivos muestra el resultado previo y no se contabiliza como una nueva ejecución procesada.
- En la primera carga de los archivos iniciales sobre una base vacía, las 1,220 filas originales deben dejar 1,200 registros candidatos después de separar los 20 duplicados exactos ATM. No se fija de antemano la cantidad final de cuarentena.
- Todas las cuentas de la tabla limpia existen en el catálogo y no hay claves de operación duplicadas en toda la base de datos, aunque procedan de ejecuciones distintas.
- Toda fila en cuarentena conserva su original y al menos un motivo verificable.
- Las consultas de saldo con cero permanecen elegibles; los importes negativos no se transforman en positivos.
- USD se convierte exactamente con 19.50 y las CLABEs conservan los ceros iniciales.
- Los correos se contabilizan separando nulos, vacíos y errores sintácticos. El conteo inicial de 30 errores por inspección básica puede diferir del validador final; cualquier diferencia se explica.
- El reporte compara calidad antes/después e informa rechazos e imputaciones, evitando presentar una mejora causada únicamente por excluir filas.
- Probar fechas inválidas, moneda desconocida, cuenta huérfana, CLABE corta, importe negativo, texto en monto, nulos, correo incorrecto, duplicados conflictivos y grupos sin base de imputación.
- Probar que una fila corrupta no detiene las demás, que una falla de carga produce rollback y que repetir una ejecución confirmada no duplica datos.
- Cargar un archivo nuevo con operaciones nuevas y comprobar que solo las válidas se agregan a la base existente.
- Cargar archivos parcialmente superpuestos: las claves idénticas se omiten y las claves existentes con contenido distinto van a cuarentena sin modificar el registro almacenado.
- Renombrar un archivo ya procesado y comprobar que no genera otra carga idéntica.
- Probar un archivo vacío, encabezados faltantes, JSON inválido, elementos JSON no estructurados y valores no numéricos sin producir inserciones parciales.
- Actualizar el catálogo con una cuenta nueva y reprocesar un rechazo huérfano; verificar la inserción única y la conservación del historial. Comprobar que un catálogo inválido no sustituye al vigente.
- Verificar que una segunda carga no recalcula los montos analíticos, segmentos ni parámetros de las transacciones previamente almacenadas.
- Las pruebas usan copias o datos sintéticos y no modifican los archivos originales.

## 15. Demostración y resultados

La interfaz ofrece entrada de archivos, evidencia del proceso y resultados: limpias, cuarentena, duplicados e historial. Cada detalle conserva original, transformaciones y parámetros. Las cifras de etapas describen poblaciones diferentes y no se suman entre sí.

Crear una sesión vacía genera una base nueva en outputs/sesiones sin borrar las anteriores ni modificar la entrega. La entrada permite seleccionar archivos con cualquier nombre y los esquemas admitidos. La vista previa no ingiere datos. La cola procesa primero el catálogo y después las operaciones mediante el mismo pipeline de consola; ante error de archivo se detiene y conserva las cargas confirmadas. Las gráficas se calculan con los registros reales bajo los filtros visibles. No se simula progreso por etapa.

Los datos bancarios ATM y digitales se conservan como fuentes académicas. Se eliminan las pantallas, endpoints y lógica de ingreso individual de los simuladores. El estado bancario sigue siendo distinto de la calidad del registro.

## 16. Presentación

La demostración puede grabarse en un video de hasta un minuto: entrada, ejecución, etapas y comparación original/procesado. Tres diapositivas explican entrada, técnicas y resultados. El equipo explica las decisiones y limitaciones; el video muestra la ejecución.

## 17. Control de cambios y referencias

Versión 1.5: alcance concentrado en archivos, ETL, cuarentena, SQLite y demostración. Cada ejecución registra versiones de reglas y proceso y sus parámetros. Los materiales históricos anteriores se conservan en el respaldo local, fuera del proyecto activo.

Referencias: guía del profesor, puntos 4 y 6; aclaración transcrita del 27 de octubre de 2026; archivos originales de datasets/ y evidencia en entrega/.
