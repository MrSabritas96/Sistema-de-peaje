'use client';
import {useState} from 'react';
import {call} from './client';

type Result={preview:string; placa:string|null; categoria:string|null; ejes:number|null; respuesta:string};
export default function Photo(){
 const [result,setResult]=useState<Result|null>(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 return <section><h2>Consultar por foto</h2><form onSubmit={async e=>{
   e.preventDefault();const body=new FormData(e.currentTarget);
   setBusy(true);setError('');setResult(null);
   try{setResult(await call('analisis/foto',{method:'POST',body}))}
   catch(err){setError(err instanceof Error?err.message:'No se pudo analizar la foto.')}
   finally{setBusy(false)}
 }}>
 <label>Foto del vehículo<input required disabled={busy} type="file" name="file" accept="image/jpeg,image/png,image/webp" onChange={()=>{setResult(null);setError('')}}/></label>
 <button disabled={busy}>{busy?'Analizando foto…':'Analizar foto'}</button></form>
 {error&&<p role="alert">{error}</p>}
 {result&&<article aria-live="polite"><img alt="Foto analizada con las detecciones superpuestas" style={{display:'block',width:'100%',maxHeight:'65vh',objectFit:'contain',background:'#10282e',borderRadius:14}} src={'data:image/jpeg;base64,'+result.preview}/>
 <dl style={{display:'flex',gap:12,flexWrap:'wrap'}}>{Object.entries({'Placa':result.placa,'Categoría':result.categoria,'Ejes':result.ejes}).map(([k,v])=><div key={k} style={{padding:'10px 16px',background:'#edf6f5',borderRadius:10}}><dt>{k}</dt><dd style={{margin:0,fontWeight:700}}>{v??'Sin confirmar'}</dd></div>)}</dl><p>{result.respuesta}</p></article>}</section>
}
