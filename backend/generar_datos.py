"""Crea usuarios.json (uno por área, contraseña innova123) y deja vacíos documentos.json y registro.json.
Los manuales ya vienen en data/manuales/<area>/. Después ejecuta: python rag.py"""
import os, hashlib
from rag import AREAS, guardar
usuarios = []
for area in AREAS:
    salt = os.urandom(8).hex()
    usuarios.append({"usuario": area, "nombre": f"Colaborador de {AREAS[area]}", "area": area, "salt": salt,
                     "hash": hashlib.pbkdf2_hmac("sha256", b"innova123", bytes.fromhex(salt), 100_000).hex()})
guardar("usuarios", usuarios); guardar("documentos", []); guardar("registro", [])
print("usuarios.json, documentos.json y registro.json creados")
