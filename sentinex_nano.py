import cv2
import base64
import requests
import os
import time
import json
import logging
from dotenv import load_dotenv

# --- Configuración ---

def setup_logging():
    """Configura el logging básico para mostrar información en la consola."""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_configuration():
    """Carga la configuración desde el archivo .env.nano y la valida."""
    load_dotenv(dotenv_path=".env.nano")
    config = {
        "rtsp_url": os.getenv("RTSP_URL"),
        "frame_scale": float(os.getenv("FRAME_SCALE", 1.0)),
        "frame_max_width": int(os.getenv("FRAME_MAX_WIDTH", 960)),
        "interval": int(os.getenv("INTERVAL", 60)),
        "lm_studio_api": os.getenv("LM_STUDIO_API"),
        "model_name": os.getenv("MODEL_NAME"),
        "system_prompt": os.getenv("SYSTEM_PROMPT"),
        "risk_threshold": float(os.getenv("RISK_THRESHOLD", 0.8)),
        "enable_telegram": os.getenv("ENABLE_TELEGRAM") == "1",
        "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
        "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID"),
    }
    
    if not config["rtsp_url"]:
        logging.error("La variable RTSP_URL no está definida en el archivo .env.nano.")
        exit(1)
    if not config["lm_studio_api"]:
        logging.error("La variable LM_STUDIO_API no está definida en el archivo .env.nano.")
        exit(1)
    return config

# --- Procesamiento de Imagen ---

def encode_image_to_base64(frame):
    """Codifica un frame de cv2 a un string base64."""
    _, buffer = cv2.imencode('.jpg', frame)
    return base64.b64encode(buffer).decode('utf-8')

def resize_frame(frame, scale, max_width):
    """Redimensiona un frame manteniendo la proporción de aspecto."""
    height, width, _ = frame.shape
    
    new_width = int(width * scale)
    new_height = int(height * scale)
    
    if new_width > max_width:
        aspect_ratio = height / width
        new_width = max_width
        new_height = int(new_width * aspect_ratio)
        
    return cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)

# --- Conexión RTSP para Cámaras Chinas ---

def create_rtsp_capture_chinese_cam(rtsp_url):
    """
    Crea una captura RTSP optimizada para cámaras chinas (Hikvision, Dahua, etc.)
    Estas cámaras tienen implementaciones RTSP no estándar que requieren configuraciones especiales.
    """
    
    # SOLUCIÓN 1: Forzar UDP y deshabilitar verificaciones estrictas
    # Las cámaras chinas a menudo fallan con TCP debido a su implementación propietaria
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
        "rtsp_transport;udp|"
        "rtsp_flags;prefer_tcp|"
        "allowed_media_types;video|"
        "timeout;5000000|"
        "stimeout;5000000"
    )
    
    logging.info("🔧 Intentando conexión con UDP (modo cámaras chinas)...")
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    
    if cap.isOpened():
        # Configurar buffer mínimo (cámaras chinas tienen latencia alta)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Intentar leer un frame de prueba
        for attempt in range(5):
            ret, frame = cap.read()
            if ret and frame is not None:
                logging.info(f"✅ Conexión exitosa con UDP (intento {attempt + 1})")
                return cap
            time.sleep(0.5)
        
        cap.release()
        logging.warning("UDP abierto pero no lee frames. Probando siguiente método...")
    
    # SOLUCIÓN 2: TCP con opciones relajadas
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
        "rtsp_transport;tcp|"
        "rtsp_flags;prefer_tcp|"
        "allowed_media_types;video"
    )
    
    logging.info("🔧 Intentando conexión con TCP relajado...")
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        for attempt in range(5):
            ret, frame = cap.read()
            if ret and frame is not None:
                logging.info(f"✅ Conexión exitosa con TCP (intento {attempt + 1})")
                return cap
            time.sleep(0.5)
        
        cap.release()
        logging.warning("TCP abierto pero no lee frames. Probando siguiente método...")
    
    # SOLUCIÓN 3: Sin especificar transporte (dejar que FFmpeg decida)
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "allowed_media_types;video"
    
    logging.info("🔧 Intentando conexión automática (FFmpeg decide)...")
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        for attempt in range(5):
            ret, frame = cap.read()
            if ret and frame is not None:
                logging.info(f"✅ Conexión exitosa en modo automático (intento {attempt + 1})")
                return cap
            time.sleep(0.5)
        
        cap.release()
    
    # SOLUCIÓN 4: URL alternativa con substream
    # Las cámaras Hikvision/Dahua tienen múltiples streams
    alternative_urls = [
        rtsp_url.replace("/onvif1", "/Streaming/Channels/101"),  # Hikvision mainstream
        rtsp_url.replace("/onvif1", "/Streaming/Channels/102"),  # Hikvision substream
        rtsp_url.replace("/onvif1", "/cam/realmonitor?channel=1&subtype=0"),  # Dahua
        rtsp_url.replace("/onvif1", "/h264/ch1/main/av_stream"),  # Genérico
        rtsp_url.replace("/onvif1", "/stream1"),  # Alternativa simple
    ]
    
    for alt_url in alternative_urls:
        logging.info(f"🔧 Probando URL alternativa: {alt_url.split('@')[1] if '@' in alt_url else alt_url}")
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
        
        cap = cv2.VideoCapture(alt_url, cv2.CAP_FFMPEG)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            ret, frame = cap.read()
            if ret and frame is not None:
                logging.info(f"✅ ¡Conexión exitosa con URL alternativa!")
                logging.info(f"💡 Actualiza tu .env.nano con esta URL: {alt_url}")
                return cap
            
            cap.release()
    
    logging.error("❌ No se pudo conectar con ningún método.")
    return None

# --- Análisis con IA ---

