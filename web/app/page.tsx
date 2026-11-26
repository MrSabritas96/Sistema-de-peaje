'use client';
import Photo from './Photo';
import {Confirm} from './confirm';
import {Tools} from './tools';
import {useEffect,useState} from 'react';
import {call,googleLogin} from './client';
type Step={id:number;fecha:string;placa:string;categoria:string;ejes:number|null;estado:string;monto:number|null;tarifa_referencia:number|null;sentido:string;evidencia:string};
export default function Page(){
 const [revenue,setRevenue]=useState('0'),[alarm,setAlarm]=useState('');
 const [steps,setSteps]=useState<Step[]>([]),[active,setActive]=useState(false),[message,setMessage]=useState(''),[plate,setPlate]=useState(''),[answer,setAnswer]=useState('');
 const [page,setPage]=useState(0),[matches,setMatches]=useState<string[]>([]),[filtered,setFiltered]=useState<Step[]|null>(null);
 const [filter,setFilter]=useState(''),[detail,setDetail]=useState<Record<string,any>|null>(null);
 const rows=filtered??steps, pages=Math.max(1,Math.ceil(rows.length/6)), current=Math.min(page,pages-1);
 const latest=steps[0];
 const [canHide,setCanHide]=useState(false);
 useEffect(()=>{if(active)call('sesion').then(v=>setCanHide(v.rol==='ADMIN')).catch(()=>setCanHide(false))},[active]);
 async function hide(id:number){
   if(!window.confirm('¿Quitar este paso del panel? Se conservarán la evidencia y los movimientos de saldo.'))return;
   try{await call('pasos/'+id+'/ocultar',{method:'POST'});setSteps(await call('historial'));setFiltered(prev=>prev?.filter(s=>s.id!==id)??null)}
   catch(e){setMessage(String(e))}
 }
 useEffect(()=>{let live=true;if(latest)call('pasos/'+latest.id+'/inferencia').then(v=>{if(live)setDetail(v)}).catch(()=>{if(live)setDetail(null)});return()=>{live=false}},[latest?.id,latest?.evidencia]);
 useEffect(()=>{let live=true;if(filter)call('placas/'+encodeURIComponent(filter)+'/historial').then(v=>{if(live)setFiltered(v)}).catch(e=>{if(live)setMessage(String(e))});return()=>{live=false}},[filter,steps]);
 function filterBy(p:string){setFilter(p);setFiltered(p?[]:null);setPage(0)}
 function stateLabel(v:string){return ({ERROR_OCR:'Placa por confirmar',SIN_PLACA:'Placa sin lectura',REVISION_MANUAL:'Por revisar'} as Record<string,string>)[v]??v.replaceAll('_',' ')}
 useEffect(()=>{call('historial').then(data=>{setSteps(data);setActive(true)}).catch(()=>{});},[]);
 useEffect(()=>{
   if(!active)return;
   let events:EventSource;
   function connect(){
     events?.close();
     events=new EventSource('/api/v1/events/stream');
     events.addEventListener('step.snapshot',e=>{setSteps(JSON.parse(e.data));setMessage('En línea')});
     events.addEventListener('tarifas.updated',e=>setRevenue(String(JSON.parse(e.data).total_bob)));
     events.addEventListener('alert.snapshot',e=>{const latest=JSON.parse(e.data)[0];setAlarm(latest?'Alerta · '+latest.tipo:'')});
     events.addEventListener('alert.created',e=>setAlarm('Alerta · '+JSON.parse(e.data).tipo));
     events.onerror=()=>setMessage('Reconectando con la caseta…');
   }
   function resume(){if(!document.hidden)connect()}
   connect();
   window.addEventListener('online',resume);
   document.addEventListener('visibilitychange',resume);
   return ()=>{events.close();window.removeEventListener('online',resume);document.removeEventListener('visibilitychange',resume)};

 },[active]);
 async function login(){
  try{
   await googleLogin();
   setActive(true)
  }catch(e){setMessage(String(e))}
 }
 return <><div className="mast"><header>CONTROL DE PEAJE · LA PAZ</header><h1>Centro de operaciones</h1></div>
 {!active?<button onClick={login}>Continuar con Google</button>:<>
 <Photo/>
 <section><h2>Consulta de placa</h2><form onSubmit={async e=>{e.preventDefault();try{const r=await call('consulta/'+encodeURIComponent(plate));setAnswer(r.respuesta);setMatches(r.sugerencias);filterBy(r.sugerencias[0]??(r.ultimo_paso?r.ultimo_paso.placa:''))}catch(e){setAnswer(String(e))}}}><input aria-label="Placa" value={plate} onChange={e=>setPlate(e.target.value)} placeholder="1234ABC" required/><button>Consultar</button></form><output>{answer}</output>{matches.map(p=><button key={p} onClick={()=>filterBy(p)}>{p}</button>)}</section>
 <section><h2>Pasos recientes</h2><p>Total de tarifas calculadas: {revenue} Bs</p><p role="alert">{stateLabel(alarm.replace("Alerta · ",""))}</p>{filter&&<p>Placa {filter} <button onClick={()=>filterBy("")}>Ver todos</button></p>}{rows.length===0?<p>Aún no hay pasos registrados.</p>:<div className="scroll"><table><thead><tr>{['Hora','Placa','Categoría','Ejes','Sentido','Estado','Tarifa calculada','Evidencia'].map(t=><th key={t}>{t}</th>)}</tr></thead><tbody>{rows.slice(current*6,current*6+6).map(s=><tr key={s.id}><td>{new Date(s.fecha).toLocaleTimeString('es-BO',{timeZone:'America/La_Paz'})}</td><td>{s.placa||'Sin lectura'}</td><td>{s.categoria}</td><td>{s.ejes??'—'}</td><td>{s.sentido}</td><td>{stateLabel(s.estado)}</td><td>{s.ejes!=null&&(s.monto??s.tarifa_referencia)!=null?(s.monto??s.tarifa_referencia)+' Bs.':'—'}</td><td><a href={'/api/v1/evidencias/'+s.evidencia}><img loading="lazy" width="96" alt="Detecciones del paso" src={'/api/v1/evidencias/'+s.evidencia}/></a>{['REVISION_MANUAL','SIN_PLACA','ERROR_OCR'].includes(s.estado)&&<Confirm id={s.id} done={()=>call('historial').then(setSteps)}/>} {canHide&&<button className="quiet" onClick={()=>hide(s.id)}>Quitar del panel</button>}</td></tr>)}</tbody></table></div>}{pages>1&&<nav aria-label="Paginación"><button disabled={!current} onClick={()=>setPage(current-1)}>Anterior</button><span>{current+1} de {pages}</span><button disabled={current+1>=pages} onClick={()=>setPage(current+1)}>Siguiente</button></nav>}</section>
 {latest&&detail&&<section><h2>Última inferencia de caseta</h2><div className="trace"><a href={'/api/v1/evidencias/'+latest.evidencia}><img alt="Máscaras, placa y centros de rueda" src={'/api/v1/evidencias/'+latest.evidencia}/></a><div>
 <p><b>M1 · Placa</b> {detail.plate||'Lectura pendiente'}</p><p><b>M2 · Vehículo</b> {detail.vehicle_category||'Pendiente'} · {Math.round(100*(detail.category_confidence||0))}%</p>
 <p><b>M3 · Ruedas</b> {detail.axle_keypoints?.length??0} centros detectados</p><p><b>Inferencia</b> {detail.latency_ms??'—'} ms</p>
 <details><summary>Ver respuesta del modelo</summary><pre>{JSON.stringify(detail,null,2)}</pre></details></div></div></section>}<Tools/></>}
 <p role="status">{message}</p></>
}

