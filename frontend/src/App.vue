<script setup>
import { ref, nextTick } from 'vue'

const sesion = ref(JSON.parse(sessionStorage.getItem('sesion') || 'null'))
const usuario = ref(''), password = ref(''), error = ref('')
const msgs = ref([]), texto = ref(''), cargando = ref(false), caja = ref(null)
const sugerencias = ['¿Cuál es el procedimiento para solicitar un equipo de cómputo nuevo?', '¿Qué documentos puedo consultar?']

async function api(ruta, cuerpo) {
  const r = await fetch('/api' + ruta, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(sesion.value ? { Authorization: 'Bearer ' + sesion.value.token } : {}) },
    body: JSON.stringify(cuerpo)
  })
  if (r.status === 401 && sesion.value) salir()
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || 'Error del servidor')
  return r.json()
}
async function login() {
  error.value = ''
  try {
    sesion.value = await api('/login', { usuario: usuario.value, password: password.value })
    sessionStorage.setItem('sesion', JSON.stringify(sesion.value)); msgs.value = []
  } catch (e) { error.value = e.message }
}
function salir() { sesion.value = null; sessionStorage.removeItem('sesion'); msgs.value = [] }
async function bajar() { await nextTick(); caja.value && (caja.value.scrollTop = caja.value.scrollHeight) }
async function enviar(p) {
  const q = (p || texto.value).trim()
  if (!q || cargando.value) return
  texto.value = ''; msgs.value.push({ rol: 'yo', texto: q }); cargando.value = true; bajar()
  try {
    if (q === '¿Qué documentos puedo consultar?') {
      const r = await fetch('/api/documentos', { headers: { Authorization: 'Bearer ' + sesion.value.token } })
      const d = await r.json()
      msgs.value.push({ rol: 'bot', texto: 'Documentos de tu área:\n' + d.map(x => `• ${x.titulo} (v${x.version}, ${x.estado})`).join('\n') })
    } else {
      const r = await api('/chat', { pregunta: q })
      msgs.value.push({ rol: 'bot', texto: r.respuesta, fuentes: r.fuentes, id: r.id, sin: !r.suficiente, modo: r.modo })
    }
  } catch (e) { msgs.value.push({ rol: 'bot', texto: 'Error: ' + e.message, sin: true }) }
  cargando.value = false; bajar()
}
async function valorar(m, util) { await api('/feedback', { id: m.id, util }); m.valorada = util }
</script>

<template>
  <div v-if="!sesion" class="login">
    <form @submit.prevent="login">
      <h1>ConversaKM</h1>
      <p>Asistente de conocimiento · InnovaCorp</p>
      <input v-model="usuario" placeholder="Usuario (ej. soporte_interno)" autofocus />
      <input v-model="password" type="password" placeholder="Contraseña" />
      <button>Entrar</button>
      <small v-if="error" class="err">{{ error }}</small>
    </form>
  </div>

  <div v-else class="app">
    <header>
      <b>ConversaKM</b><span class="tag">{{ sesion.area_nombre }}</span>
      <span class="who">{{ sesion.nombre }}</span><button class="ghost" @click="salir">Salir</button>
    </header>
    <main ref="caja">
      <div v-if="!msgs.length" class="vacio">
        <p>Pregunta sobre los manuales de <b>{{ sesion.area_nombre }}</b>.</p>
        <button v-for="s in sugerencias" :key="s" class="chip" @click="enviar(s)">{{ s }}</button>
      </div>
      <div v-for="(m, i) in msgs" :key="i" :class="['m', m.rol, { sin: m.sin }]">
        <p>{{ m.texto }}</p>
        <div v-if="m.fuentes && m.fuentes.length" class="src">
          Fuente:
          <span v-for="f in m.fuentes" :key="f.documento">📄 {{ f.documento }} (fragmentos {{ f.fragmentos.join(', ') }})</span>
        </div>
        <div v-if="m.modo && m.modo.startsWith('extractivo')" class="src">Modo sin LLM: se muestran fragmentos del manual.</div>
        <div v-if="m.id" class="fb">
          <button :class="{ on: m.valorada === true }" @click="valorar(m, true)">👍 Útil</button>
          <button :class="{ on: m.valorada === false }" @click="valorar(m, false)">👎 No útil</button>
        </div>
      </div>
      <div v-if="cargando" class="m bot"><p>Consultando los manuales…</p></div>
    </main>
    <form class="entrada" @submit.prevent="enviar()">
      <input v-model="texto" placeholder="Escribe tu pregunta…" />
      <button :disabled="cargando">Enviar</button>
    </form>
  </div>
</template>

<style>
* { box-sizing: border-box } body { margin: 0; font-family: system-ui, sans-serif; background: #f4f6fb; color: #1b2440 }
button { cursor: pointer; border: 0; border-radius: 8px; padding: 10px 16px; background: #4f63e6; color: #fff; font-size: 14px }
button:disabled { opacity: .5 } input { padding: 12px; border: 1px solid #ccd3e6; border-radius: 8px; font-size: 15px }
.login { min-height: 100vh; display: grid; place-items: center }
.login form { background: #fff; padding: 32px; border-radius: 14px; width: 340px; display: grid; gap: 12px; box-shadow: 0 6px 24px #1b24401a }
.login h1 { margin: 0; color: #4f63e6 } .login p { margin: 0 0 8px; color: #667 } .err { color: #c0392b }
.app { max-width: 820px; margin: 0 auto; height: 100vh; display: flex; flex-direction: column }
header { display: flex; align-items: center; gap: 12px; padding: 14px 16px; background: #1b2440; color: #fff }
.tag { background: #4f63e6; border-radius: 99px; padding: 3px 12px; font-size: 13px } .who { margin-left: auto; font-size: 13px; opacity: .8 }
.ghost { background: #ffffff22 } main { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px }
.vacio { text-align: center; margin-top: 8vh } .chip { display: block; margin: 8px auto; background: #e6eaff; color: #3a4bc4 }
.m { max-width: 80%; padding: 10px 14px; border-radius: 14px; background: #fff; box-shadow: 0 1px 4px #1b244014 }
.m p { margin: 0; white-space: pre-wrap; line-height: 1.5 } .m.yo { align-self: flex-end; background: #4f63e6; color: #fff }
.m.sin { background: #fff4e0; border-left: 4px solid #e69a1b } .src { margin-top: 8px; font-size: 12px; color: #3a4bc4; display: flex; gap: 8px; flex-wrap: wrap }
.fb { margin-top: 6px; display: flex; gap: 6px } .fb button { background: #eef0f8; color: #333; padding: 4px 10px; font-size: 12px } .fb .on { background: #bfe8c9 }
.entrada { display: flex; gap: 8px; padding: 12px 16px; background: #fff } .entrada input { flex: 1 }
</style>
