# Evaluación: agente texto → audio → WhatsApp (infra gratis)

**Veredicto: fácil.** ~50 líneas de código, 1 tarde, $0 de infra.
El 90% del riesgo no es técnico: es que WhatsApp banea números que usan librerías no oficiales.

## Arquitectura mínima

```
texto → TTS (edge-tts) → .mp3 → ffmpeg → .ogg/opus → Baileys → tu número
```

Tres piezas, ninguna paga, ninguna necesita servidor.

## 1. TTS gratis — ranking

| Opción | Costo | Calidad | Offline | Notas |
|---|---|---|---|---|
| **edge-tts** (recomendado) | gratis, sin API key | muy alta (voces neurales MS) | no | `pip install edge-tts`. Endpoint no oficial de Edge Read Aloud. Voces es-AR: `es-AR-TomasNeural`, `es-AR-ElenaNeural`. Puede romperse si MS cambia el endpoint. |
| **Piper** | gratis (MIT) | alta | **sí** | Binario + modelo ONNX (~60MB). Rápido en CPU. La opción "no depende de nadie". |
| **Kokoro-82M** | gratis (Apache) | muy alta | sí | Modelo chico moderno, mejor calidad que Piper, más pesado de instalar. Español aceptable. |
| `say` (macOS) | gratis, ya instalado | media | sí | Cero dependencias si el agente corre en tu Mac. Voz Mónica/Diego. |
| gTTS | gratis, sin key | media | no | Endpoint no oficial de Google Translate. Robótico, corta textos largos. |
| Coqui TTS | gratis | alta | sí | Pesado (PyTorch), proyecto archivado. Evitar. |
| ElevenLabs free | 10k chars/mes | altísima | no | Tier gratis se agota rápido, requiere key. |

**Elección lazy:** edge-tts. Una línea, sin key, calidad de producto pago.
**Plan B si edge-tts se cae:** Piper local, mismo contrato (texto in, wav out).

## 2. Envío a WhatsApp — open-wa vs alternativas

