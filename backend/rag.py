"""Motor RAG de ConversaKM: ingesta TXT, embeddings, Chroma, umbral y Gemini con respaldo."""
import os, re, json, time, uuid
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()
DATA = Path(__file__).parent / "data"
UMBRAL = float(os.getenv("UMBRAL", "0.35"))
TOP_K = 4
AREAS = {"administracion": "Administración", "logistica": "Logística", "recursos_humanos": "Recursos Humanos",
         "ti": "TI", "soporte_interno": "Soporte Interno", "finanzas": "Finanzas", "ventas": "Ventas",
         "produccion": "Producción", "atencion_cliente": "Atención al Cliente"}
SIN = "No cuento con evidencia suficiente en los documentos de tu área para responder esa consulta. Te sugiero contactar a Soporte Interno o a Recursos Humanos."

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

# ---------- Ingesta de manuales TXT ----------
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

def ingestar():
    previos = {d["id"]: d for d in leer("documentos")}
    docs, ids, textos, metas = [], [], [], []
    base = DATA / "manuales"
    archivos = sorted(base.glob("*/*.txt"))
    for archivo in archivos:
        area, did = archivo.parent.name, f"{archivo.parent.name}/{archivo.stem}"
        if area not in AREAS: continue
        docs.append({"id": did, "titulo": archivo.stem, "area": area, "version": "1.0", "vigencia": "2026-01-01",
                     "estado": previos.get(did, {}).get("estado", "vigente")})
        texto = archivo.read_text(encoding="utf-8")
        for k, frag in enumerate(trocear(texto), 1):
            ids.append(f"{did}#{k}")
            textos.append(frag)
            metas.append({"area": area, "doc_id": did, "titulo": archivo.stem, "fragmento": k})
    c = cliente()
    try: c.delete_collection("manuales")
    except Exception: pass
    col = c.get_or_create_collection("manuales", metadata={"hnsw:space": "cosine"})
    if textos:
        col.add(ids=ids, documents=textos, metadatas=metas, embeddings=vectores(textos))
    guardar("documentos", docs)
    print(f"Ingesta lista: {len(docs)} manuales TXT, {len(textos)} fragmentos")

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
    ctx = "\n\n".join(f"[Documento: {f['documento']} | fragmento: {f['fragmento']}]\n{f['texto']}" for f in frs)
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
                m = re.search(r"\\{.*\\}", txt, re.S)
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

# ---------- Consulta ----------
def responder(area, pregunta):
    vigentes = {d["id"] for d in leer("documentos") if d["estado"] == "vigente"}
    r = coleccion().query(query_embeddings=vectores([pregunta]), n_results=8, where={"area": area})
    frs = [{"texto": t, "documento": m["titulo"], "fragmento": m["fragmento"], "puntaje": round(1 - d, 3)}
           for t, m, d in zip(r["documents"][0], r["metadatas"][0], r["distances"][0])
           if m["doc_id"] in vigentes][:TOP_K]
    top = frs[0]["puntaje"] if frs else 0.0
    sin = {"respuesta": SIN, "fuentes": [], "puntaje": top, "suficiente": False, "modo": "sin evidencia"}
    if top < UMBRAL: return sin
    modo = "llm"
    try:
        if not hay_llm(): raise RuntimeError("Sin GEMINI_API_KEY")
        j, modelo_usado = llamar_llm(pregunta, frs)
        cit = [x for x in j.get("fuentes", []) if x in {f["documento"] for f in frs}]
        if not j.get("suficiente") or not cit: return sin
        resp = j["respuesta"]
        modo = f"Gemini ({modelo_usado})"
    except Exception:
        modo = "extractivo (sin Gemini)"
        sel = frs[:2]
        cit = list(dict.fromkeys(f["documento"] for f in sel))
        resp = "Esto indican los manuales de tu área:\n\n" + "\n\n".join(f["texto"] for f in sel)
    fuentes = [{"documento": d, "fragmentos": sorted({f["fragmento"] for f in frs if f["documento"] == d})} for d in cit]
    return {"respuesta": resp, "fuentes": fuentes, "puntaje": top, "suficiente": True, "modo": modo}

def mejor_puntaje(area, pregunta):
    """Mayor similitud de coseno de la pregunta contra manuales vigentes del área (calibración del umbral)."""
    r = coleccion().query(query_embeddings=vectores([pregunta]), n_results=1, where={"area": area})
    return round(1 - r["distances"][0][0], 3) if r["distances"][0] else 0.0

# ---------- Registro ----------
def registrar(usuario, area, pregunta, res):
    reg = leer("registro"); rid = uuid.uuid4().hex[:8]
    reg.append({"id": rid, "fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "usuario": usuario, "area": area,
                "pregunta": pregunta, "respuesta": res["respuesta"], "fuentes": res["fuentes"],
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
