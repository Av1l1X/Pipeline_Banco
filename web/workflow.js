import{$,esc,api,post,flash,showView}from'./common.js';
let queue=[],busy=false,state=null,runs=[];
const labels={ATM:'ATM',DIGITAL:'Digital',CATALOGO:'Catálogo'};
const pending=()=>queue.filter(x=>x.status!=='done');
function controls(){
 $('#run-pipeline').disabled=busy||!pending().length;
 for(const id of ['file-input','source','new-session'])$('#'+id).disabled=busy;
 $('#dropzone').setAttribute('aria-disabled',String(busy));
}
function form(file,source){const data=new FormData();data.append('fuente',source);data.append('archivo',file);return data}
function renderQueue(){
 $('#queue-count').textContent=queue.length;$('#queue').className=queue.length?'':'empty';
 $('#queue').innerHTML=queue.length?queue.map(x=>`<div class="queue-item"><span class="file-icon">${esc(x.file.name.split('.').pop().toUpperCase())}</span><div><h3>${esc(x.file.name)}</h3><p class="small muted">${labels[x.source]} · ${x.preview.filas.toLocaleString('es-MX')} filas · ${(x.file.size/1024).toFixed(1)} KB</p>${x.error?`<p class="small" style="color:var(--red)">${esc(x.error)}</p>`:''}</div><div class="queue-actions"><span class="badge ${x.status==='done'?'good':x.status==='error'?'bad':''}">${({pending:'En cola',running:'Procesando',done:'Procesado',error:'Error'})[x.status]}</span><button class="btn text-btn" data-preview="${x.id}" ${busy?'disabled':''}>Ver</button><button class="icon-btn" data-remove="${x.id}" aria-label="Quitar ${esc(x.file.name)}" ${busy?'disabled':''}>×</button></div></div>`).join(''):'<span class="empty-symbol">＋</span><h3>No hay archivos seleccionados</h3><p>Agrega un catálogo y uno o más archivos de operaciones.</p>';
 controls();
}
async function refreshState(){state=await api('/api/estado');$('#session-state').textContent=state.catalogo?'Catálogo disponible':'Sin catálogo';$('#catalog-status').className='catalog-status'+(state.catalogo?' ready':'');$('#catalog-status').textContent=state.catalogo?`${state.cuentas} cuentas disponibles. Puedes cargar más operaciones o actualizar el catálogo.`:'Empieza con un catálogo de cuentas. Se necesita para validar las operaciones.';schema()}
function schema(){if(!state)return;const source=$('#source').value;$('#file-input').accept=state.formatos[source].join(',');$('#file-types').textContent=state.formatos[source].map(x=>x.slice(1).toUpperCase()).join(' · ');$('#schema').innerHTML=`<p>${source==='DIGITAL'?'JSON con una lista de objetos.':source==='ATM'?'CSV con encabezados o XLSX con hoja transacciones_atm.':'CSV con encabezados y catálogo completo.'}</p>${state.campos[source].map(x=>`<code>${esc(x)}</code>`).join(' ')}`}
async function addFiles(files){
 if(busy||!files.length)return;busy=true;controls();const source=$('#source').value;let added=0,errors=[];
 for(const file of files){try{
  $('#file-status').textContent=`Revisando ${file.name}…`;
  if(file.size>20*1024*1024)throw Error('Supera el límite de 20 MB.');
  if(source==='CATALOGO'&&pending().some(x=>x.source==='CATALOGO'))throw Error('Ya hay un catálogo en cola. Retíralo para sustituirlo.');
  if(queue.some(x=>x.source===source&&x.file.name===file.name&&x.file.size===file.size&&x.file.lastModified===file.lastModified))throw Error('Este archivo ya está en la cola.');
  const preview=await api('/api/archivos/vista-previa',{method:'POST',body:form(file,source)});
  queue.push({id:crypto.randomUUID(),file,source,preview,status:'pending'});added++;
 }catch(e){errors.push(`${file.name}: ${e.message}`)}}
 busy=false;$('#file-input').value='';$('#file-status').textContent=`${added} archivo(s) agregado(s).${errors.length?' '+errors.join(' '):' Revisa la cola y ejecuta el pipeline.'}`;if(errors.length)flash(errors.join(' '),true);renderQueue();
}
function renderProgress(){ $('#run-files').innerHTML=queue.map(x=>`<div class="run-file"><span>${esc(x.file.name)} <small>· ${labels[x.source]}</small></span><span class="badge ${x.status==='done'?'good':x.status==='error'?'bad':''}">${({pending:'Pendiente',running:'Procesando',done:x.repeated?'Ya cargado':'Confirmado',error:'Error'})[x.status]}</span></div>`).join('') }
async function run(){
 if(busy||!pending().length)return;
 if(!state?.catalogo&&!pending().some(x=>x.source==='CATALOGO')){flash('Agrega un catálogo de cuentas antes de procesar las operaciones.',true);return}
 busy=true;controls();renderQueue();showView('proceso');$('#notice').classList.add('hidden');$('#run-status').className='run-status running';const start=performance.now();let failed=false;
 const jobs=[...pending()].sort((a,b)=>(a.source==='CATALOGO'?0:1)-(b.source==='CATALOGO'?0:1));
 for(const item of jobs){item.status='running';item.error='';$('#run-status').textContent=`Procesando ${item.file.name}…`;renderProgress();try{
  const result=await api('/api/cargas',{method:'POST',body:form(item.file,item.source)});item.status='done';item.repeated=!!result.already_processed;
  await refreshState();window.dispatchEvent(new Event('pipeline-updated'));await refreshRuns();
 }catch(e){item.status='error';item.error=e.message;failed=true;flash(`${item.file.name}: ${e.message}. Los archivos confirmados anteriormente se conservan.`,true);break}}
 busy=false;renderQueue();renderProgress();$('#run-status').className='run-status';$('#run-status').textContent=failed?'Carga detenida. Revisa el error en Entrada y reintenta los pendientes.':`Carga finalizada en ${((performance.now()-start)/1000).toFixed(1)} s. Los resultados están listos para explorar.`;
}
function renderStages(){const run=runs.find(x=>x.id===$('#lot-select').value);if(!run){$('#pipeline-stages').innerHTML='<div class="empty"><h3>No hay lotes procesados</h3><p>Agrega archivos en Entrada y ejecuta el pipeline.</p></div>';return}
 const steps=run.evidencia.etapas||[];$('#pipeline-stages').innerHTML=steps.length?`<div class="timeline">${steps.map((s,i)=>`<article class="step"><span class="step-number">${i+1}</span><div><h3>${esc(s.nombre)}</h3><p>${esc(s.detalle)}</p></div><strong>${s.cantidad.toLocaleString('es-MX')}</strong></article>`).join('')}</div><details><summary>Ver parámetros y diagnóstico del lote</summary><pre>${esc(JSON.stringify({perfil:run.evidencia.comparacion,parametros:run.evidencia.parametros},null,2))}</pre></details>`:'<div class="empty">Esta carga histórica no incluye el desglose de etapas. Los nuevos lotes sí lo registran.</div>';
}
async function refreshRuns(){const selected=$('#lot-select').value;const data=await api('/api/control');runs=data.ejecuciones.filter(x=>x.estado==='COMPLETADA');$('#lot-select').innerHTML=runs.length?runs.map(x=>`<option value="${esc(x.id)}">${esc(x.archivo)} · ${esc(x.fuente)} · ${esc(x.id.slice(0,8))}</option>`).join(''):'<option value="">Sin ejecuciones</option>';if(runs.some(x=>x.id===selected))$('#lot-select').value=selected;renderStages()}
export function initWorkflow(){
 $('#source').onchange=schema;$('#file-input').onchange=e=>addFiles([...e.target.files]);
 const zone=$('#dropzone');zone.ondragover=e=>{e.preventDefault();if(!busy)zone.classList.add('dragging')};zone.ondragleave=()=>zone.classList.remove('dragging');zone.ondrop=e=>{e.preventDefault();zone.classList.remove('dragging');addFiles([...e.dataTransfer.files])};
 $('#queue').onclick=e=>{const remove=e.target.closest('[data-remove]'),preview=e.target.closest('[data-preview]');if(busy)return;if(remove){queue=queue.filter(x=>x.id!==remove.dataset.remove);renderQueue()}if(preview){const item=queue.find(x=>x.id===preview.dataset.preview);$('#detail-title').textContent=item.file.name;$('#detail-body').innerHTML=`<p class="muted">Primeros ${item.preview.muestra.length} registros de ${item.preview.filas}. Datos originales, todavía sin limpiar.</p><pre>${esc(JSON.stringify(item.preview.muestra,null,2))}</pre>`;$('#detail').showModal()}};
 $('#run-pipeline').onclick=run;$('#lot-select').onchange=renderStages;
 $('#new-session').onclick=async()=>{if(busy)return;busy=true;controls();try{await post('/api/sesiones',{});queue=[];$('#run-status').textContent='Sesión vacía lista. Agrega tus archivos en Entrada.';$('#run-files').innerHTML='';$('#file-status').textContent='Sesión nueva: selecciona tus archivos.';await refreshState();await refreshRuns();window.dispatchEvent(new Event('pipeline-updated'));flash('Sesión nueva creada. Las bases anteriores se conservan.')}catch(e){flash(e.message,true)}finally{busy=false;renderQueue()}};
 Promise.all([refreshState(),refreshRuns()]).catch(e=>flash(e.message,true));
}
