import numpy as np
from scipy.io import wavfile
from scipy import signal

# --- CONFIGURACIÓN DE LA ALARMA ---
fs = 44100           # Calidad de audio
frecuencia_1 = 800   # Tono Alto (Hz)
frecuencia_2 = 500   # Tono Bajo (Hz)
velocidad = 0.4      # Cuánto dura cada "ui" (segundos)
repeticiones = 8     # Cuántas veces hace "ui-u"

# --- GENERACIÓN ---
# Creamos el tiempo para UN solo ciclo (el tono alto)
t = np.linspace(0, velocidad, int(fs * velocidad), endpoint=False)

# Generamos los dos trozos de audio (Onda Cuadrada pa que suene fuerte)
# Si quieres que sea más suave, cambia 'signal.square' por 'np.sin'
tono_alto = 0.5 * signal.square(2 * np.pi * frecuencia_1 * t)
tono_bajo = 0.5 * signal.square(2 * np.pi * frecuencia_2 * t)

# Pegamos los tonos: Alto -> Bajo
ciclo_completo = np.concatenate((tono_alto, tono_bajo))

# Repetimos el ciclo las veces que dijimos (pa que dure harto)
alarma_final = np.tile(ciclo_completo, repeticiones)

# --- GUARDAR ---
# Convertir a 16-bit
datos_int16 = np.int16(alarma_final * 32767)
nombre_archivo = 'alarma_infernal.wav'

wavfile.write(nombre_archivo, fs, datos_int16)

print(f"¡Listo el pollo! Se creó el archivo: {nombre_archivo}")
print("Ábrelo con cuidado que suena juerte.")