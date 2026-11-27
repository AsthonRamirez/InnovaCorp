# ConversaKM

**ConversaKM** es un asistente interno de consulta de manuales para InnovaCorp. Permite que cada colaborador consulte la documentación de su área y recibe respuestas respaldadas por fragmentos de los manuales.

El proyecto utiliza Vue 3 y Vite en el frontend, FastAPI en el backend y un sistema RAG (Retrieval-Augmented Generation) con embeddings y Chroma para recuperar información relevante. Gemini redacta la respuesta a partir de la evidencia recuperada.

## Funcionalidades

- Inicio de sesión de demostración con autenticación JWT.
- Acceso a documentos filtrado por el área incluida en el token.
- Búsqueda semántica de manuales y exclusión de documentos obsoletos.
- Respuestas con nombre del manual y referencia a los fragmentos consultados.
- Rechazo de consultas cuando la evidencia recuperada es insuficiente.
- Gemini con un modelo principal y dos modelos de respaldo.
- Modo extractivo cuando no hay API key o los modelos no están disponibles.
- Registro local de consultas y valoración de respuestas.

## Tecnologías

- **Frontend:** Vue 3, Vite y JavaScript.
- **Backend:** Python, FastAPI y Uvicorn.
- **RAG:** pypdf, Sentence Transformers y Chroma.
- **Documentos:** manuales en formato PDF (texto extraído con pypdf).
- **Modelo generativo:** Gemini API.
- **Datos locales:** JSON.

## Estructura

```text
conversakm/
├── backend/
│   ├── main.py                 # API, login y endpoints
│   ├── rag.py                  # Ingesta, recuperación y respuesta Gemini
│   ├── generar_datos.py        # Genera usuarios y JSON locales
│   ├── casos.py                # Casos de prueba
│   ├── pruebas.py               # Ejecuta pruebas y genera CSV
│   ├── calibrar.py              # Calibración del umbral RAG
│   ├── requirements.txt
│   ├── .env.example
│   └── data/
│       └── manuales/            # 90 manuales PDF por área
├── frontend/
│   ├── src/
│   │   ├── App.vue
│   │   └── main.js
│   ├── package.json
│   └── vite.config.js
├── .gitignore
└── README.md
```

Los manuales se conservan en **un solo formato: PDF**. `rag.py` extrae el texto de cada página con `pypdf`, lo divide en fragmentos y guarda el número de página como metadato, de modo que cada respuesta indica el manual y la página consultada. Los PDF deben tener texto seleccionable (no escaneados como imagen). Cada manual está almacenado una sola vez en `backend/data/manuales/<area>/`.

## Requisitos

- Python 3.10 o superior.
- Node.js 18 o superior y npm.
- Conexión a internet para instalar dependencias y descargar el modelo de embeddings la primera vez.
- Una clave de Gemini API es opcional. Sin ella, el chatbot funciona en modo extractivo.

## Configuración de Gemini

ConversaKM intenta usar los modelos en este orden:

| Prioridad | Modelo |
|---|---|
| Principal | `gemini-4-neon` |
| Respaldo 1 | `gemini-4-hydrogen` |
| Respaldo 2 | `gemini-4-carbon` |

Cuando un modelo no responde por límite de solicitudes, indisponibilidad o error de servicio, se intenta el siguiente. Los nombres pueden cambiar según la disponibilidad de Gemini; puedes reemplazarlos en el archivo `.env` sin modificar el código.

1. Obtén una API key de Gemini.
2. Copia `backend/.env.example` a `backend/.env`.
3. Coloca tu clave en `GEMINI_API_KEY`.
4. Ajusta los tres identificadores de modelo si lo necesitas.

**No subas `backend/.env` ni compartas tu API key.** El `.gitignore` ya excluye los archivos `.env`.

## Instalación y ejecución

Abre dos terminales desde la carpeta raíz del proyecto.

### 1. Preparar el backend

En la primera terminal:

```bash
cd backend
python -m venv .venv
```

Activa el entorno virtual.

**Windows PowerShell**
```powershell
.venv\Scripts\Activate.ps1
```

**Linux o macOS**
```bash
source .venv/bin/activate
```

Instala las dependencias y genera los archivos de datos locales:

```bash
pip install -r requirements.txt
python generar_datos.py
```

Configura las variables de Gemini copiando el archivo de ejemplo:

**Windows PowerShell**
```powershell
Copy-Item .env.example .env
```

**Linux o macOS**
```bash
cp .env.example .env
```

Edita `backend/.env` y agrega `GEMINI_API_KEY`.

### 2. Crear el índice e iniciar la API

Desde `backend`, con el entorno virtual activado:

```bash
python rag.py
uvicorn main:app --reload --port 8000
```

La API estará en `http://localhost:8000`. La documentación interactiva de FastAPI está en `http://localhost:8000/docs`.

La primera ingesta descarga el modelo de embeddings y crea el índice local de Chroma en `backend/data/chroma/`. En los siguientes arranques se reutiliza el índice existente.

### 3. Iniciar el frontend

