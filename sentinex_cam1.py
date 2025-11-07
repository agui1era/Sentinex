import os
import cv2
import time
import base64
import requests
import re
import pyttsx3
from dotenv import load_dotenv

load_dotenv()

RTSP_URL = os.getenv("RTSP_URL_CAM1")
FRAME_WIDTH = int(os.getenv("FRAME_WIDTH", "1280"))
FRAME_HEIGHT = int(os.getenv("FRAME_HEIGHT", "720"))
FRAME_SCALE = float(os.getenv("FRAME_SCALE", "1.0"))
FRAME_MAX_WIDTH = int(os.getenv("FRAME_MAX_WIDTH", "960"))
INTERVAL = float(os.getenv("INTERVAL", "60"))

LM_STUDIO_API = os.getenv("LM_STUDIO_API")
MODEL_NAME = os.getenv("MODEL_NAME")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "")
RISK_THRESHOLD = float(os.getenv("RISK_THRESHOLD", "0.8"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TTS_ALERT_PHRASE = os.getenv("TTS_ALERT_PHRASE", "Alexa, enciende la casa.")

RISK_REGEX = re.compile(r"\"riesgo\"\\s*:\\s*(0(?:\\.\\d+)?|1(?:\\.0+)?)", re.IGNORECASE)

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def resize_if_needed(frame, max_width: int):
    if max_width and frame.shape[1] > max_width:
        scale = max_width / frame.shape[1]
        new_size = (int(frame.shape[1] * scale), int(frame.shape[0] * scale))
        frame = cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)
    return frame

def a_b64_jpg(frame):
    ok, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise RuntimeError("Fallo al codificar JPEG")
    im_b64 = base64.b64encode(buf).decode("utf-8")
    return im_b64, f"data:image/jpeg;base64,{im_b64}"

def analizar_imagen(frame):
    im_b64, data_uri = a_b64_jpg(frame)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": data_uri}}]},
    ]
    payload = {"model": MODEL_NAME, "messages": messages, "temperature": 0.1, "max_tokens": 700}
    try:
        resp = requests.post(LM_STUDIO_API, json=payload, timeout=60)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            return content, im_b64
        else:
            log(f"[LLM] Error HTTP {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        log(f"[LLM] Error conexión: {e}")
    return None, im_b64

def extraer_riesgo(texto: str):
    if not texto:
        return None
    m = RISK_REGEX.search(texto)
    if m:
        try:
            val = float(m.group(1))
            return val if 0.0 <= val <= 1.0 else None
        except ValueError:
            pass
    return None

def enviar_telegram(im_b64: str, desc: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    data = {"chat_id": TELEGRAM_CHAT_ID, "caption": desc[:1024]}
    files = {"photo": base64.b64decode(im_b64)}
    try:
        resp = requests.post(url, data=data, files=files, timeout=20)
        log(f"📨 Telegram: {resp.status_code} {resp.text[:100]}")
    except Exception as e:
        log(f"❌ Telegram error: {e}")

def speak_alert():
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)
    engine.setProperty('volume', 1.0)
    for _ in range(3):
        engine.say(TTS_ALERT_PHRASE)
        engine.runAndWait()
        time.sleep(3)
    engine.stop()

def iniciar_stream(backoff_start=5, backoff_max=60):
    retries = 0
    while True:
        cap = cv2.VideoCapture(RTSP_URL)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

        if not cap.isOpened():
            wait = min(backoff_start * (2 ** retries), backoff_max)
            log(f"❌ No se pudo abrir RTSP. Reintentando en {wait}s...")
            time.sleep(wait)
            retries += 1
            continue

        log("✅ Conectado a RTSP.")
        return cap

def main():
    cap = iniciar_stream()

    while True:
        ok, frame = cap.read()
        if not ok:
            log("⚠️ Fallo al capturar frame. Reintentando conexión...")
            cap.release()
            cap = iniciar_stream()
            continue

        frame = resize_if_needed(frame, FRAME_MAX_WIDTH)
        texto, im_b64 = analizar_imagen(frame)
        riesgo = extraer_riesgo(texto)

        log("──────── LLM OUTPUT ────────")
        print(texto or "[Vacío]")
        log(f"RIESGO: {riesgo}")

        if 1:
            speak_alert()
            enviar_telegram(im_b64, texto)

        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()