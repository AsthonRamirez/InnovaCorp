"""Parte 4: ejecuta los casos, imprime la tabla y las métricas, y guarda resultados_pruebas.csv. Uso: python pruebas.py"""
import csv, rag
from casos import CASOS, SIN
filas, ok, fund, rech, n_con, n_sin = [], 0, 0, 0, 0, 0
print(f"{'#':<3}{'Tipo':<20}{'Esperado':<34}{'Obtenido':<34}{'Punt.':<7}Cumple")
for i, (a, q, tipo, esp) in enumerate(CASOS, 1):
    r = rag.responder(a, q); fu = [f["documento"] for f in r["fuentes"]]
    obt = ", ".join(fu) if fu else ("sin evidencia (resp. general Gemini)" if r.get("general") else "sin evidencia")
    if esp == SIN: cumple = not fu; n_sin += 1; rech += cumple
    elif esp is None: cumple = True
    else:
        lista = esp if isinstance(esp, list) else [esp]; cumple = any(x in fu for x in lista); n_con += 1; fund += cumple
    ok += cumple
    e = "sin evidencia" if esp == SIN else ("justificable" if esp is None else (esp if isinstance(esp, str) else " / ".join(esp)))
    print(f"{i:<3}{tipo:<20}{e[:32]:<34}{obt[:32]:<34}{r['puntaje']:<7}{'Sí' if cumple else 'No'}")
    filas.append([i, a, q, tipo, e, obt, r["puntaje"], "Sí" if cumple else "No", r["respuesta"].replace("\n", " ")])
print(f"\nExactitud (respuestas correctas): {ok}/{len(CASOS)} = {100*ok/len(CASOS):.0f}%")
print(f"Fundamentación (con fuente correcta): {fund}/{n_con} = {100*fund/max(n_con,1):.0f}%")
print(f"Rechazo correcto sin evidencia: {rech}/{n_sin} = {100*rech/max(n_sin,1):.0f}%   (umbral={rag.UMBRAL})")
with open("resultados_pruebas.csv", "w", newline="", encoding="utf-8-sig") as f:
    csv.writer(f).writerows([["#", "area", "consulta", "tipo", "esperado", "obtenido", "puntaje", "cumple", "respuesta"]] + filas)
print("Guardado: resultados_pruebas.csv")
