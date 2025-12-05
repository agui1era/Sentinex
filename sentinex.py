# sentinex.py — Multi-camera cognitive surveillance
# Author: Oscar Aguilera

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

def load_cameras_from_env():
    """Load all cameras defined as RTSP_URL_<NAME> in .env file."""
    cameras = {}
    for key, value in os.environ.items():
        if not key.startswith("RTSP_URL_"):
            continue
        if not value:
            continue
        name = key.replace("RTSP_URL_", "")
        cameras[name] = value
    return cameras


CAMERAS = load_cameras_from_env()

FRAME_WIDTH = int(os.getenv("FRAME_WIDTH", "1280"))
FRAME_HEIGHT = int(os.getenv("FRAME_HEIGHT", "720"))
FRAME_MAX_WIDTH = int(os.getenv("FRAME_MAX_WIDTH", "960"))
INTERVAL = float(os.getenv("INTERVAL", "60"))
_last_dir = os.getenv("LAST_FRAME_DIR", "last_frames")
LAST_FRAME_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), _last_dir) if not os.path.isabs(_last_dir) else _last_dir

# LLM API configuration (supports ngrok or local IP)
LM_API = os.getenv("LM_STUDIO_API", "").rstrip("/")
LM_PATH = os.getenv("LM_STUDIO_PATH", "/chat/completions")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen3-vl-8b")

API_KEY = os.getenv("API_KEY")  

SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD", "0.8"))
HUMAN_ALERT_DEFAULT = float(os.getenv("HUMAN_ALERT_COOLDOWN", "300"))
HUMAN_ALERT_MIN_SCORE = float(os.getenv("HUMAN_ALERT_MIN_SCORE", "0.2"))
HUMAN_ALERT_COOLDOWNS = {
    name: float(os.getenv(f"HUMAN_ALERT_COOLDOWN_{name}", HUMAN_ALERT_DEFAULT))
    for name in CAMERAS.keys()
}

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
        raise RuntimeError("Failed to encode frame to JPEG")
    return base64.b64encode(buf).decode("utf-8")


def risk_emoji(score: float) -> str:
    if score >= 0.8:
        return "🚨"
    if score >= 0.4:
        return "⚠️"
    return "ℹ️"


def human_detected(text: str, payload: dict) -> bool:
    human_flag = payload.get("human") if isinstance(payload, dict) else None
    if human_flag is None and isinstance(payload, dict):
        human_flag = payload.get("human_detected")
    if isinstance(human_flag, bool):
        return human_flag

    text_lower = (text or "").lower()
    keywords = ["human", "humano", "persona", "person", "people", "hombre", "mujer"]
    return any(k in text_lower for k in keywords)


def save_last_frame(camera_name: str, frame):
    """Save the last analyzed frame for each camera."""
    try:
        os.makedirs(LAST_FRAME_DIR, exist_ok=True)
        safe_name = "".join(c if c.isalnum() else "_" for c in camera_name)
        path = os.path.join(LAST_FRAME_DIR, f"{safe_name}_last.jpg")
        ok = cv2.imwrite(path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ok:
            log(f"⚠️ Failed to save frame from {camera_name}")
        else:
            log(f"💾 Frame saved: {path}")
    except Exception as e:
        log(f"⚠️ Error saving frame from {camera_name}: {e}")


# ============================================================
# LLM ANALYSIS (API KEY)
# ============================================================

def analyze_llm(camera_name, frame) -> dict:
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
        return {"score": 0.0, "text": "Analysis error", "b64": img_b64}


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(img_b64: str, caption: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption[:1024]}
        files = {"photo": ("frame.jpg", base64.b64decode(img_b64), "image/jpeg")}
        r = requests.post(url, data=data, files=files, timeout=20)
        log(f"📨 Telegram status: {r.status_code}")
    except Exception as e:
        log(f"❌ Error Telegram: {e}")


# ============================================================
# OMNISTATUS
# ============================================================

def inject_omnistatus(source: str, text: str, score: float):
    if not ENABLE_OMNISTATUS or not OMNISTATUS_API:
        return
    try:
        payload = {"source": source, "text": text, "score": score}
        requests.post(OMNISTATUS_API, json=payload, timeout=10)
    except Exception as e:
        log(f"❌ OmniStatus injection error: {e}")


# ============================================================
# CAMERA LOOP
# ============================================================

def process_camera(name, url):
    retries = 0
    cap = cv2.VideoCapture(url)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    if not cap.isOpened():
        log(f"❌ Failed to open {name}")
        return

    log(f"🎥 Camera {name} started")
    last_human_alert_at = 0.0
    cooldown = HUMAN_ALERT_COOLDOWNS.get(name, HUMAN_ALERT_DEFAULT)

    while True:
        ok, frame = cap.read()
        if not ok:
            log(f"⚠️ Invalid frame on {name}, retrying...")
            time.sleep(3)
            cap.release()
            cap = cv2.VideoCapture(url)
            retries += 1
            if retries > 5:
                log(f"❌ {name} exhausted retries. Pausing 60s")
                time.sleep(60)
                retries = 0
            continue

        retries = 0
        frame = resize_if_needed(frame)

        res = analyze_llm(name, frame)
        save_last_frame(name, frame)

        score = res["score"]
        text = res["text"]
        human = human_detected(text, res)

        log(f"[{name}] score={score:.2f} | {text}")

        risk_sent = False
        if score >= SCORE_THRESHOLD:
            emoji = risk_emoji(score)
            send_telegram(res["b64"], f"{emoji} {name}: {text} | Risk={score:.2f}")
            risk_sent = True

        if human and not risk_sent:
            now = time.time()
            elapsed = now - last_human_alert_at
            if score < HUMAN_ALERT_MIN_SCORE:
                log(f"[{name}] Person detected, but score={score:.2f} < min {HUMAN_ALERT_MIN_SCORE:.2f}; alert not sent")
            elif elapsed >= cooldown:
                send_telegram(res["b64"], f"🧍 {name}: Person detected | Risk={score:.2f} | {text}")
                last_human_alert_at = now
            else:
                remaining = int(cooldown - elapsed)
                log(f"[{name}] Person detected but in cooldown ({remaining}s remaining)")

        inject_omnistatus(name, text, score)

        time.sleep(INTERVAL)


# ============================================================
# MAIN
# ============================================================

def main():
    from threading import Thread

    for name, url in CAMERAS.items():
        if not url:
            continue
        Thread(target=process_camera, args=(name, url), daemon=True).start()

    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
