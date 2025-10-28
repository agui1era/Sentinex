# 📡 Sentinex RTSP (Cognitive Surveillance System)

**Multimodal frame analysis system using Qwen3-VL and RTSP cameras.**  
Detects visual risks and sends real-time alerts via Telegram.  
Built for real-world surveillance scenarios — resilient, lightweight and local-first.

---

## 🧠 Features

- 🧲 Pulls frames from any IP camera / RTSP stream (DVR/NVR compatible).
- 🔍 Sends frames to **local LLM** (e.g. Qwen3-VL via LM Studio).
- 🧠 Performs visual reasoning with a configurable system prompt.
- 🧮 Extracts structured risk score (0.0 to 1.0).
- 🚨 Sends alerts to Telegram on critical events.
- 🔄 Auto-reconnects if RTSP stream fails (resilient loop).
- 🪶 Fully stateless, fast and resource-light (runs on consumer hardware).

---

## ⚙️ Quick Setup

1. Install **LM Studio** or run your local LLM API (port 1234).
2. Clone this repo and create a `.env` file as shown below.
3. Run:

```bashx
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python sentinex.py
```

---

## 🔐 `.env` Example

```env
# 📡 RTSP Camera
RTSP_URL=rtsp://user:password@camera_ip:554/path

# 🎞️ Frame capture
FRAME_WIDTH=1280
FRAME_HEIGHT=720
FRAME_SCALE=1.0
FRAME_MAX_WIDTH=960
INTERVAL=60

# 🧠 LLM Settings
LM_STUDIO_API=http://localhost:1234/v1/chat/completions
MODEL_NAME=qwen3-vl-8b
SYSTEM_PROMPT=You are a cognitive sentinel. You observe camera images to detect human presence, anomalies, or risks. Always respond in valid JSON: {"description":"...", "evaluation":"...", "risk":0.0}

# ⚠️ Risk scoring
RISK_THRESHOLD=0.8

# 📲 Telegram
ENABLE_TELEGRAM=1
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

---

> 🛠 Developed by Oscar Aguilera — [Oscar Aguilera](https://www.linkedin.com/in/oaguileraz/) - Ingeniería + Visión Artificial + Modelos Cognitivos Locales.  


---

# 📷 Sentinex RTSP (Sistema de Monitoreo Cognitivo)

**Sistema de análisis por imágenes en tiempo real usando Qwen3-VL y cámaras RTSP.**  
Detecta riesgos visuales y envía alertas por Telegram en escenarios reales.

---

## 🧠 Características

- 🔌 Conecta con cualquier cámara IP o stream RTSP.
- 🤖 Usa un modelo LLM local (Qwen3-VL con LM Studio).
- 🧠 Analiza cada imagen y evalúa el riesgo.
- 📈 Devuelve un puntaje estructurado de 0.0 a 1.0.
- 🚨 Envía alertas si el riesgo es alto.
- 🛠️ Se reconecta solo si la cámara falla.
- 🌀 No necesita mantener contexto — es liviano y veloz.

---

## ⚙️ Instalación Rápida

1. Instala **LM Studio** o tu API local (puerto 1234).
2. Clona el repositorio y crea un `.env` como el de abajo.
3. Ejecuta:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python sentinex.py
```

---

## 🔐 Ejemplo de `.env`

```env
# 📡 Cámara RTSP
RTSP_URL=rtsp://usuario:clave@ip_camara:554/ruta

# 🎞️ Captura de imágenes
FRAME_WIDTH=1280
FRAME_HEIGHT=720
FRAME_SCALE=1.0
FRAME_MAX_WIDTH=960
INTERVAL=60

# 🧠 LLM (Qwen3 local)
LM_STUDIO_API=http://localhost:1234/v1/chat/completions
MODEL_NAME=qwen3-vl-8b
SYSTEM_PROMPT=Eres un centinela cognitivo. Observas imágenes de cámaras y detectas presencia humana, anomalías o riesgos. Devuelve siempre en JSON: {"descripcion":"...", "evaluacion":"...", "riesgo":0.0}

# ⚠️ Evaluación de riesgo
RISK_THRESHOLD=0.8

# 📲 Alerta Telegram
ENABLE_TELEGRAM=1
TELEGRAM_BOT_TOKEN=tu_token
TELEGRAM_CHAT_ID=tu_chat_id
```

---

> 🛠 Desarrollado por Oscar Aguilera — [Oscar Aguilera](https://www.linkedin.com/in/oaguileraz/) - Ingeniería + Visión Artificial + Modelos Cognitivos Locales.  