Preguntaste por [open-wa](https://www.open-wa.org/). Comparación:

| Librería | Costo real | Cómo funciona | Fricción |
|---|---|---|---|
| **Baileys** (recomendado) | 100% gratis, MIT | WebSocket directo al protocolo WA | Sin browser, sin RAM extra. Node. |
| whatsapp-web.js | gratis | Puppeteer + Chrome headless | ~400MB RAM, se rompe con updates de WA Web |
| open-wa / wa-automate | **freemium** | Puppeteer | El core es gratis, pero varias features y el "insiders" build piden license key paga. Para audio/PTT confiable te empuja al tier pago. |
| WhatsApp Cloud API (oficial) | gratis hasta cierto volumen | API oficial Meta | Necesita Business Manager, número dedicado, y **no podés mandarte a vos mismo sin que el usuario inicie la conversación** (ventana de 24h). Para este caso de uso es más burocracia que beneficio. |

**Elección:** Baileys. Gratis de verdad, sin Chrome, y `sendMessage` con `ptt: true` manda nota de voz nativa.

## 3. Requisito no obvio: el formato de audio

WhatsApp solo reconoce nota de voz si el archivo es **OGG/Opus mono**. Si mandás mp3 llega como adjunto genérico, no como audio reproducible in-line.

```bash
ffmpeg -i in.mp3 -c:a libopus -ac 1 -b:a 32k -application voip out.ogg
```

Esto es lo que hace fallar el 80% de los intentos de la gente. Anotado.

## 4. Código completo (esto es todo)

```bash
npm i @whiskeysockets/baileys qrcode-terminal
pip install edge-tts
brew install ffmpeg
```

```js
// tts-wa.js
const { default: makeWASocket, useMultiFileAuthState } = require('@whiskeysockets/baileys')
const qrcode = require('qrcode-terminal')
const { execFileSync } = require('child_process')

const MI_NUMERO = '5491112345678@s.whatsapp.net' // sin +, sin espacios

async function decir(texto) {
  execFileSync('edge-tts', ['--voice', 'es-AR-TomasNeural', '--text', texto, '--write-media', '/tmp/o.mp3'])
  execFileSync('ffmpeg', ['-y', '-i', '/tmp/o.mp3', '-c:a', 'libopus', '-ac', '1', '-b:a', '32k', '/tmp/o.ogg'])

  const { state, saveCreds } = await useMultiFileAuthState('./wa-auth')
  const sock = makeWASocket({ auth: state })
  sock.ev.on('creds.update', saveCreds)
  sock.ev.on('connection.update', async ({ connection, qr }) => {
    if (qr) qrcode.generate(qr, { small: true })
    if (connection === 'open') {
      await sock.sendMessage(MI_NUMERO, {
        audio: { url: '/tmp/o.ogg' }, mimetype: 'audio/ogg; codecs=opus', ptt: true,
      })
      process.exit(0)
    }
  })
}

decir(process.argv[2] || 'hola, esto es una prueba')
```

Primera corrida: escaneás un QR con tu WhatsApp (igual que WhatsApp Web). La sesión queda en `./wa-auth/` y no volvés a escanear.

## 5. Dónde corre (gratis)

- **Tu máquina / cron**: cero infra, cero costo. Lo obvio para uso personal.
- **Railway / Fly free tier**: si querés que corra 24/7. Ojo: la carpeta `wa-auth` necesita volumen persistente o re-escaneás QR en cada deploy.
- **GitHub Actions**: solo si es disparado por evento y guardás la sesión en secrets/artifact. Frágil, no lo haría.

## 6. Riesgos reales

| Riesgo | Severidad | Mitigación |
|---|---|---|
| **Ban del número** | alta | Baileys/open-wa son no oficiales y violan los ToS. Mandarte mensajes a vos mismo a bajo volumen casi nunca dispara ban, pero usá un número secundario si te importa. |
| Sesión expira | media | Se re-escanea el QR. Persistir `wa-auth`. |
| edge-tts deja de andar | baja | Swap a Piper, misma interfaz. |
| Rate limit / spam | baja | No mandes ráfagas. 1 mensaje cada varios segundos. |

## 7. Estimación

| Tarea | Tiempo |
|---|---|
| TTS andando | 15 min |
| Baileys + QR + primer mensaje | 30 min |
| Formato opus correcto | 15 min (si no lees esto, 2h) |
| Envolverlo en "agente" (input, prompt, trigger) | depende del trigger |
| **Total core** | **~1-1.5 h** |

## Recomendación

Empezá con el script de arriba tal cual, contra tu número, en tu máquina. Si funciona en 1 hora, recién ahí decidís si merece ser un "agente" con triggers, cola, o deploy. La parte agente es la cara; la parte texto→audio→WhatsApp es la barata.

---

# Anexo: la misma cosa pero a Discord

**Complejidad: trivial.** El envío pasa de "librería no oficial + QR + riesgo de ban" a **una llamada HTTP**.

## Por qué Discord gana

| | WhatsApp (Baileys) | Discord (webhook) |
|---|---|---|
| API oficial | ❌ no, viola ToS | ✅ sí |
| Riesgo de ban | real | ninguno |
| Auth | QR + sesión persistida en disco | una URL secreta |
| Dependencias | Baileys + libs | `curl` |
| Se rompe solo | sí (updates de WA) | no |
| Reproduce audio inline | sí (ptt) | sí (player de attachment) |
| Notificación al celu | sí | sí (app de Discord) |

Lo único que perdés: no llega a *WhatsApp*. Si el requisito real era "que me avise en el celular", Discord lo cumple igual.

## Setup (2 minutos, cero código)

1. Servidor propio de Discord (creás uno gratis, solo vos).
2. Canal → ⚙️ Editar canal → Integraciones → **Webhooks** → Nuevo webhook → **Copiar URL**.
3. Listo. Esa URL *es* la credencial — tratala como secreto, quien la tenga postea en tu canal.

## Envío: una línea

```bash
curl -F "file=@/tmp/o.mp3" "$DISCORD_WEBHOOK_URL"
```

Discord renderiza un player inline para mp3/ogg/wav. **No hace falta convertir a opus** — ese paso de ffmpeg desaparece.

## Script completo

```bash
pip install edge-tts
```

```bash
#!/bin/bash
# tts-discord.sh "texto a decir"
set -euo pipefail
: "${DISCORD_WEBHOOK_URL:?falta DISCORD_WEBHOOK_URL}"

edge-tts --voice es-AR-TomasNeural --text "$1" --write-media /tmp/tts.mp3
curl -sf -F "file=@/tmp/tts.mp3" -F 'payload_json={"content":""}' "$DISCORD_WEBHOOK_URL" >/dev/null
```

Eso es el agente entero. Sin Node, sin npm, sin ffmpeg, sin auth persistida.

## Estimación revisada

| Tarea | WhatsApp | Discord |
|---|---|---|
| TTS | 15 min | 15 min |
| Transporte | 45 min + riesgo | **2 min** |
| Formato de audio | 15 min | 0 |
| Mantenimiento | recurrente | ninguno |
| **Total** | ~1.5 h | **~20 min** |

## Cuándo NO alcanza el webhook

Un webhook solo **postea**. Si querés que el agente **reciba** texto desde Discord (vos escribís, te contesta en audio), necesitás un bot real: `discord.py` o `discord.js`, token de bot, y un proceso corriendo con conexión al gateway. Sigue siendo gratis y oficial, pero ya es un proceso 24/7 en vez de un script.

Regla: **disparo desde otro lado → webhook. Conversación dentro de Discord → bot.**

## Recomendación

Si el objetivo es "probar rápido que la idea sirve", hacelo en Discord con las 4 líneas de arriba. Si después resulta que *tiene* que ser WhatsApp, el bloque de TTS se reusa igual y solo cambiás el transporte.
