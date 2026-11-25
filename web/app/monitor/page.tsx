'use client';
import {useEffect,useState} from 'react';
type Evento={hora:string;tipo:string;datos:string};
export default function Monitor(){
 const [services,setServices]=useState<Record<string,unknown>>({});
 const [events,setEvents]=useState<Evento[]>([]);
 const [status,setStatus]=useState('Conectando');
 useEffect(()=>{
   let active=true;
   const probe=()=>fetch('/api/v1/monitor',{cache:'no-store'}).then(async r=>{
     if(!r.ok)throw Error(r.status===401?'Inicia sesión en el centro de operaciones':'Consulta de servicios interrumpida');
     const data=await r.json();if(active)setServices(data);
   }).catch(e=>{if(active)setServices({Estado:String(e.message)})});
   probe();const timer=setInterval(probe,30000);
   const stream=new EventSource('/api/v1/events/stream');
   stream.onopen=()=>setStatus('En línea');stream.onerror=()=>setStatus('Reconectando');
   for(const tipo of ['step.snapshot','step.created','step.updated','alert.created','revenue.updated','heartbeat']){
     stream.addEventListener(tipo,e=>{
       const data=JSON.parse(e.data);
       const datos=tipo==='step.snapshot'?data.length+' pasos en el historial':JSON.stringify(data);
       setEvents(prev=>[{hora:new Date().toLocaleTimeString('es-BO'),tipo,datos},...prev].slice(0,40));
     });
   }
   return()=>{active=false;clearInterval(timer);stream.close()};
 },[]);
 return <><div className="mast"><a href="/">← Centro de operaciones</a><h1>Monitor en vivo</h1><span>{status}</span></div>
 <div className="services">{Object.entries(services).map(([name,value])=><section key={name}><h2>{name}</h2><pre>{JSON.stringify(value,null,2)}</pre></section>)}</div>
 <section><h2>Eventos de la caseta</h2><div className="terminal">{events.length===0?'Esperando el primer evento…':events.map((e,i)=><p key={i}><b>{e.hora} · {e.tipo}</b><br/>{e.datos}</p>)}</div></section>
 <section><h2>Consultar origen</h2><div className="trace"><a href="/api/v1/monitor">Respuesta de los servicios</a><a href="/api/v1/historial">Filas del historial</a><a href="https://console.firebase.google.com/">Consola de Firebase</a><a href="https://console.runpod.io/pods">Pod de inferencia</a></div></section></>;
}
