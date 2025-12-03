# sentinex_multicamera.py — Versión API KEY (sin HMAC)
# Autor: Zorro12 + ZorroIA

import os
import cv2
import time
import base64
import requests
import json
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIG
# ============================================================

CAMERAS = {
    "CAM1": os.getenv("RTSP_URL_CAM1"),
    "CAM6": os.getenv("RTSP_URL_CAM6"),
    "CAM8": os.getenv("RTSP_URL_CAM8"),
}

FRAME_WIDTH = int(os.getenv("FRAME_WIDTH", "1280"))
FRAME_HEIGHT = int(os.getenv("FRAME_HEIGHT", "720"))
FRAME_MAX_WIDTH = int(os.getenv("FRAME_MAX_WIDTH", "960"))
INTERVAL = float(os.getenv("INTERVAL", "60"))

# Aquí va el PROXY (ngrok o IP)
LM_API = os.getenv("LM_STUDIO_API").rstrip("/")
LM_PATH = os.getenv("LM_STUDIO_PATH", "/chat/completions")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen3-vl-8b")

API_KEY = os.getenv("API_KEY")  

SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD", "0.8"))

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# OmniStatus
ENABLE_OMNISTATUS = os.getenv("ENABLE_OMNISTATUS", "0") == "1"
OMNISTATUS_API = os.getenv("OMNISTATUS_ENDPOINT")


# ============================================================
# UTILS
# ============================================================

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def resize_if_needed(frame):
    if FRAME_MAX_WIDTH and frame.shape[1] > FRAME_MAX_WIDTH:
        scale = FRAME_MAX_WIDTH / frame.shape[1]
        new_size = (int(frame.shape[1] * scale), int(frame.shape[0] * scale))
        frame = cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)
    return frame


def to_b64_jpg(frame):
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise RuntimeError("No se pudo convertir frame a JPEG")
    return base64.b64encode(buf).decode("utf-8")


# ============================================================
# ANALISIS LLM (API KEY)
# ============================================================

def analizar_llm(camera_name, frame) -> dict:
    img_b64 = to_b64_jpg(frame)
    img_data_uri = f"data:image/jpeg;base64,{img_b64}"

    system_prompt = os.getenv(f"SYSTEM_PROMPT_{camera_name}", "")

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": img_data_uri}}
            ]},
        ],
        "temperature": 0.1,
        "max_tokens": 700,
    }

    url = LM_API + LM_PATH

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        r.raise_for_status()

        raw = r.json()["choices"][0]["message"]["content"]
        parsed = json.loads(raw)

        return {
            "score": float(parsed.get("score", 0.0)),
            "text": parsed.get("description", ""),
            "b64": img_b64
        }

    except Exception as e:
        log(f"❌ LLM error ({camera_name}): {e}")
        return {"score": 0.0, "text": "Error en análisis", "b64": img_b64}


# ============================================================
# TELEGRAM
# ============================================================

def enviar_telegram(img_b64: str, caption: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption[:1024]}
        files = {"photo": base64.b64decode(img_b64)}
        r = requests.post(url, data=data, files=files, timeout=20)
        log(f"📨 Telegram status: {r.status_code}")
    except Exception as e:
        log(f"❌ Error Telegram: {e}")


# ============================================================
# OMNISTATUS
# ============================================================

def inyectar_omnistatus(source: str, text: str, score: float):
    if not ENABLE_OMNISTATUS or not OMNISTATUS_API:
        return
    try:
        payload = {"source": source, "text": text, "score": score}
        requests.post(OMNISTATUS_API, json=payload, timeout=10)
    except Exception as e:
        log(f"❌ Error inyección OmniStatus: {e}")


# ============================================================
# CAMARA LOOP
# ============================================================

def procesar_camara(nombre, url):
    retries = 0
    cap = cv2.VideoCapture(url)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    if not cap.isOpened():
        log(f"❌ No se pudo abrir {nombre}")
        return

    log(f"🎥 Cámara {nombre} iniciada")

    while True:
        ok, frame = cap.read()
        if not ok:
            log(f"⚠️ Frame inválido en {nombre}, reintentando...")
            time.sleep(3)
            cap.release()
            cap = cv2.VideoCapture(url)
            retries += 1
            if retries > 5:
                log(f"❌ {nombre} agotó reintentos. Pausa 60s")
                time.sleep(60)
                retries = 0
            continue

        retries = 0
        frame = resize_if_needed(frame)

        res = analizar_llm(nombre, frame)

        score = res["score"]
        text = res["text"]

        log(f"[{nombre}] score={score:.2f} | {text}")

        if score >= SCORE_THRESHOLD:
            enviar_telegram(res["b64"], f"🚨 {nombre}: {text}")

        inyectar_omnistatus(nombre, text, score)

        time.sleep(INTERVAL)


# ============================================================
# MAIN
# ============================================================

def main():
    from threading import Thread

    for nombre, url in CAMERAS.items():
        if not url:
            continue
        Thread(target=procesar_camara, args=(nombre, url), daemon=True).start()

    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()