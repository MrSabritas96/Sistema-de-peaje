import {initializeApp,getApps} from 'firebase/app';
import {getAuth,GoogleAuthProvider,signInWithPopup} from 'firebase/auth';

export async function call(path:string,options?:RequestInit){
  const response=await fetch('/api/v1/'+path,options);
  if(!response.ok)throw new Error((await response.json()).detail||'Error de conexión');
  return response.json();
}
export async function googleLogin(){
   const fb=getApps()[0]||initializeApp({appId:process.env.NEXT_PUBLIC_FIREBASE_APP_ID,apiKey:process.env.NEXT_PUBLIC_FIREBASE_API_KEY,authDomain:process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,projectId:process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID});
   const session=await signInWithPopup(getAuth(fb),new GoogleAuthProvider());
   await call('auth/google',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id_token:await session.user.getIdToken()})});
}
