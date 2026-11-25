"""Ayuda a elegir el UMBRAL: muestra el mejor puntaje de preguntas con y sin respuesta documental. Uso: python calibrar.py"""
import rag
from casos import CASOS, SIN
con = [(a, q, rag.mejor_puntaje(a, q)) for a, q, _, e in CASOS if e not in (SIN, None)]
sin = [(a, q, rag.mejor_puntaje(a, q)) for a, q, _, e in CASOS if e == SIN]
for t, L in (("CON respuesta en manuales", con), ("SIN respuesta (fuera de área o inexistente)", sin)):
    print(f"\n{t}"); [print(f"  {p:<7}{a:<18}{q[:70]}") for a, q, p in sorted(L, key=lambda x: x[2])]
lo, hi = min(p for *_, p in con), max(p for *_, p in sin)
print(f"\nMenor puntaje CON respuesta: {lo} | Mayor puntaje SIN respuesta: {hi}")
print(f"Umbral sugerido: {round((lo+hi)/2,2)}" if lo > hi else "Los rangos se traslapan: agrega más texto a los manuales o ajusta el umbral a mano.")
