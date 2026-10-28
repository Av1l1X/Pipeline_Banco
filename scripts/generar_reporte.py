"""Reporte reproducible a partir de resultados.json; ReportLab, sin red."""
import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable
from reportlab.lib.pagesizes import A4

TEAL=colors.HexColor('#087f79'); NAVY=colors.HexColor('#15363d'); LIGHT=colors.HexColor('#edf5f3'); AMBER=colors.HexColor('#c67c38')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleLab',fontName='Helvetica-Bold',fontSize=29,leading=34,textColor=NAVY,spaceAfter=20))
styles.add(ParagraphStyle(name='SubLab',fontName='Helvetica-Bold',fontSize=18,leading=22,textColor=TEAL,spaceAfter=14))
styles.add(ParagraphStyle(name='BodyLab',fontSize=10,leading=15,textColor=NAVY,spaceAfter=10))
styles.add(ParagraphStyle(name='SmallLab',fontSize=8,leading=11,textColor=NAVY,spaceAfter=7))

def p(t,style='BodyLab'):return Paragraph(t,styles[style])
def table(rows,widths=None):
    data=[[p(escape(str(x)),'SmallLab') for x in row] for row in rows]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),LIGHT),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),1,TEAL),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#dce6e3')),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    return t

class Diagram(Flowable):
    def __init__(self):Flowable.__init__(self);self.width=490;self.height=410
    def draw(self):
        c=self.canv
        boxes=[('Archivos ATM XLSX/CSV + DIGITAL JSON',370),('Lectura y perfil inicial',320),('Tipos, fechas, USD/MXN y duplicados',270),('Catálogo y detección de huérfanos',220),('Mediana / IQR 1.5 / MinMax / terciles',170),('Validación y separación de resultados',120),('Transacción SQLite: commit o rollback',70),('Dashboard y evidencia por ejecución',20)]
        for i,(label,y) in enumerate(boxes):
            c.setFillColor(LIGHT if i%2 else colors.HexColor('#e0f0eb'));c.setStrokeColor(TEAL);c.roundRect(5,y,345,34,7,fill=1,stroke=0)
            c.setFillColor(NAVY);c.setFont('Helvetica',10);c.drawCentredString(177,y+13,label)
            if i<len(boxes)-1:
                c.setStrokeColor(TEAL);c.line(177,y,177,y-16);c.line(177,y-16,173,y-11);c.line(177,y-16,181,y-11)
        c.setFillColor(colors.HexColor('#fff1de'));c.roundRect(365,120,125,174,7,fill=1,stroke=0)
        c.setFillColor(NAVY);c.setFont('Helvetica-Bold',10);c.drawString(375,270,'CUARENTENA')
        c.setFont('Helvetica',9)
        for j,line in enumerate(['Registro original','Motivos / campo','Fase / ejecución','Historial preservado','Reproceso auditable']):c.drawString(375,247-j*22,line)
        c.setStrokeColor(AMBER);c.line(350,285,365,285);c.line(350,235,365,235);c.line(350,135,365,135);c.line(427,120,427,87);c.line(427,87,350,87)

