# Reporte de Calidad, Nulos y Outliers (M1 - M4)

**Integrante:** Maki (David Cuevas)
**Rol:** Ingeniería 1 - Calidad, Nulos y Outliers
**Fecha:** 24 de octubre de 2026

---

### 1. Diagnóstico inicial de calidad
Se analizaron las fuentes originales (transacciones_atm.xlsx y transferencias_digitales.json) sin alterar su contenido. Según los controles de referencia de las Reglas de Negocio v1.4:

- ATM: 620 filas, 20 duplicados exactos adicionales, 27 montos faltantes y 44 identificadores de cajero faltantes. Se detectó que los montos vienen como texto.
- Digital: 600 filas, 29 cuentas huérfanas y 46 CLABEs cortas (de 5 dígitos). Hay 8 correos nulos y 8 vacíos.

### 2. Hipótesis de faltantes (MCAR / MAR)
Tras analizar la distribución de los valores ausentes, se concluye que los faltantes no son completamente aleatorios (no son MCAR). 

- Los 27 montos faltantes en ATM se concentran en su mayoría en operaciones donde el cajero no reportó el importe o en fallos de conexión. Al observar la tasa de ausencia por tipo de operación, la ausencia depende del tipo de operación y del estado. Por lo tanto, se clasifican como MAR (Missing At Random) condicionados a esas variables.
- No se puede afirmar causalidad, pero la evidencia justifica agrupar por operación y estado para imputar.

### 3. Estrategia de imputación
¿Por qué Mediana y no Media? Se eligió la mediana porque los montos bancarios presentan valores extremos (outliers) muy altos. La media se distorsiona fácilmente con estos valores, mientras que la mediana es una medida robusta que representa el centro real de los datos.

Reglas aplicadas:

- Consultas de Saldo: Si el monto es nulo, se imputa 0 (no mueven dinero).
- Cajeros ATM: Si falta el id_cajero, se imputa la etiqueta DESCONOCIDO.
- Concepto Digital: Si falta, se imputa SIN_CONCEPTO.
- Montos (ATM y Digital): Se calculó la mediana agrupada (por tipo de operación/resultado para ATM; por moneda/estado para digital). Se exigió un mínimo de 5 observaciones elegibles. Si el grupo tenía menos de 5, la fila se envió a cuarentena con el código SIN_BASE_PARA_IMPUTAR.
- Valores no numéricos: No se imputaron. Se enviaron a cuarentena.

### 4. Tratamiento de outliers con IQR
- Se aplicó la fórmula de Rango Intercuartílico (IQR) con factor 1.5 por cada grupo (fuente, tipo_operacion).
- Se excluyeron del cálculo las consultas de saldo y los montos que ya habían sido imputados.
- Capping / Winsorizing: No se eliminó ninguna fila. En su lugar, los valores extremos se recortaron en una nueva columna llamada monto_analitico_mxn. El importe monetario real (monto_mxn) se conservó intacto para auditoría.
- Si el grupo tenía menos de 5 datos o el IQR era cero, se registró la causa y no se aplicó recorte.

### 5. Comparación antes / después
El pipeline permite generar los archivos calidad_inicial.json y calidad_final.json. Con base en las pruebas sintéticas y los controles esperados:

- Antes: Alta presencia de duplicados exactos (20 en ATM), nulos en montos (27 en ATM) y cajeros faltantes (44 en ATM).
- Después de M1-M4: Los 20 duplicados exactos se omitieron y registraron en bitácora. Los faltantes con base estadística fueron imputados. Los registros sin base suficiente o con datos no numéricos corruptos fueron desviados a cuarentena con sus motivos. La calidad del lote restante mejoró en completitud sin eliminar datos válidos.

### 6. Limitaciones
- El umbral mínimo de 5 observaciones para imputar es un criterio operativo del proyecto, no una garantía estadística.
- La clasificación MAR es una hipótesis basada en la observación de patrones en los datos, no una prueba causal formal.
- El capping altera el monto solo en la variable analítica, no en el registro contable (esto es correcto para el análisis, pero no debe usarse para cálculos de saldos reales).