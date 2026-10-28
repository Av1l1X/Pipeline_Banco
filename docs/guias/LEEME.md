# Guías de estudio del equipo

Actualizadas el 28 de octubre de 2026. Cada PDF explica responsabilidades, archivos `.py`, funciones, entradas y salidas, fragmentos reales con líneas y ejemplos para la defensa.

- `GUIA_MAKI_ETL.pdf`: perfilado, duplicados, imputación, IQR y comparación.
- `GUIA_AVILIX_ETL.pdf`: lectura, catálogo, integración, divisas, Min-Max, orquestación y carga/consulta desde la página.
- `GUIA_LEO_ETL.pdf`: Pydantic, cuarentena, SQLite, commit/rollback y pruebas de resiliencia.

Los `.md` contienen el mismo material en texto. Las líneas corresponden al código utilizado al generar los PDF; los nombres de función permiten localizarlo después de futuros cambios.

Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe docs/guias/consultar_ejemplos.py maki
.\.venv\Scripts\python.exe docs/guias/consultar_ejemplos.py avilix
.\.venv\Scripts\python.exe docs/guias/consultar_ejemplos.py leo
```

El consultor abre la base oficial en modo de solo lectura. Para regenerar las guías con los fragmentos actuales: `python scripts/generar_guias.py`, usando el entorno del proyecto.

Son material de estudio. Los archivos de entrega al profesor están en `entrega/`; la evidencia técnica está en `docs/evidencia/`.
