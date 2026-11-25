"""Consultas de resumen en español. El usuario solo aporta valores parametrizados."""
import re
import unicodedata
from .domain import db, query

def resumen(pregunta):
    frase = unicodedata.normalize("NFKD", pregunta.casefold())
    frase = "".join(c for c in frase if not unicodedata.combining(c))
    def tiene(patron):
        return re.search(patron, frase) is not None

    padron = tiene(r"registrad|inscrit|padron|matriculad|dadas? de alta")
    observado = tiene(r"detectad|observad|captad|capturad|ley[oó]|leidas?|pasaron")
    placas = tiene(r"placas?|matriculas?|vehiculos?|autos?")
    pasos = tiene(r"\b(pasos?|cruces|transitos?)\b")
    dinero = tiene(r"recaud|cobrado|cobro total")
    pide = tiene(r"cuant|cantidad|total|numero de|hay|dime|muestrame")
    if not pide or not (placas or pasos or dinero or tiene(r"minibus|camion|motos?|buses")):
        return None
    if tiene(r"semana|mes|lunes|martes|miercoles|jueves|viernes|sabado|domingo|entre|desde|sin |no registr|por caseta|por categoria|por tipo|saldo|\d{1,2}[/.-]\d{1,2}"):
        return None
    hoy, ayer = tiene(r"\bhoy\b"), tiene(r"\bayer\b")
    if pasos and tiene(r"pasos? registrados?"):
        padron=False
    if hoy and ayer or padron and (observado or pasos or dinero or hoy or ayer):
        return None
    categorias = [c for c,pat in (("auto",r"\bautos?\b"),("minibus",r"\bminibus(?:es)?\b"),("bus",r"\bbus(?:es)?\b"),("camion",r"\bcamion(?:es)?\b"),("moto",r"\bmotos?\b")) if tiene(pat)]
    if len(categorias)>1:
        return None
    condiciones=[]
    valores={}
    patrones=[("inicio",r"(?:empiez|comienz)\w* (?:por|con|en) (?:el |la )?([a-z0-9])\b"),("fin",r"(?:termin|acab)\w* (?:por|con|en) (?:el |la )?([a-z0-9])\b"),("contenido",r"(?:contien|conteng)\w* (?:la letra |el numero )?([a-z0-9])\b")]
    filtros=[]
    for nombre,pat in patrones:
        match=re.search(pat,frase)
        if match:
            valor=match[1].upper()
            valores[nombre]={"inicio":valor+"%","fin":"%"+valor,"contenido":"%"+valor+"%"}[nombre]
            condiciones.append("placa LIKE :"+nombre)
            filtros.append({"inicio":"empieza por ","fin":"termina en ","contenido":"contiene "}[nombre]+valor)
    if tiene(r"empiez|comienz|termin|contien|conteng|acab") and not filtros:
        return None
    if categorias:
        condiciones.append("categoria=:categoria")
        valores["categoria"]=categorias[0]
    if hoy or ayer:
        condiciones.append("(fecha AT TIME ZONE 'America/La_Paz')::date=(now() AT TIME ZONE 'America/La_Paz')::date-CAST(:dias AS integer)")
        valores["dias"]=int(ayer)
    sufijo=(" de tipo "+categorias[0] if categorias else "")+(" hoy" if hoy else " ayer" if ayer else "")
    if filtros:
        sufijo+=" ("+", ".join(filtros)+")"
    if not (padron or observado or pasos or dinero or hoy or ayer or categorias or filtros):
        with db.connect() as c:
            reg=query(c,"SELECT count(*) FROM vehiculos WHERE activo AND NOT is_demo").scalar_one()
            obs=query(c,"SELECT count(DISTINCT NULLIF(placa,'')) FROM pasos").scalar_one()
        return {"respuesta":f"Hay {reg} vehículos registrados y {obs} placas distintas leídas en los pasos.","registrados":reg,"detectadas":obs}
    if dinero:
        fuente,expr,concepto="pasos","coalesce(sum(monto),0)","Total cobrado"
        condiciones.append("estado='PAGADO'")
    elif pasos:
        fuente,expr,concepto="pasos","count(*)","Pasos registrados en el historial"
    elif padron:
        fuente,expr,concepto="vehiculos","count(*)","Vehículos inscritos activos"
        condiciones.extend(["activo","NOT is_demo"])
    else:
        fuente,expr,concepto="pasos","count(DISTINCT NULLIF(placa,''))","Placas distintas detectadas"
    where=" WHERE "+" AND ".join(condiciones) if condiciones else ""
    with db.connect() as c:
        total=query(c,f"SELECT {expr} FROM {fuente}{where}",**valores).scalar_one()
    return {"respuesta":f"{concepto}{sufijo}: {total}"+(" Bs." if dinero else "."),"total":total}
