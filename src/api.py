"""API local para cargar archivos elegidos por el usuario y consultar su ETL."""
import json
import os
import uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from src.catalogo import activar_catalogo, obtener_catalogo
from src.consultas import snapshot
from src.pipeline import ejecutar_lote, LOCK
from src.persistence import initialize_database
from src.lectura import leer_fuente, FIELDS

ROOT = Path(__file__).resolve().parents[1]
FORMATS = {'ATM': ('.csv', '.xlsx'), 'DIGITAL': ('.json',), 'CATALOGO': ('.csv',)}


def create_app(db=None, demo_root=None):
    app = FastAPI(title='Pipeline Banco', version='1.1')
    app.state.session_root = Path(demo_root or ROOT / 'outputs/sesiones')
    app.state.db = str(db or os.environ.get('PIPELINE_DB', ROOT / 'outputs/pipeline.sqlite'))
    app.mount('/static', StaticFiles(directory=ROOT / 'web'), name='static')

    @app.middleware('http')
    async def local_guard(request: Request, call_next):
        if request.method in ('POST', 'PUT', 'DELETE'):
            origin = request.headers.get('origin')
            if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
                return JSONResponse({'detail': 'Origen no permitido'}, status_code=403)
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=422)

    @app.get('/')
    def home():
        return FileResponse(ROOT / 'web/index.html')

    @app.get('/api/control')
    def control(request: Request):
        with LOCK:
            return snapshot(app.state.db, dict(request.query_params))

    @app.get('/api/estado')
    def status():
        with LOCK:
            try:
                version, rows = obtener_catalogo(app.state.db)
            except ValueError:
                version, rows = None, {}
            return {'catalogo': version, 'cuentas': len(rows),
                    'sesion': Path(app.state.db).parent.name,
                    'formatos': FORMATS, 'campos': FIELDS}

    @app.post('/api/sesiones')
    def new_session():
        with LOCK:
            folder = app.state.session_root / str(uuid.uuid4())
            folder.mkdir(parents=True)
            target = folder / 'pipeline.sqlite'
            initialize_database(target).close()
            app.state.db = str(target)
            return {'estado': 'LISTA', 'mensaje': 'Sesión vacía creada. Las anteriores se conservan.'}

    def save_upload(source, upload):
        if source not in FORMATS:
            raise ValueError('Selecciona un tipo de datos válido.')
        name = Path((upload.filename or '').replace('\\', '/')).name
        if Path(name).suffix.lower() not in FORMATS[source]:
            raise ValueError('Formato no admitido. Para ' + source + ': ' + ', '.join(FORMATS[source]))
        data = upload.file.read(20 * 1024 * 1024 + 1)
        if len(data) > 20 * 1024 * 1024:
            raise ValueError('El archivo supera el límite de 20 MB.')
        if not data:
            raise ValueError('El archivo está vacío.')
        folder = Path(app.state.db).parent / 'uploads' / str(uuid.uuid4())
        folder.mkdir(parents=True)
        path = folder / name
        path.write_bytes(data)
        return path

    @app.post('/api/archivos/vista-previa')
    def preview(fuente: str = Form(...), archivo: UploadFile = File(...)):
        with LOCK:
            path = save_upload(fuente, archivo)
            try:
                data = leer_fuente(path, fuente)
                rows = data['registros']
                if not rows:
                    raise ValueError('El archivo no contiene registros.')
                result = {'archivo': path.name, 'filas': len(rows),
                          'muestra': rows[:5], 'campos': FIELDS[fuente]}
                return json.loads(json.dumps(result, default=str))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError('No se pudo leer el archivo: ' + str(exc)) from exc
            finally:
                path.unlink(missing_ok=True)
                path.parent.rmdir()

    @app.post('/api/cargas')
    def upload(fuente: str = Form(...), archivo: UploadFile = File(...)):
        with LOCK:
            path = save_upload(fuente, archivo)
            try:
                if fuente == 'CATALOGO':
                    version = activar_catalogo(path, app.state.db)
                    return {'status': 'COMPLETADA', 'version': version, 'fuente': fuente}
                return ejecutar_lote(path, fuente, None, app.state.db)
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError('No se pudo leer el archivo: ' + str(exc)) from exc

    return app


app = create_app()
