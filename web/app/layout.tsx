import type { ReactNode } from 'react';
import './style.css';
export default function Layout({children}:{children:ReactNode}) {
  return <html lang="es"><body><main><nav className="stationNav" aria-label="Navegación principal"><a href="/movil">Caseta móvil</a><a href="/">Operaciones</a><a href="/monitor">Monitor</a></nav>{children}</main></body></html>
}