def main():
    a=argparse.ArgumentParser();a.add_argument('--carpeta',default='entrega');args=a.parse_args();folder=Path(args.carpeta)
    d=json.loads((folder/'resultados.json').read_text(encoding='utf-8'));ev=list(d['evidencia'].values());s=[]
    def heading(k,title):s.extend([p(k,'SmallLab'),p(title,'TitleLab')])
    heading('INGENIERÍA DE DATOS · UNIDAD 2 · TECNM CAMPUS COLIMA','Pipeline ETL bancario<br/>con zona de cuarentena')
    s.append(p('Reporte técnico de integración y entrega','SubLab'))
    s.append(p('Equipo: <b>Avilix · Maki · Leo</b><br/>Fuentes: cajeros ATM y transferencias digitales.<br/>Corte de preparación: 27 de octubre de 2026.'))
    s.append(table([['Responsable','Especialidad'],['Maki','Perfilado, faltantes, duplicados y outliers'],['Avilix','Integración, transformación, orquestación e interfaces'],['Leo','Pydantic, cuarentena, persistencia y resiliencia']],[90,400]))
    s.append(Spacer(1,20));s.append(p('Resultado reproducible','SubLab'))
    s.append(table([['Fuente','Leídas','Limpias','Cuarentena','Omitidas'],['ATM',620,568,32,20],['DIGITAL',600,504,96,0],['TOTAL',1220,1072,128,20]],[110,90,90,100,100]))
    s.append(p('La conciliación es 1,220 = 1,072 + 128 + 20. Los rechazos se conservan; las omisiones corresponden a duplicados exactos. La base entregable contiene solo las fuentes originales, sin las operaciones manuales de prueba.'))
    s.append(p('Repositorio: https://github.com/Av1l1X/Pipeline_Banco<br/>Base: entrega/pipeline_banco.sqlite<br/>Evidencia detallada: entrega/resultados.json','SmallLab'))
    s.append(PageBreak());heading('01 / ARQUITECTURA','Un solo recorrido de datos')
    s.append(Diagram());s.append(p('La validación temprana impide que importes o claves corruptas contaminen los parámetros estadísticos. La validación final comprueba las variables analíticas antes de persistir.'))
    s.append(p('El catálogo CSV se valida como snapshot completo. Se conserva la versión aplicada a cada registro; los huérfanos van a cuarentena. Las filas omitidas también tienen bitácora y forman parte de la conciliación.'))
    s.append(p('El diagrama editable está en docs/DIAGRAMA.md. El encabezado de la guía dice “6 fases”, pero enumera siete; esta implementación cubre también la carga transaccional de la fase 7.','SmallLab'))
    s.append(PageBreak());heading('02 / DIAGNÓSTICO Y FALTANTES','Medir antes de transformar')
    rows=[['Fuente / campo','Nulos','Vacíos','% ausencia','Tipos observados']]
    for e in ev:
        for field,m in e['perfil_inicial']['metricas_por_campo'].items():
            if m['nulos'] or m['vacios']:
                rows.append([e['fuente']+' / '+field,m['nulos'],m['vacios'],round(m['pct_nulos']+m['pct_vacios'],2),', '.join(m['tipos_observados'])])
    s.append(table(rows,[190,45,45,65,145]));s.append(Spacer(1,12))
    s.append(p('Se cuentan nulos y cadenas vacías por separado. El ATM contiene 20 duplicados exactos. El perfil completo conserva tipos observados y categorías por columna; no reemplaza las fuentes.'))
    s.append(p('Hipótesis MCAR/MAR y límites','SubLab'))
    s.append(p('Las ausencias de monto/comisión se tratan bajo una hipótesis MAR operativa: el grupo de operación, estado o cajero puede aportar información al valor faltante. Una omisión aislada de concepto o identificador de cajero es compatible con MCAR, pero el perfil descriptivo no demuestra independencia. No se presenta ninguna de estas hipótesis como causalidad comprobada.'))
    s.append(p('Se imputa mediana por grupo con al menos cinco valores observados válidos. Es menos sensible a colas y extremos que la media. Se guardan ambas medidas y el tamaño del grupo para auditar la elección. Si no hay base suficiente, se rechaza; no se inventa un importe.'))
    s.append(p('Las categorías faltantes se sustituyen por DESCONOCIDO o SIN_CONCEPTO. El correo es opcional, pero si está presente debe ser válido. Una consulta de saldo tiene importe cero; ese cero no significa un saldo bancario real.'))
    s.append(PageBreak());heading('03 / TRANSFORMACIÓN','Conservar el origen, explicar el cambio')
    s.append(table([['Regla','Aplicación'],['Dinero','Decimal; USD × 19.50; HALF_UP a dos decimales. Se conserva importe y moneda originales.'],['Fechas','Parseo por fuente, fecha ISO YYYY-MM-DD y fecha/hora UTC-06:00. Fechas imposibles o ambiguas se rechazan.'],['IQR','Q1 y Q3 con interpolación lineal; límites Q1 − 1.5 IQR y Q3 + 1.5 IQR, inferior no negativo. No se ajusta con importes imputados.'],['Capping','Solo cambia monto_analitico_mxn. monto_mxn permanece como importe de operación. Con menos de cinco observaciones o IQR cero no se recorta.'],['MinMax','(x − mínimo)/(máximo − mínimo), por fuente y operación. Grupo constante: cero.'],['Segmentos','Terciles del grupo: BAJO hasta primer corte, MEDIO hasta segundo, ALTO después. Consulta de saldo: BAJO.']],[85,405]))
    s.append(Spacer(1,15));s.append(p('Efecto en los datos aceptados','SubLab'))
    s.append(p(f"{d['outliers']} registros se marcaron como outliers; {d['imputados']} registros registraron cambios en la etapa de imputación. Esta última cifra no cuenta las normalizaciones deterministas realizadas antes por los validadores."))
    s.append(table([['Segmento','Registros'],*[[k,d['segmentos'][k]] for k in ('BAJO','MEDIO','ALTO')]],[245,245]))
    s.append(p('La comparación antes/después usa poblaciones distintas: antes son las filas crudas; después son las aceptadas. Una reducción de nulos puede deberse tanto a imputación como a separación en cuarentena, por lo que no se atribuye toda la mejora a la limpieza.','SmallLab'))
    s.append(PageBreak());heading('04 / RESILIENCIA Y BASE DE DATOS','Aceptar, aislar y poder auditar')
    s.append(table([['Motivo registrado','Ocurrencias'],*[[k,v] for k,v in d['motivos'].items()]],[350,140]))
    s.append(p('Hay 128 filas en cuarentena y 132 ocurrencias de motivos. Las categorías se superponen: una fila puede contener varios errores. Un registro rechazado en validación temprana no alcanza necesariamente el cruce de catálogo; los conteos son errores detectados en el recorrido, no un inventario exhaustivo de todos los defectos latentes.'))
    s.append(p('Integridad y transacciones','SubLab'))
    s.append(p('SQLite contiene transacciones_limpias y cuarentena_errores, además de ejecuciones, catálogo versionado, evidencia y bitácoras. Los importes Decimal se guardan como texto exacto dentro del payload JSON. La carga de filas, cuarentena y evidencias se confirma de forma atómica. Ante fallo se revierte y queda una ejecución FALLIDA.'))
    s.append(p('La entrega pasó PRAGMA integrity_check y foreign_key_check. La unicidad fuente/ID y la huella de origen impiden recargas duplicadas. Una carga idéntica devuelve el resumen previo; un ID con contenido distinto se desvía a cuarentena.'))
    s.append(p('Pruebas automatizadas y de interfaz','SubLab'))
    s.append(p('49 pruebas aprobadas: validación, fechas ambiguas, números no finitos, CLABE/correo, huérfanos, duplicación, vista previa, carga personalizada, aislamiento de sesiones, rollback, catálogos, filtros y archivos ilegibles. Se conserva la salida en entrega/pruebas.txt. Hay una advertencia de deprecación del adaptador httpx de TestClient; no es un fallo de prueba.'))
    s.append(PageBreak());heading('05 / DEMOSTRACIÓN','Entrada, proceso y resultados')
    s.append(p('La página tiene tres vistas: Entrada, Proceso y Resultados. Permite seleccionar archivos propios, revisar una muestra sin ingerirlos y procesar primero el catálogo y después los lotes. Los nombres de archivo pueden variar; sus columnas deben corresponder al esquema seleccionado. Las sesiones vacías se conservan en outputs/sesiones.'))
    s.append(p('Las etapas muestran conteos de evidencia_lotes después de confirmar los resultados: lectura y diagnóstico, duplicados exactos, validación, cruce de catálogo, imputación, transformación y persistencia. No se simula progreso. Las cantidades de etapas no se suman: describen poblaciones distintas.'))
    s.append(p('El dashboard incluye gráficas de destino, motivos y segmentos, filtros, historial y comparación original/procesado. El menú es compacto y plegable. El ingreso individual y los simuladores se retiraron del alcance. Los archivos bancarios siguen siendo las fuentes del ejercicio.'))
    s.append(p('Video de hasta un minuto: muestra original, ejecución, etapas, indicadores y un detalle. El guion está en docs/GUION_VIDEO.md. El video se graba después de ensayar el recorrido.'))
    s.append(p('Inicio: instalar dependencias con Python 3.12, ejecutar iniciar.cmd y abrir http://127.0.0.1:8765. Crear una sesión vacía conserva las bases anteriores y limpia la cola de selección. La selección de sesión se mantiene mientras el servidor está activo.'))
    s.append(p('Servicio local de un solo proceso y volumen académico. El estado bancario se conserva separado del resultado de calidad. Una fila limpia no acredita un movimiento bancario exitoso.'))
    s.append(PageBreak());heading('06 / ENTREGA Y DEFENSA','Evidencias para revisar y reproducir')
    s.append(table([['Requisito de la guía','Evidencia'],['Reglas y mockup','REGLAS_DE_NEGOCIO.md y docs/DIAGRAMA.md'],['Calidad antes/después','src/calidad.py, src/limpieza.py; perfiles en resultados.json'],['Integración y transformación','src/integracion.py, src/transformacion.py, src/pipeline.py'],['Pydantic y cuarentena','src/validation.py; tabla cuarentena_errores'],['Persistencia y resiliencia','src/persistence.py; tests/; entrega/pruebas.txt'],['Repositorio, BD y reporte','GitHub; pipeline_banco.sqlite; este PDF'],['Defensa individual','docs/GUION_VIDEO.md; explicación en vivo de los tres integrantes']],[160,330]))
    s.append(Spacer(1,16));s.append(p('Fuentes y reproducibilidad','SubLab'))
    s.append(p('1. GUIA_LINEAMIENTOS_PROYECTO_ALUMNOS.pdf, pp. 1–3, documento proporcionado por el docente: objetivo, fases, entregables y rúbrica.<br/>2. datasets/catalogo_cuentas.csv, datasets/transacciones_atm.xlsx y datasets/transferencias_digitales.json: fuentes originales recibidas.<br/>3. entrega/resultados.json y pipeline_banco.sqlite: mediciones producidas por este código. SHA256.json identifica los archivos usados.'))
    s.append(p('Las fuentes canónicas están en datasets/. Las copias históricas se retiraron de la raíz para evitar cargar versiones distintas por error.'))
    s.append(p('Para reproducir: python -m scripts.preparar_entrega --salida outputs/reproduccion. El comando se niega a sobreescribir una base existente. Después ejecutar scripts/generar_reporte.py con --carpeta outputs/reproduccion.'))
    s.append(p('Las firmas reales de Avilix, Maki y Leo en las reglas y la defensa oral son acciones personales pendientes de los integrantes. Este reporte no simula firmas ni acredita una exposición que no se ha realizado.'))
    def footer(c,doc):
        c.setStrokeColor(TEAL);c.line(45,43,A4[0]-45,43);c.setFillColor(NAVY);c.setFont('Helvetica',8);c.drawString(45,29,'PIPELINE BANCO  /  AVILIX · MAKI · LEO');c.drawRightString(A4[0]-45,29,str(doc.page))
    SimpleDocTemplate(str(folder/'REPORTE_FINAL.pdf'),pagesize=A4,rightMargin=50,leftMargin=50,topMargin=45,bottomMargin=60,title='Pipeline Banco — Reporte técnico',author='Avilix, Maki y Leo').build(s,onFirstPage=footer,onLaterPages=footer)
    print(folder/'REPORTE_FINAL.pdf')

if __name__=='__main__':main()
