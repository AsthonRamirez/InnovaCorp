"""Crea usuarios.json (uno por área con contraseña innova123, más el usuario admin) y deja vacíos documentos.json y registro.json.
Los manuales ya vienen en data/manuales/<area>/. Después ejecuta: python rag.py
El usuario admin consulta los manuales de TODAS las áreas. Su contraseña se toma de ADMIN_PASSWORD (.env); por defecto es admin123."""
import os, hashlib
from rag import AREAS, ADMIN_AREA, guardar

def usuario(nombre_usuario, nombre, area, clave):
    salt = os.urandom(8).hex()
    return {"usuario": nombre_usuario, "nombre": nombre, "area": area, "salt": salt,
            "hash": hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(salt), 100_000).hex()}

usuarios = [usuario(a, f"Colaborador de {AREAS[a]}", a, "innova123") for a in AREAS]
usuarios.append(usuario("admin", "Administrador", ADMIN_AREA, os.getenv("ADMIN_PASSWORD", "admin123")))
guardar("usuarios", usuarios); guardar("documentos", []); guardar("registro", [])
print("usuarios.json (10 usuarios, incluido admin), documentos.json y registro.json creados")
