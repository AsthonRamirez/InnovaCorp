"""Motor RAG de ConversaKM: ingesta de PDF (pypdf), embeddings, Chroma, umbral y Gemini con respaldo."""
import os, re, json, time, uuid
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()
DATA = Path(__file__).parent / "data"
UMBRAL = float(os.getenv("UMBRAL", "0.35"))
TOP_K = 4
ADMIN_AREA = "todas"   # el usuario administrador consulta los manuales de todas las áreas
# Si no hay evidencia en los manuales, Gemini responde con información general (con búsqueda web si está disponible).
GENERAL = os.getenv("RESPUESTA_GENERAL", "true").strip().lower() in ("1", "true", "si", "sí", "yes")
AREAS = {"administracion": "Administración", "logistica": "Logística", "recursos_humanos": "Recursos Humanos",
         "ti": "TI", "soporte_interno": "Soporte Interno", "finanzas": "Finanzas", "ventas": "Ventas",
         "produccion": "Producción", "atencion_cliente": "Atención al Cliente"}
SIN = "No cuento con evidencia suficiente en los manuales a los que tienes acceso para responder esa consulta. Te sugiero contactar a Soporte Interno o a Recursos Humanos."

# ---------- JSON como base de datos ----------
def leer(n):
    p = DATA / f"{n}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
def guardar(n, d):
    (DATA / f"{n}.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------- Modelos de embeddings (carga perezosa) ----------
_m = None
def modelo():
    global _m
    if _m is None:
        from sentence_transformers import SentenceTransformer
        _m = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _m
def vectores(textos):
    return modelo().encode(textos, normalize_embeddings=True).tolist()
def cliente():
    import chromadb
    return chromadb.PersistentClient(path=str(DATA / "chroma"))
def coleccion():
    return cliente().get_or_create_collection("manuales", metadata={"hnsw:space": "cosine"})

# ---------- Ingesta de manuales PDF ----------
def trocear(t, n=700, s=100):
    t = re.sub(r"\s+", " ", t).strip()
    out, i = [], 0
    while i < len(t):
        j = min(i + n, len(t))
        if j < len(t) and t.rfind(" ", i, j) > i:
            j = t.rfind(" ", i, j)
        out.append(t[i:j])
        if j >= len(t): break
        i = max(j - s, i + 1)
    return out

def leer_pdf(ruta):
    """Devuelve el texto de cada página de un PDF (lista de str) usando pypdf."""
    from pypdf import PdfReader
    lector = PdfReader(str(ruta))
    if lector.is_encrypted:
        try: lector.decrypt("")
        except Exception: raise ValueError("el PDF está protegido con contraseña")
    return [(p.extract_text() or "") for p in lector.pages]

def ingestar():
    previos = {d["id"]: d for d in leer("documentos")}
    docs, ids, textos, metas = [], [], [], []
    for archivo in sorted((DATA / "manuales").glob("*/*.pdf")):
        area, did = archivo.parent.name, f"{archivo.parent.name}/{archivo.stem}"
        if area not in AREAS: continue
        try:
            paginas = leer_pdf(archivo)
        except Exception as e:
            print(f"AVISO: no se pudo leer {archivo.name}: {e}"); continue
        if not any(p.strip() for p in paginas):
            print(f"AVISO: {archivo.name} no tiene texto extraíble (¿PDF escaneado?). Se omite."); continue
        docs.append({"id": did, "titulo": archivo.stem, "area": area, "version": "1.0", "vigencia": "2026-01-01",
                     "estado": previos.get(did, {}).get("estado", "vigente")})
        k = 0
        for pg, texto in enumerate(paginas, 1):
            for frag in trocear(texto):
                k += 1
                ids.append(f"{did}#{k}"); textos.append(frag)
                metas.append({"area": area, "doc_id": did, "titulo": archivo.stem, "fragmento": k, "pagina": pg})
    c = cliente()
    try: c.delete_collection("manuales")
    except Exception: pass
    col = c.get_or_create_collection("manuales", metadata={"hnsw:space": "cosine"})
    if textos:
        col.add(ids=ids, documents=textos, metadatas=metas, embeddings=vectores(textos))
    guardar("documentos", docs)
    print(f"Ingesta lista: {len(docs)} manuales PDF, {len(textos)} fragmentos")

# ---------- Gemini: modelo principal y dos respaldos ----------
SYS = ("Eres ConversaKM, asistente interno de InnovaCorp. Responde SOLO con la información de los fragmentos "
       "entregados, en español claro y por pasos numerados si es un procedimiento. No inventes datos. Si los "
       "fragmentos no contienen la respuesta, usa suficiente=false. Devuelve únicamente JSON: "
       '{"suficiente": true|false, "respuesta": "...", "fuentes": ["nombre exacto del documento usado"]}')

def modelos_gemini():
    nombres = [
        os.getenv("GEMINI_PRIMARY_MODEL", "gemini-4-neon"),
        os.getenv("GEMINI_BACKUP_MODEL_1", "gemini-4-hydrogen"),
        os.getenv("GEMINI_BACKUP_MODEL_2", "gemini-4-carbon")
    ]
    return list(dict.fromkeys(x.strip() for x in nombres if x and x.strip()))

def llamar_llm(pregunta, frs):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("No se configuró GEMINI_API_KEY")
    ctx = "\n\n".join(f"[Documento: {f['documento']} | pág. {f['pagina']} | fragmento: {f['fragmento']}]\n{f['texto']}" for f in frs)
    user = f"Fragmentos de manuales:\n{ctx}\n\nPregunta: {pregunta}"
    errores = []
    for modelo_id in modelos_gemini():
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo_id}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": SYS}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}
        }
        try:
            r = requests.post(url, params={"key": api_key}, json=payload, timeout=60)
            if r.status_code in (401, 403):
                r.raise_for_status()
            if r.status_code == 429 or r.status_code >= 500 or r.status_code == 404:
                errores.append(f"{modelo_id}: HTTP {r.status_code}")
                continue
            r.raise_for_status()
            datos = r.json()
            partes = datos.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            txt = next((p.get("text", "") for p in partes if p.get("text")), "")
            if not txt:
                errores.append(f"{modelo_id}: respuesta vacía")
                continue
            try:
                resultado = json.loads(txt)
            except json.JSONDecodeError:
                m = re.search(r"\{.*\}", txt, re.S)
                if not m: raise ValueError("Gemini no devolvió JSON válido")
                resultado = json.loads(m.group(0))
            if not isinstance(resultado, dict):
                raise ValueError("Formato de respuesta inválido")
            print(f"Gemini respondió con {modelo_id}")
            return resultado, modelo_id
        except requests.HTTPError as e:
            # Errores de credenciales o de solicitud no se solucionan cambiando de modelo.
            raise RuntimeError(f"Error de Gemini ({modelo_id}): {e}") from e
        except Exception as e:
            errores.append(f"{modelo_id}: {e}")
    raise RuntimeError("Todos los modelos Gemini fallaron. " + " | ".join(errores))