def analyze_frame_with_llm(base64_image, config):
    """Envía un frame al LLM local para análisis y devuelve la respuesta estructurada."""
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": config["model_name"],
        "messages": [
            {
                "role": "system",
                "content": config["system_prompt"]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    },
                    {
                        "type": "text",
                        "text": "Analiza esta imagen."
                    }
                ]
            }
        ],
        "max_tokens": 300,
        "stream": False
    }

    try:
        response = requests.post(config["lm_studio_api"], headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        
        response_json = response.json()
        content = response_json['choices'][0]['message']['content']
        
        analysis_result = json.loads(content)
        return analysis_result

    except requests.exceptions.RequestException as e:
        logging.error(f"Falló la petición a la API: {e}")
    except (json.JSONDecodeError, KeyError) as e:
        logging.error(f"Falló el parseo de la respuesta del LLM: {e}")
        if 'content' in locals():
            logging.error(f"Contenido de la respuesta: {content}")
    return None

# --- Sistema de Alertas ---

def send_telegram_alert(image_bytes, analysis, config):
    """Envía una alerta con una imagen a Telegram."""
    if not all([config["enable_telegram"], config["telegram_bot_token"], config["telegram_chat_id"]]):
        logging.warning("Telegram está habilitado pero las credenciales no están completas. Omitiendo alerta.")
        return

    url = f"https://api.telegram.org/bot{config['telegram_bot_token']}/sendPhoto"
    caption = (
        f"🚨 *Alerta Cognitiva: Riesgo Alto Detectado* 🚨\n\n"
        f"*Descripción:* {analysis.get('descripcion', 'N/A')}\n"
        f"*Evaluación:* {analysis.get('evaluacion', 'N/A')}\n"
        f"*Puntaje de Riesgo:* `{analysis.get('riesgo', 'N/A')}`"
    )
    
    files = {'photo': ('frame.jpg', image_bytes, 'image/jpeg')}
    data = {'chat_id': config['telegram_chat_id'], 'caption': caption, 'parse_mode': 'Markdown'}

    try:
        response = requests.post(url, files=files, data=data, timeout=30)
        response.raise_for_status()
        logging.info("Alerta de Telegram enviada exitosamente.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Falló el envío de la alerta de Telegram: {e}")

# --- Bucle Principal ---

def main():
    """Función principal que ejecuta el ciclo de monitoreo cognitivo."""
    setup_logging()
    config = load_configuration()
    
    logging.info("🤖 Sentinex Nano iniciado (Modo Cámaras Chinas)")
    logging.info(f"📡 URL RTSP: {config['rtsp_url']}")
    logging.info("💡 Probando múltiples métodos de conexión...")

    reconnect_attempts = 0
    max_reconnect_attempts = 3
    
    # Bucle externo para manejar reconexiones
    while True:
        cap = create_rtsp_capture_chinese_cam(config["rtsp_url"])
        
        if not cap:
            reconnect_attempts += 1
            logging.error(f"No se pudo abrir el stream RTSP (intento {reconnect_attempts}/{max_reconnect_attempts}).")
            
            if reconnect_attempts >= max_reconnect_attempts:
                logging.error("❌ Máximo de intentos alcanzado.")
                logging.info("\n🔧 SUGERENCIAS:")
                logging.info("1. Verifica que las credenciales sean correctas")
                logging.info("2. Prueba acceder desde VLC y copia la URL exacta")
                logging.info("3. Revisa si la cámara tiene habilitado RTSP en su configuración")
                logging.info("4. Intenta con el substream (menor calidad pero más compatible)")
                break
                
            wait_time = min(30, 10 * reconnect_attempts)
            logging.info(f"⏳ Esperando {wait_time} segundos antes de reintentar...")
            time.sleep(wait_time)
            continue

        reconnect_attempts = 0
        logging.info("🎥 Stream RTSP conectado y funcionando correctamente.")
        
        last_capture_time = 0
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        # Bucle interno para procesar frames
        while cap.isOpened():
            ret, frame = cap.read()
            
            if not ret:
                consecutive_errors += 1
                logging.warning(f"⚠️ Error leyendo frame ({consecutive_errors}/{max_consecutive_errors}).")
                
                if consecutive_errors >= max_consecutive_errors:
                    logging.error("Demasiados errores consecutivos. Reconectando...")
                    break
                
                time.sleep(2)
                continue

            # Frame leído correctamente
            consecutive_errors = 0
            current_time = time.time()
            
            # Saltar frames según el intervalo configurado
            if current_time - last_capture_time < config["interval"]:
                continue
            
            last_capture_time = current_time
            logging.info("🎞️  Capturando frame para análisis...")

            try:
                resized_frame = resize_frame(frame, config["frame_scale"], config["frame_max_width"])
                base64_image = encode_image_to_base64(resized_frame)

                logging.info("🧠 Enviando frame al LLM para análisis...")
                analysis = analyze_frame_with_llm(base64_image, config)

                if analysis and isinstance(analysis, dict):
                    risk_score = float(analysis.get("riesgo", 0.0))
                    logging.info(f"✅ Análisis completo. Puntaje de riesgo: {risk_score}")

                    if risk_score >= config["risk_threshold"]:
                        logging.warning(f"⚠️ ¡Riesgo alto detectado! Puntaje: {risk_score}. Enviando alerta...")
                        _, img_bytes = cv2.imencode('.jpg', resized_frame)
                        send_telegram_alert(img_bytes.tobytes(), analysis, config)
                else:
                    logging.error("El análisis no devolvió un resultado válido.")

            except Exception as e:
                logging.error(f"Error procesando frame: {e}", exc_info=True)
        
        cap.release()
        logging.info("Stream RTSP liberado. Reintentando conexión en 5 segundos...")
        time.sleep(5)

if __name__ == "__main__":
    main()