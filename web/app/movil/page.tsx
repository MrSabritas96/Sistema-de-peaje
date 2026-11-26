'use client';
import Photo from '../Photo';
import {useEffect,useRef,useState} from 'react';
import {call,googleLogin} from '../client';

type Detection={box:number[];label:string;score:number};
type Overlay={width:number;height:number;objects:Detection[]};
const colors:Record<string,string>={auto:'#69bcff',minibus:'#45e1a1',persona:'#ff96ce',bus:'#ff975e',camion:'#c39aff',moto:'#ffd565'};

export default function Mobile(){
 const [access,setAccess]=useState(false),[running,setRunning]=useState(false);
 const [booths,setBooths]=useState<{id:number;nombre:string}[]>([]);
 const [boot,setBoot]=useState(''),[direction,setDirection]=useState('ENTRADA');
 const [notice,setNotice]=useState(''),[result,setResult]=useState(''),[overlay,setOverlay]=useState<Overlay|null>(null);
 const [answer,setAnswer]=useState(''),[aspect,setAspect]=useState(4/3);
 const video=useRef<HTMLVideoElement>(null);
 useEffect(()=>{call('sesion').then(()=>setAccess(true)).catch(()=>{})},[]);
 useEffect(()=>{
  if(access)call('casetas').then(rows=>{setBooths(rows);setBoot(String(rows[0]?.id??''))}).catch(()=>setNotice('No se pudieron cargar las casetas activas.'));
 },[access]);
 useEffect(()=>{
  if(!running)return;
  const controller=new AbortController(),session=crypto.randomUUID(),canvas=document.createElement('canvas');
  let stream:MediaStream|undefined,timer:ReturnType<typeof setTimeout>;
  const stop=()=>{if(document.hidden)setRunning(false)};
  document.addEventListener('visibilitychange',stop);
  async function start(){
   try{
    stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:1280}},audio:false});
    if(controller.signal.aborted){stream.getTracks().forEach(t=>t.stop());return}
    const player=video.current!;
    player.srcObject=stream;await player.play();
    async function capture(){
     if(controller.signal.aborted)return;
     try{
      const w=player.videoWidth,h=player.videoHeight;
      if(!w||!h){timer=setTimeout(capture,150);return}
      const scale=Math.min(1,1440/Math.max(w,h));canvas.width=Math.round(w*scale);canvas.height=Math.round(h*scale);
      canvas.getContext('2d')!.drawImage(player,0,0,canvas.width,canvas.height);setAspect(w/h);
      const blob=await new Promise<Blob|null>(resolve=>canvas.toBlob(resolve,'image/jpeg',.82));
      if(!blob)throw Error('No se pudo capturar la imagen');
      const form=new FormData();form.append('file',blob,'camara.jpg');form.append('caseta',boot);form.append('sentido',direction);form.append('sesion',session);
      const r=await call('pasos/frame',{method:'POST',body:form,signal:controller.signal});
      if(controller.signal.aborted)return;
      setOverlay(r.overlay);setNotice('');
      setResult([r.placa,r.categoria,r.ejes!=null?r.ejes+' ejes':'',r.sentido,r.monto!=null?r.monto+' Bs.':'',r.estado?.replaceAll('_',' ')].filter(Boolean).join(' · '));
      timer=setTimeout(capture,100);
     }catch(e){if(!controller.signal.aborted){setNotice(String(e));setRunning(false)}}
    }
    await capture();
   }catch(e){if(!controller.signal.aborted){setNotice('Revisa el permiso de cámara del navegador. '+String(e));setRunning(false)}}
  }
  start();
  return()=>{controller.abort();clearTimeout(timer);stream?.getTracks().forEach(t=>t.stop());document.removeEventListener('visibilitychange',stop)};
 },[running,boot,direction]);
 return <><div className="mast"><header>CONTROL DE PEAJE · LA PAZ</header><h1>Caseta móvil</h1></div>
 {!access?<section><h2>Acceso del operador</h2><button onClick={async()=>{try{await googleLogin();setAccess(true);setNotice('')}catch(e){setNotice(String(e))}}}>Continuar con Google</button></section>:<>
 <section className="cameraCard"><h2>Cámara de la caseta</h2><div className="controls"><label>Caseta<select value={boot} disabled={running||!booths.length} onChange={e=>setBoot(e.target.value)}>{!booths.length&&<option value="">Sin casetas disponibles</option>}{booths.map(b=><option key={b.id} value={b.id}>{b.nombre} · #{b.id}</option>)}</select></label><label>Sentido<select value={direction} disabled={running} onChange={e=>setDirection(e.target.value)}><option>ENTRADA</option><option>SALIDA</option><option value="AUTO">Automático</option></select></label></div>
 <div className="viewfinder" style={{aspectRatio:aspect}}><video ref={video} muted playsInline autoPlay/>{!running&&<span>Cámara detenida</span>}
 {running&&overlay&&<svg viewBox={'0 0 '+overlay.width+' '+overlay.height} preserveAspectRatio="none" aria-label="Detecciones del último fotograma">{overlay.objects.map((o,i)=>{const [x,y,r,b]=o.box,c=colors[o.label]||'white';return <g key={i}><rect x={x} y={y} width={r-x} height={b-y} fill="none" stroke={c} strokeWidth="3"/><text x={x+4} y={y+22} stroke="#10252d" strokeWidth="4" paintOrder="stroke" fill={c} fontWeight="bold" fontSize="23">{o.label} {Math.round(o.score*100)}%</text></g>})}</svg>}</div>
 <button disabled={!Number.isInteger(+boot)||+boot<1} onClick={()=>{setNotice('');setOverlay(null);setResult('');setRunning(!running)}}>{running?'Detener cámara':'Iniciar captura'}</button><output aria-live="polite">{result||(running?'Esperando la primera lectura…':'')}</output></section>
 <Photo/>
 <section><h2>Consulta de vehículo</h2><form onSubmit={async e=>{e.preventDefault();const f=new FormData(e.currentTarget);setAnswer('Consultando…');try{const r=await call('chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pregunta:f.get('pregunta')})});setAnswer(r.respuesta)}catch(err){setAnswer(String(err))}}}><label>Placa o pregunta<input name="pregunta" placeholder="1234ABC"/></label><button>Consultar</button></form><output>{answer}</output></section></>}
 {notice&&<p role="alert">{notice}</p>}</>
}
