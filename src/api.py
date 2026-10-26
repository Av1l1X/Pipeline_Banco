"""Aplicación local. Las escrituras pasan por el pipeline, nunca por JavaScript."""
import json
import os
import uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from src.catalogo import obtener_catalogo, activar_catalogo
from src.consultas import snapshot
from src.pipeline import ejecutar_lote, ejecutar_manual, reprocesar
from src.persistence import initialize_database

ROOT=Path(__file__).resolve().parents[1]


def create_app(db=None):
    app=FastAPI(title='Pipeline Banco',version='1.0')
    app.state.db=str(db or os.environ.get('PIPELINE_DB',ROOT/'outputs/pipeline.sqlite'))
    app.mount('/static',StaticFiles(directory=ROOT/'web',check_dir=False),name='static')

    @app.middleware('http')
    async def local_guard(request:Request,call_next):
        if request.method in ('POST','PUT','DELETE'):
            origin=request.headers.get('origin')
            if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
                return JSONResponse({'detail':'Origen no permitido'},status_code=403)
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def invalid(request,exc):return JSONResponse({'detail':str(exc)},status_code=422)

    @app.get('/')
    def home():return FileResponse(ROOT/'web/index.html')

    @app.get('/atm')
    def atm():return FileResponse(ROOT/'web/atm.html')

    @app.get('/digital')
    def digital():return FileResponse(ROOT/'web/digital.html')

    @app.get('/api/control')
    def control(request:Request):return snapshot(app.state.db,dict(request.query_params))

    @app.get('/api/cuentas')
    def accounts():
        try:version,rows=obtener_catalogo(app.state.db)
        except ValueError:return {'version':None,'cuentas':[]}
        return {'version':version,'cuentas':list(rows.values())}

    @app.get('/api/referencias')
    def references(fuente:str):
        return [{'id':r['id'],'archivo':r['archivo'],'fecha':r['iniciada_en']} for r in snapshot(app.state.db,{'fuente':fuente})['ejecuciones'] if r['estado']=='COMPLETADA' and r['origen_ingreso']=='ARCHIVO' and r['nuevas_limpias']>0]

    @app.post('/api/transacciones')
    def manual(body:dict):
        if not all(k in body for k in ('solicitud_id','fuente','datos_origen')):raise ValueError('Solicitud incompleta')
        if not isinstance(body['datos_origen'],dict):raise ValueError('Los datos deben ser un objeto')
        return ejecutar_manual(body,app.state.db)

    @app.post('/api/cuarentena/{rid}/reprocesar')
    def retry(rid:int,body:dict):return reprocesar(rid,app.state.db,body.get('referencia_ejecucion'),body.get('correccion'))

    @app.post('/api/cargas')
    def upload(fuente:str=Form(...),archivo:UploadFile=File(...)):
        if fuente not in ('ATM','DIGITAL','CATALOGO'):raise ValueError('Fuente inválida')
        suffix=Path(archivo.filename or '').suffix.lower()
        allowed={'ATM':('.csv','.xlsx'),'DIGITAL':('.json',),'CATALOGO':('.csv',)}
        if suffix not in allowed[fuente]:raise ValueError('Formato no admitido')
        data=archivo.file.read(20*1024*1024+1)
        if len(data)>20*1024*1024:raise ValueError('Límite de carga: 20 MB')
        folder=Path(app.state.db).parent/'uploads'/str(uuid.uuid4());folder.mkdir(parents=True)
        # No confiar en rutas proporcionadas por el navegador.
        safe_name=Path((archivo.filename or 'archivo').replace('\\','/')).name
        path=folder/safe_name;path.write_bytes(data)
        try:
            if fuente=='CATALOGO':return {'status':'COMPLETADA','version':activar_catalogo(path,app.state.db)}
            return ejecutar_lote(path,fuente,None,app.state.db)
        except (OSError,UnicodeError,json.JSONDecodeError) as e:raise ValueError('No se pudo leer el archivo: '+str(e))

    return app

app=create_app()
