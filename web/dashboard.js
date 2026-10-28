import{$,esc,api,flash,mxn,sidebar,showView}from'./common.js';
import{initWorkflow}from'./workflow.js';
sidebar();
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>showView(b.dataset.view));
showView(location.hash.slice(1));
window.addEventListener('hashchange',()=>showView(location.hash.slice(1)));
$('#close-detail').onclick=()=>$('#detail').close();
let data=null,tab='limpias',page=0,requestId=0;const size=12;
const number=n=>Number(n||0).toLocaleString('es-MX');
const pre=x=>`<pre>${esc(JSON.stringify(x,null,2))}</pre>`;
async function load(){const id=++requestId;try{const result=await api('/api/control?'+new URLSearchParams(new FormData($('#filters'))));if(id!==requestId)return;data=result;page=0;render()}catch(e){flash(e.message,true)}}
function bars(items,color){const max=Math.max(...items.map(x=>x[1]),1);return items.map(([label,n])=>`<div class="bar-row"><div class="bar-label"><span>${esc(label)}</span><b>${number(n)}</b></div><div class="bar" role="img" aria-label="${esc(label)}: ${n}"><i style="width:${100*n/max}%;background:${color}"></i></div></div>`).join('')}
function render(){
 const m=data.resumen;
 $('#metrics').innerHTML=[['Registros limpios',m.limpias,'Cumplen las reglas de datos'],['En cuarentena',m.rechazos_historicos,'Con motivo de rechazo'],['Duplicados omitidos',m.duplicados,'Copias reconocidas'],['Lotes confirmados',m.lotes,'Historial de la fuente seleccionada']].map(([a,b,c])=>`<article class="metric"><span class="label">${a}</span><strong>${number(b)}</strong><small>${c}</small></article>`).join('');
 const slices=[['Limpias',m.limpias,'#4285f4'],['Cuarentena',m.rechazos_historicos,'#e8a266'],['Omitidas',m.duplicados,'#a49bd1']];const total=slices.reduce((s,x)=>s+x[1],0);let offset=0;const circumference=2*Math.PI*64;
 const rings=slices.map(([label,n,color])=>{const length=total?circumference*n/total:0;const svg=`<circle cx="80" cy="80" r="64" fill="none" stroke="${color}" stroke-width="15" stroke-dasharray="${length} ${circumference-length}" stroke-dashoffset="${-offset}"/>`;offset+=length;return svg}).join('');
 $('#distribution').innerHTML=`<div class="donut"><svg viewBox="0 0 160 160" role="img" aria-label="${slices.map(x=>x[0]+': '+x[1]).join(', ')}"><circle cx="80" cy="80" r="64" fill="none" stroke="#edf1f7" stroke-width="15"/>${rings}</svg><div class="donut-label"><strong>${number(total)}</strong><span>${total?'registros':'Sin datos'}</span></div></div><div class="chart-legend">${slices.map(([label,n,color])=>`<div><span class="dot" style="background:${color}"></span>${label}<b>${total?(100*n/total).toFixed(1):0}% · ${number(n)}</b></div>`).join('')}</div>`;
 const reasons=Object.entries(data.motivos).sort((a,b)=>b[1]-a[1]).slice(0,5).map(([k,v])=>[k.replaceAll('_',' '),v]);
 $('#reasons').innerHTML=reasons.length?bars(reasons,'#e8a266'):'<div class="empty">Sin rechazos para esta selección.</div>';
 const segments=['BAJO','MEDIO','ALTO'].map(s=>[s,data.limpias.filter(r=>r.segmento===s).length]);$('#segments').innerHTML=data.limpias.length?bars(segments,'#81b995'):'<div class="empty">Los segmentos aparecerán al aceptar registros.</div>';
 renderTable();
}
function renderTable(){
 if(!data)return;const rows=[...data[tab]];
 if(tab==='limpias')rows.sort($('#sort').value==='amount'?(a,b)=>Number(b.monto_mxn)-Number(a.monto_mxn):(a,b)=>String(b.fecha_hora).localeCompare(String(a.fecha_hora)));
 const headers={limpias:['Operación / cuenta','Fecha','Fuente','Tipo','Importe MXN','Estado bancario',''],cuarentena:['Operación','Fuente','Motivo','Seguimiento',''],ejecuciones:['Archivo / ejecución','Fuente','Estado','Limpias','Cuarentena','Omitidas','']};
 $('#head').innerHTML='<tr>'+headers[tab].map(x=>`<th>${x}</th>`).join('')+'</tr>';
 $('#rows').innerHTML=rows.slice(page*size,(page+1)*size).map(r=>{
  if(tab==='limpias')return `<tr><td><b>${esc(r.id_transaccion)}</b><br><small>${esc(r.id_cuenta)}</small></td><td>${esc(String(r.fecha_hora).slice(0,16).replace('T',' '))}</td><td><span class="badge">${esc(r.fuente)}</span></td><td>${esc(r.tipo_operacion.replaceAll('_',' '))}</td><td class="money">${mxn(r.monto_mxn)}</td><td>${esc(r.estado_operacion)}</td><td><button class="link" data-detail="${r.id}">Ver detalle →</button></td></tr>`;
  if(tab==='cuarentena')return `<tr><td>${esc(r.id_transaccion||'Sin identificador')}</td><td>${esc(r.fuente)}</td><td style="white-space:normal;min-width:200px">${esc(r.motivo_rechazo_cuarentena)}</td><td><span class="badge warn">${esc(r.estado_seguimiento)}</span></td><td><button class="link" data-detail="${r.id}">Ver motivo →</button></td></tr>`;
  return `<tr><td>${esc(r.archivo)}<br><small>${esc(r.id.slice(0,12))}</small></td><td>${esc(r.fuente)}</td><td><span class="badge ${r.estado==='COMPLETADA'?'good':'bad'}">${esc(r.estado)}</span></td><td>${number(r.nuevas_limpias)}</td><td>${number(r.cuarentena)}</td><td>${number(r.duplicados_internos+r.ya_cargadas)}</td><td><button class="link" data-detail="${esc(r.id)}">Ver carga →</button></td></tr>`;
 }).join('')||'<tr><td colspan="7"><div class="empty"><h3>No hay registros para mostrar</h3><p>Carga tus archivos o prueba otros filtros.</p></div></td></tr>';
 $('#count').textContent=rows.length?`${page*size+1}–${Math.min((page+1)*size,rows.length)} de ${number(rows.length)}`:'0 registros';$('#prev').disabled=page===0;$('#next').disabled=(page+1)*size>=rows.length;
 $('#scope').textContent=tab==='ejecuciones'?'El historial filtra por fuente. La búsqueda de operación o cuenta no se aplica a los lotes.':'Las primeras tres cifras y las gráficas responden a búsqueda y fuente. Los lotes confirmados se filtran solo por fuente.';
}
$('#rows').onclick=e=>{const b=e.target.closest('[data-detail]');if(!b||!data)return;const r=data[tab].find(x=>String(x.id)===b.dataset.detail);if(!r)return;$('#detail-title').textContent=r.id_transaccion||'Detalle de carga';
 $('#detail-body').innerHTML=tab==='limpias'?`<div class="split"><div><h3>Datos originales</h3>${pre(r.original_json)}</div><div><h3>Valores procesados</h3>${pre({moneda_original:r.moneda_original,monto_original:r.monto_original,monto_mxn:r.monto_mxn,monto_analitico_mxn:r.monto_analitico_mxn,monto_normalizado:r.monto_normalizado,segmento:r.segmento,estado_bancario:r.estado_operacion})}</div></div><h3>Transformaciones aplicadas</h3>${pre(r.transformaciones)}<details><summary>Parámetros IQR y trazabilidad</summary>${pre({iqr:r.parametros_iqr,ejecucion:r.ejecucion_id,catalogo:r.version_catalogo,archivo:r.archivo_origen,fila:r.fila_origen})}</details>`:tab==='cuarentena'?`<p class="notice error">${esc(r.motivo_rechazo_cuarentena)}</p><h3>Registro original</h3>${pre(r.original)}<h3>Errores detectados</h3>${pre(r.errores)}`:pre(r);$('#detail').showModal();
};
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.tab;page=0;document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('active',x===b));renderTable()});
$('#filters').onsubmit=e=>{e.preventDefault();load()};$('#clear').onclick=()=>{$('#filters').reset();load()};$('#refresh').onclick=load;$('#sort').onchange=()=>{page=0;renderTable()};$('#prev').onclick=()=>{page--;renderTable()};$('#next').onclick=()=>{page++;renderTable()};
window.addEventListener('pipeline-updated',load);initWorkflow();load();