En la segunda terminal:

```bash
cd frontend
npm install
npm run dev
```

Abre `http://localhost:5173` en el navegador. Vite reenvía las solicitudes `/api` al backend en `http://localhost:8000`.

## Usuarios de demostración

`generar_datos.py` crea un usuario para cada área:

- `administracion`
- `logistica`
- `recursos_humanos`
- `ti`
- `soporte_interno`
- `finanzas`
- `ventas`
- `produccion`
- `atencion_cliente`
- `admin` (**administrador**: consulta los manuales de **todas** las áreas)

**Contraseña de las cuentas de área:** `innova123`

**Contraseña del administrador:** `admin123` por defecto. Puedes cambiarla con `ADMIN_PASSWORD` en `backend/.env` antes de ejecutar `generar_datos.py`.

Estas cuentas son solo para pruebas locales. No las uses en producción. Cambia `JWT_SECRET` por una clave larga y aleatoria y configura cuentas propias antes de desplegar.

## Pruebas y calibración

Desde la carpeta `backend`:

```bash
python calibrar.py
python pruebas.py
```

Los casos están en `casos.py`. `pruebas.py` imprime métricas y genera `resultados_pruebas.csv`, que se mantiene como archivo local.

## Solución de problemas

**"Documentos disponibles para ti: vacío" o el chatbot responde "sin evidencia" aunque los PDF existan.**
El catálogo `backend/data/documentos.json` es el que define qué manuales están vigentes y cuáles ve cada perfil. Antes, volver a ejecutar `python generar_datos.py` lo dejaba en `[]` mientras el índice Chroma seguía creado, y como el arranque solo ingestaba cuando no existía `chroma/`, nunca se reconstruía. Ahora:

- `generar_datos.py` ya no vacía `documentos.json` ni `registro.json` si existen.
- Al iniciar la API (`asegurar_indice`) se reingesta si el índice está vacío y se avisa si faltan manuales por indexar.
- `catalogo()` reconstruye el catálogo desde los PDF cuando está vacío o desactualizado, conservando el estado `vigente`/`obsoleto` de los manuales que ya estaban.

Si aun así no aparecen manuales, borra `backend/data/chroma/` y ejecuta `python rag.py`; revisa en la consola los avisos `AVISO: no se pudo leer ...` o `no tiene texto extraíble`.

## Agregar o actualizar manuales

Coloca manuales en formato PDF (con texto seleccionable) en una carpeta correspondiente al área:

```text
backend/data/manuales/<area>/<nombre_del_manual>.pdf
```

Áreas reconocidas: `administracion`, `logistica`, `recursos_humanos`, `ti`, `soporte_interno`, `finanzas`, `ventas`, `produccion` y `atencion_cliente`.

Después de agregar o modificar manuales, vuelve a ejecutar desde `backend`:

```bash
python rag.py
```

La ingesta reconstruye el índice local y actualiza el catálogo de documentos. Si un manual debe excluirse de las consultas, cambia su estado a `"obsoleto"` en `backend/data/documentos.json` y conserva el índice; el sistema filtrará los documentos obsoletos durante la recuperación.

## Flujo de consulta

1. El usuario inicia sesión y recibe un token JWT que incluye su área.
2. La pregunta se convierte en un embedding.
3. Chroma busca fragmentos de manuales filtrados por el área del usuario.
4. Se excluyen manuales obsoletos y se aplica el umbral de similitud.
5. Gemini genera una respuesta basada únicamente en los fragmentos recuperados.
6. Se validan las fuentes citadas y se devuelve la respuesta con referencias.
7. Si los manuales no tienen la información (similitud menor al umbral o Gemini indica que no alcanza), Gemini responde por su cuenta con información general, usando búsqueda web cuando el modelo lo permite. Esa respuesta se marca en pantalla como «no proviene de los manuales de InnovaCorp», no cita manuales y muestra las fuentes web cuando existen.
8. La consulta y la valoración se guardan en los JSON locales.

Si no se configura Gemini o los tres modelos no están disponibles, el sistema muestra fragmentos recuperados de los manuales en modo extractivo.

### Respuesta general de Gemini

Está activa por defecto (`RESPUESTA_GENERAL=true` en `backend/.env`). Para que el sistema solo responda con los manuales, por ejemplo en las pruebas de desconocimiento, usa `RESPUESTA_GENERAL=false`. La respuesta general no filtra contenido de otras áreas: Gemini recibe únicamente la pregunta del usuario, nunca fragmentos de manuales. La búsqueda web usa la herramienta de búsqueda de Google de la API de Gemini, que puede no estar disponible en todos los modelos o planes gratuitos; si no lo está, Gemini responde con su conocimiento general.

## Consideraciones de seguridad

Este proyecto está preparado para demostración y desarrollo local. Antes de un despliegue real, revisa la autenticación, reemplaza las credenciales de demostración, configura un `JWT_SECRET` seguro, restringe CORS al dominio de la aplicación y utiliza almacenamiento persistente y protegido para usuarios y registros.
