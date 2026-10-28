import argparse
import json
from src.pipeline import ejecutar_lote, reprocesar
from src.catalogo import activar_catalogo
from src.persistence import fetch_summary


def main():
    p=argparse.ArgumentParser(description='Pipeline Banco: procesamiento auditable')
    sub=p.add_subparsers(dest='command',required=True)
    for name in ('cargar','resumen','actualizar-catalogo','reprocesar'):
        s=sub.add_parser(name);s.add_argument('--bd',default='outputs/pipeline.sqlite')
        if name=='cargar':
            s.add_argument('--fuente',choices=['ATM','DIGITAL'],required=True);s.add_argument('--archivo',required=True);s.add_argument('--catalogo')
        if name=='actualizar-catalogo':s.add_argument('--archivo',required=True)
        if name=='reprocesar':s.add_argument('--id',type=int,required=True)
    a=p.parse_args()
    try:
        if a.command=='cargar':r=ejecutar_lote(a.archivo,a.fuente,a.catalogo,a.bd)
        elif a.command=='resumen':r=fetch_summary(a.bd)
        elif a.command=='actualizar-catalogo':r={'version':activar_catalogo(a.archivo,a.bd)}
        else:r=reprocesar(a.id,a.bd)
        print(json.dumps(r,ensure_ascii=False,indent=2))
    except (ValueError,OSError) as e:p.exit(1,f'Error: {e}\n')

if __name__=='__main__':main()
