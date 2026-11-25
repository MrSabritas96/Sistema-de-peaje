import React,{useEffect,useRef,useState} from 'react';
import {AppState,Button,Image,ScrollView,Text,TextInput,View} from 'react-native';
import * as Picker from 'expo-image-picker';
import {CameraView,useCameraPermissions} from 'expo-camera';
import {GoogleSignin} from '@react-native-google-signin/google-signin';
import {getApp,getApps,initializeApp} from 'firebase/app';
import {getAuth,GoogleAuthProvider,signInWithCredential} from 'firebase/auth';

const url=process.env.EXPO_PUBLIC_API_URL;
async function api(path:string,options:RequestInit={}){
 if(!url?.startsWith('https://'))throw Error('Falta configurar la URL HTTPS de la API');
 const res=await fetch(url.replace(/\/$/,'')+'/api/v1/'+path,options);
 const data=await res.json();if(!res.ok)throw Error(typeof data.detail==='string'?data.detail:'Solicitud rechazada');return data;
}
export default function App(){
 const [token,save]=useState(''),[mode,setMode]=useState('Consulta'),[permission,requestPermission]=useCameraPermissions();
 const [plate,setPlate]=useState(''),[booth,setBooth]=useState('1'),[direction,setDirection]=useState('ENTRADA'),[running,start]=useState(false),[ready,setReady]=useState(false),[message,show]=useState('');
 const [preview,setPreview]=useState<string|null>(null);
 const [pictureSize,setPictureSize]=useState<string>();
 const camera=useRef<CameraView>(null), busy=useRef(false);
 const picking=useRef(false);
 useEffect(()=>{
  const sub=AppState.addEventListener('change',state=>{
   if(state==='background'&&token&&!picking.current){start(false);save('');setReady(false);setPreview(null);show('');setMode('Consulta');}
  });
  return ()=>sub.remove();
 },[token]);
 async function ask(photo:boolean){
  try{
   let options:RequestInit;
   if(photo){
    picking.current=true;
    const selected=await Picker.launchImageLibraryAsync({mediaTypes:['images'],quality:.85,allowsEditing:true});
    if(selected.canceled)return;
    const file=selected.assets[0],form=new FormData();
    form.append('file',{uri:file.uri,type:file.mimeType||'image/jpeg',name:'consulta.jpg'} as any);
    options={method:'POST',body:form,headers:{Authorization:'Bearer '+token}};
   }else{
    options={method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({pregunta:plate})};
   }
   show((await api(photo?'chat/imagen':'chat',options)).respuesta)
  }catch(e){show(String(e))}finally{picking.current=false}
 }
 async function login(){
  try{
   GoogleSignin.configure({webClientId:process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID});
   await GoogleSignin.hasPlayServices();await GoogleSignin.signOut();const result=await GoogleSignin.signIn();
   if(result.type!=='success'||!result.data.idToken)return;
   const fb=getApps().length?getApp():initializeApp({apiKey:process.env.EXPO_PUBLIC_FIREBASE_API_KEY,projectId:process.env.EXPO_PUBLIC_FIREBASE_PROJECT_ID,appId:process.env.EXPO_PUBLIC_FIREBASE_APP_ID});
   const session=await signInWithCredential(getAuth(fb),GoogleAuthProvider.credential(result.data.idToken));
   const data=await api('auth/google',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id_token:await session.user.getIdToken()})});
   save(data.access_token);show('');
  }catch(e){show(String(e))}
 }
 useEffect(()=>{
  if(!running||!ready||mode!=='Caseta')return;
  let active=true;const session=String(Date.now());
  let capturing=false;
  let pending:string|null=null;
  async function sendLatest(){
   if(busy.current||!pending||!active)return;
   const uri=pending;pending=null;busy.current=true;
   try{
    const form=new FormData();form.append('file',{uri,type:'image/jpeg',name:'frame.jpg'} as any);
    form.append('preview','true');form.append('caseta',booth);form.append('sentido',direction);form.append('sesion',session);
    const r=await api('pasos/frame',{method:'POST',body:form,headers:{Authorization:'Bearer '+token}});
    if(active){
     setPreview(r.preview?'data:image/jpeg;base64,'+r.preview:null);
     show([r.placa||'Placa pendiente',r.categoria,r.ejes!=null?r.ejes+' ejes':'',r.estado==='ERROR_OCR'?'Placa por confirmar':r.estado?.replace(/_/g,' '),r.monto!=null?r.monto+' Bs.':''].filter(Boolean).join(' · '));
    }
   }catch(e){if(active){show(String(e));start(false);active=false}}
   finally{busy.current=false;if(active&&pending)void sendLatest()}
  }
  const timer=setInterval(async()=>{
   if(!active||capturing||pending||!camera.current)return;
   capturing=true;
   try{
    const pic=await camera.current.takePictureAsync({quality:.75,shutterSound:false});
    if(pic&&active){pending=pic.uri;void sendLatest()}
   }catch(e){if(active){show(String(e));start(false)}}
   finally{capturing=false}
  },200);
  return ()=>{active=false;pending=null;clearInterval(timer)}

 },[running,ready,mode,booth,direction,token]);
 return <ScrollView contentContainerStyle={{padding:18,paddingTop:48,gap:12,backgroundColor:'#edf4f4',flexGrow:1}}>
 <View style={{padding:20,backgroundColor:'#103f48',borderRadius:16,borderLeftWidth:6,borderLeftColor:'#efb64d'}}><Text style={{color:'#a9dfd8',fontWeight:'700'}}>CONTROL DE PEAJE</Text><Text style={{fontSize:30,color:'white',fontWeight:'700'}}>La Paz</Text>{Boolean(token)&&<Text style={{color:'white'}}>{mode==='Caseta'?'Caseta '+booth+' · '+direction:'Consulta de vehículos'}</Text>}</View>
 {!token?<Button color="#12695f" title="Continuar con Google" onPress={login}/>:<>
 <Button color="#12695f" title={'Cambiar a modo '+(mode==='Consulta'?'Caseta':'Consulta')} onPress={()=>{start(false);setReady(false);setMode(mode==='Consulta'?'Caseta':'Consulta');show('')}}/>
 {mode==='Consulta'?<><TextInput accessibilityLabel="Placa" placeholder="Placa o pregunta" value={plate} onChangeText={setPlate} autoCapitalize="characters"/>
 <Button color="#12695f" title="Consultar placa" onPress={async()=>{try{show((await api('consulta/'+encodeURIComponent(plate),{headers:{Authorization:'Bearer '+token}})).respuesta)}catch(e){show(String(e))}}}/><Button color="#12695f" title="Preguntar al agente" onPress={()=>ask(false)}/><Button color="#12695f" title="Consultar por foto" onPress={()=>ask(true)}/></>:
 <><Text>Caseta</Text><TextInput value={booth} onChangeText={setBooth} keyboardType="numeric" editable={!running}/>
 <Button color="#12695f" title={direction} disabled={running} onPress={()=>setDirection(direction==='ENTRADA'?'SALIDA':direction==='SALIDA'?'AUTO':'ENTRADA')}/>
 {permission?.granted?<CameraView style={{height:310}} ref={camera} facing="back" pictureSize={pictureSize} onCameraReady={async()=>{try{const sizes=await camera.current?.getAvailablePictureSizesAsync();const best=sizes?.map(size=>({size,w:Math.max(...size.split('x').map(Number))})).filter(s=>s.w>=1280&&s.w<=2048).sort((a,b)=>b.w-a.w)[0];if(best)setPictureSize(best.size)}finally{setReady(true)}}}/>:<Button color="#12695f" title="Permitir cámara" onPress={requestPermission}/>}
 {preview&&<><Text>Último fotograma analizado</Text><Image source={{uri:preview}} resizeMode="contain" style={{height:240,width:'100%'}}/></>}
 <Button color="#12695f" title={running?'Detener captura':'Iniciar captura'} disabled={!ready} onPress={()=>start(!running)}/></>}</>}
 {message&&<Text style={{padding:16,backgroundColor:"white",borderRadius:12,color:"#173f49",fontSize:17}} accessibilityLiveRegion="polite">{message}</Text>}</ScrollView>
}
