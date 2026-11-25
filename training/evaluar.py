"""Compare measured predictions with a manually reviewed, held-out CSV.
Columns: id, placa_real, placa_predicha, ejes_reales, ejes_predichos,
latencia_inferencia_ms, latencia_total_ms. Empty prediction means manual review.
"""
import argparse
import csv
import json
from statistics import mean
import numpy as np


def edits(a,b):
    previous=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        row=[i]
        for j,y in enumerate(b,1):
            row.append(min(row[-1]+1,previous[j]+1,previous[j-1]+int(x!=y)))
        previous=row
    return previous[-1]


def measure(rows):
    plates=[r for r in rows if r["placa_real"]]
    axes=[r for r in rows if r["ejes_reales"]]
    answered=[r for r in axes if r["ejes_predichos"]]
    diff=[abs(int(r["ejes_reales"])-int(r["ejes_predichos"])) for r in answered]
    results={"n":len(rows),"ocr_n":len(plates),"ejes_n":len(axes),"ejes_con_respuesta":len(diff)}
    if plates:
        results["ocr_exacto"]=mean(r["placa_real"]==r["placa_predicha"] for r in plates)
        results["ocr_tasa_error_caracter"]=sum(edits(r["placa_real"],r["placa_predicha"]) for r in plates)/sum(len(r["placa_real"]) for r in plates)
    if axes:
        results["cobertura_ejes"]=len(diff)/len(axes)
        results["acierto_ejes_sobre_total"]=diff.count(0)/len(axes)
    if diff:
        results["mae_ejes_respondidos"]=mean(diff)
    for col in ("latencia_inferencia_ms","latencia_total_ms"):
        data=[float(r[col]) for r in rows if r.get(col)]
        if data:
            results[col]=dict(zip(["p50","p95"],np.percentile(data,[50,95]).tolist()))
    return results


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv")
    with open(parser.parse_args().csv,encoding="utf-8-sig",newline="") as f:
        print(json.dumps(measure(list(csv.DictReader(f))),ensure_ascii=False,indent=2))
