"""API de ConversaKM (FastAPI). El área del usuario se toma del token, nunca del cliente."""
import os, time, hashlib, hmac
import jwt
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import rag

SECRET = os.getenv("JWT_SECRET", "cambia-esta-clave")
app = FastAPI(title="ConversaKM")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
api = APIRouter(prefix="/api")

class Login(BaseModel): usuario: str; password: str
class Chat(BaseModel): pregunta: str
class Fb(BaseModel): id: str; util: bool

def usuario_actual(authorization: str = Header(default="")):
    try: return jwt.decode(authorization.replace("Bearer ", ""), SECRET, algorithms=["HS256"])
    except Exception: raise HTTPException(401, "Sesión inválida o expirada")

@app.on_event("startup")
def inicio():
    rag.asegurar_indice()

@api.post("/login")
def login(d: Login):
    u = next((x for x in rag.leer("usuarios") if x["usuario"] == d.usuario.strip().lower()), None)
    h = hashlib.pbkdf2_hmac("sha256", d.password.encode(), bytes.fromhex(u["salt"]), 100_000).hex() if u else ""
    if not u or not hmac.compare_digest(h, u["hash"]): raise HTTPException(401, "Usuario o contraseña incorrectos")
    tok = jwt.encode({"sub": u["usuario"], "area": u["area"], "exp": time.time() + 8 * 3600}, SECRET, algorithm="HS256")
    return {"token": tok, "nombre": u["nombre"], "area": u["area"], "area_nombre": rag.AREAS.get(u["area"], "Administrador (todas las áreas)")}

@api.post("/chat")
def chat(d: Chat, u=Depends(usuario_actual)):
    if not d.pregunta.strip(): raise HTTPException(400, "Escribe una pregunta")
    res = rag.responder(u["area"], d.pregunta.strip())
    res["id"] = rag.registrar(u["sub"], u["area"], d.pregunta.strip(), res)
    return res

@api.post("/feedback")
def feedback(d: Fb, u=Depends(usuario_actual)):
    return {"ok": rag.valorar(d.id, u["sub"], d.util)}

@api.get("/documentos")
def documentos(u=Depends(usuario_actual)):
    return [x for x in rag.catalogo() if u["area"] == rag.ADMIN_AREA or x["area"] == u["area"]]

app.include_router(api)
