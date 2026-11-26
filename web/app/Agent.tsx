'use client';
import {useState} from 'react';
import {call} from './client';

export function Agent(){
 const [question,setQuestion]=useState(''),[file,setFile]=useState<File|null>(null);
 const [photo,setPhoto]=useState(false),[busy,setBusy]=useState(false);
 const [reply,setReply]=useState<{query:string;text:string}|null>(null),[error,setError]=useState('');
 async function consult(text:string){
   if(busy||!(photo?file:text.trim()))return;
   setBusy(true);setError('');
   try{
     let result;
     if(photo&&file){
       const body=new FormData();body.append('file',file);
       result=await call('chat/imagen',{method:'POST',body});
     }else{
       result=await call('chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pregunta:text.trim()})});
     }
     setReply({query:photo&&file?file.name:text,text:result.respuesta});
   }catch(e){setError(e instanceof Error?e.message:'No se pudo completar la consulta.')}
   finally{setBusy(false)}
 }
 return <section className="queryAgent"><h2>Agente de consultas</h2>
 <div className="queryModes">{['Por texto','Por foto'].map((label,i)=><button key={label} disabled={busy} aria-pressed={photo===Boolean(i)} onClick={()=>{setPhoto(Boolean(i));setError('');setFile(null)}}>{label}</button>)}</div>
 {!photo&&<div className="queryExamples">{['¿Cuántos vehículos están registrados?','¿Cuántos pasos hubo hoy?'].map(q=><button disabled={busy} key={q} onClick={()=>{setQuestion(q);void consult(q)}}>{q}</button>)}</div>}
 <form onSubmit={e=>{e.preventDefault();void consult(question)}}>{photo?<label>Foto de la placa<input required disabled={busy} type="file" accept="image/jpeg,image/png,image/webp" onChange={e=>setFile(e.target.files?.[0]??null)}/></label>:<label>Pregunta o placa<input disabled={busy} value={question} onChange={e=>setQuestion(e.target.value)} placeholder="¿Cuándo pasó la placa 4106EPU?"/></label>}<button disabled={busy||!(photo?file:question.trim())}>{busy?'Consultando…':'Consultar'}</button></form>
 {error&&<p role="alert">{error}</p>}<div aria-live="polite">{reply&&<div className="queryReply"><small>{reply.query}</small><p>{reply.text}</p></div>}</div></section>
}