def hay_llm():
    return bool(os.getenv("GEMINI_API_KEY", "").strip())

# ---------- Respuesta general de Gemini (cuando los manuales no tienen la información) ----------
SYS_GENERAL = ("Eres ConversaKM, asistente de InnovaCorp. La consulta del usuario NO se encontró en los manuales internos de la empresa. "
               "Responde con información general y confiable en español claro y conciso, buscando en la web si es necesario. "
               "No presentes la respuesta como política o procedimiento oficial de InnovaCorp y no inventes datos internos de la "
               "empresa (formatos, plazos, montos, responsables). Si la pregunta trata de un trámite interno que no conoces, dilo "
               "y sugiere con qué área consultarlo.")

def llamar_general(pregunta):
    """Gemini responde por su cuenta. Primero con búsqueda en Google (grounding); si no está disponible, sin búsqueda."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key: raise RuntimeError("No se configuró GEMINI_API_KEY")
    errores = []
    for con_busqueda in (True, False):
        for modelo_id in modelos_gemini():
            payload = {"systemInstruction": {"parts": [{"text": SYS_GENERAL}]},
                       "contents": [{"role": "user", "parts": [{"text": pregunta}]}],
                       "generationConfig": {"temperature": 0.3}}
            if con_busqueda: payload["tools"] = [{"google_search": {}}]
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{modelo_id}:generateContent",
                                  params={"key": api_key}, json=payload, timeout=90)
            except requests.RequestException as e:
                errores.append(f"{modelo_id}: {e}"); continue
            if r.status_code in (401, 403) and not con_busqueda:
                raise RuntimeError(f"Credenciales de Gemini rechazadas (HTTP {r.status_code})")
            if r.status_code != 200:
                errores.append(f"{modelo_id}{' +búsqueda' if con_busqueda else ''}: HTTP {r.status_code}"); continue
            cand = (r.json().get("candidates") or [{}])[0]
            partes = cand.get("content", {}).get("parts", [])
            texto = "".join(p.get("text", "") for p in partes if not p.get("thought")).strip()
            if not texto:
                errores.append(f"{modelo_id}: respuesta vacía"); continue
            web, vistos = [], set()
            for c in (cand.get("groundingMetadata") or {}).get("groundingChunks", []):
                w = c.get("web") or {}
                if w.get("uri") and w["uri"] not in vistos:
                    vistos.add(w["uri"]); web.append({"titulo": w.get("title") or w["uri"], "url": w["uri"]})
            return texto, web, modelo_id, con_busqueda
    raise RuntimeError("Gemini no pudo responder. " + " | ".join(errores))

def sin_o_general(pregunta, sin):
    """Sin evidencia en los manuales: devuelve el aviso, o una respuesta general de Gemini si está habilitada."""
    if not (GENERAL and hay_llm()): return sin
    try:
        texto, web, modelo_usado, con_busqueda = llamar_general(pregunta)
    except Exception as e:
        print("AVISO: no se pudo generar la respuesta general:", e); return sin
    modo = f"general (Gemini {modelo_usado}{' + búsqueda web' if con_busqueda else ''})"
    return {**sin, "respuesta": texto, "fuentes_web": web, "general": True, "modo": modo}

# ---------- Consulta ----------
def filtro_area(area):
    return {} if area == ADMIN_AREA else {"where": {"area": area}}

def responder(area, pregunta):
    vigentes = {d["id"] for d in leer("documentos") if d["estado"] == "vigente"}
    r = coleccion().query(query_embeddings=vectores([pregunta]), n_results=8, **filtro_area(area))
    frs = [{"texto": t, "documento": m["titulo"], "area": m["area"], "fragmento": m["fragmento"], "pagina": m.get("pagina", 1), "puntaje": round(1 - d, 3)}
           for t, m, d in zip(r["documents"][0], r["metadatas"][0], r["distances"][0])
           if m["doc_id"] in vigentes][:TOP_K]
    top = frs[0]["puntaje"] if frs else 0.0
    sin = {"respuesta": SIN, "fuentes": [], "fuentes_web": [], "general": False, "puntaje": top, "suficiente": False, "modo": "sin evidencia"}
    if top < UMBRAL: return sin_o_general(pregunta, sin)
    modo = "llm"
    try:
        if not hay_llm(): raise RuntimeError("Sin GEMINI_API_KEY")
        j, modelo_usado = llamar_llm(pregunta, frs)
        cit = [x for x in j.get("fuentes", []) if x in {f["documento"] for f in frs}]
        if not j.get("suficiente") or not cit: return sin_o_general(pregunta, sin)
        resp = j["respuesta"]
        modo = f"Gemini ({modelo_usado})"
    except Exception:
        modo = "extractivo (sin Gemini)"
        sel = frs[:2]
        cit = list(dict.fromkeys(f["documento"] for f in sel))
        resp = "Esto indican los manuales:\n\n" + "\n\n".join(f["texto"] for f in sel)
    fuentes = [{"documento": d, "area": next(f["area"] for f in frs if f["documento"] == d),
                "fragmentos": sorted({f["fragmento"] for f in frs if f["documento"] == d}),
                "paginas": sorted({f["pagina"] for f in frs if f["documento"] == d})} for d in cit]
    return {"respuesta": resp, "fuentes": fuentes, "fuentes_web": [], "general": False, "puntaje": top, "suficiente": True, "modo": modo}

def mejor_puntaje(area, pregunta):
    """Mayor similitud de coseno de la pregunta contra manuales vigentes del área (calibración del umbral)."""
    r = coleccion().query(query_embeddings=vectores([pregunta]), n_results=1, **filtro_area(area))
    return round(1 - r["distances"][0][0], 3) if r["distances"][0] else 0.0

# ---------- Registro ----------
def registrar(usuario, area, pregunta, res):
    reg = leer("registro"); rid = uuid.uuid4().hex[:8]
    reg.append({"id": rid, "fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "usuario": usuario, "area": area,
                "pregunta": pregunta, "respuesta": res["respuesta"], "fuentes": res["fuentes"],
                "fuentes_web": res.get("fuentes_web", []), "general": res.get("general", False),
                "puntaje": res["puntaje"], "modo": res["modo"], "util": None})
    guardar("registro", reg); return rid

def valorar(rid, usuario, util):
    reg = leer("registro")
    for e in reg:
        if e["id"] == rid and e["usuario"] == usuario:
            e["util"] = util; guardar("registro", reg); return True
    return False

if __name__ == "__main__":
    ingestar()
