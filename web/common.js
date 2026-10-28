export const $=s=>document.querySelector(s);
export const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const mxn=v=>new Intl.NumberFormat('es-MX',{style:'currency',currency:'MXN'}).format(Number(v||0));
export async function api(path,options={}){const r=await fetch(path,options);let data;try{data=await r.json()}catch{throw Error('No se pudo leer la respuesta. Comprueba que el servidor está activo.')}if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));return data}
export const post=(path,data)=>api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
export function flash(message,error=false){const n=$('#notice');n.textContent=message;n.className='notice'+(error?' error':'');n.setAttribute('role',error?'alert':'status')}
const paths={menu:'M4 6h16M4 12h16M4 18h16',entrada:'M12 16V3m-4 4 4-4 4 4M4 14v6h16v-6',proceso:'M4 5h5v5H4zM15 14h5v5h-5zM9 7h8v7M7 10v7h8',resultados:'M4 20h17M7 16v-5m5 5V4m5 12V8'};
export function sidebar(){
 const icon=name=>`<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]}" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
 $('#sidebar').innerHTML=`<button id="toggle-nav" aria-label="Abrir menú lateral" aria-expanded="false" aria-controls="side-nav">${icon('menu')}<span class="nav-text">Menú</span></button><nav id="side-nav" aria-label="Navegación principal">${['entrada','proceso','resultados'].map((v,i)=>`<button data-view="${v}" title="${['Entrada','Proceso','Resultados'][i]}" aria-label="${['Entrada','Proceso','Resultados'][i]}">${icon(v)}<span class="nav-text">${['Entrada','Proceso','Resultados'][i]}</span></button>`).join('')}</nav>`;
 $('#toggle-nav').onclick=()=>{const open=$('.shell').classList.toggle('expanded');$('#toggle-nav').setAttribute('aria-expanded',String(open));$('#toggle-nav').setAttribute('aria-label',open?'Cerrar menú lateral':'Abrir menú lateral')};
}
export function showView(view){
 if(!['entrada','proceso','resultados'].includes(view))view='entrada';
 document.querySelectorAll('.view').forEach(el=>{el.hidden=el.id!==view;el.classList.toggle('active',el.id===view)});
 document.querySelectorAll('[data-view]').forEach(el=>{el.classList.toggle('active',el.dataset.view===view);if(el.closest('nav'))el.setAttribute('aria-current',el.dataset.view===view?'step':'false')});
 history.replaceState(null,'','#'+view);window.scrollTo({top:0,behavior:'instant'});
}
