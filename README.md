# ReadAI Local - MeetSense

Un sistema autónomo, local y privado de inteligencia de reuniones y control automatizado de asistencia para Google Meet, sin suscripciones ni dependencias de servicios externos.

---

## 🚀 Características Principales

1. **Control de Asistencia Automatizado en Google Meet:**
   - Detecta la entrada y salida de cada participante en tiempo real con su nombre oficial de Google.
   - Registra hora exacta de ingreso, hora de salida y permanencia.
   - Clasificación automática: `Presente (Puntual)`, `Tardanza` (umbral configurable) o `Ausente`.
   - Soporte para precargar listas oficiales de estudiantes o convocados (Roster).
   - Exportación de reportes oficiales de asistencia a **Excel (.xlsx)** con un solo clic.

2. **Transcripción Inteligente de Reuniones:**
   - Transcripción local de audio y video con marcas de tiempo usando `faster-whisper`.
   - Detección y separación por participantes (Hablante 1, Hablante 2, etc.).
   - Reproductor web con transcripción sincronizada: haz clic en cualquier frase o minuto para saltar directamente al audio.

3. **Métricas de Reunión (Estilo Read AI):**
   - Distribución de tiempo de habla (% Talk-Time) por participante en gráfico circular interactivo.
   - Ritmo de habla en palabras por minuto (WPM).
   - Análisis de sentimiento (positivo, neutral, negativo) por turno de habla.
   - Extracción automática de compromisos y tareas pendientes (*Action Items*).

4. **"Ask Read" (Motor RAG Conversacional):**
   - Asistente conversacional en lenguaje natural (`/analytics/ask`).
   - Responde preguntas sobre asistencia: *"¿Quiénes faltaron a la sesión?"*, *"¿A qué hora ingresó María?"*.
   - Responde preguntas sobre contenido: *"¿Cuáles son los acuerdos del proyecto?"*.
   - Cita la hora exacta y el participante responsable.

---

## 🛠️ Instalación y Puesta en Marcha

### 1. Iniciar la Aplicación
En una terminal (PowerShell o CMD), navega a esta carpeta y ejecuta:
```bash
python run.py
```
El servidor se iniciará en `http://localhost:8000` y abrirá automáticamente tu navegador web.

---

## 🧩 Conectar con Google Meet (Extensión de Navegador)

Para capturar la asistencia automáticamente mientras estás en una reunión de Google Meet:

1. Abre Google Chrome o Microsoft Edge y ve a:
   - En Chrome: `chrome://extensions`
   - En Edge: `edge://extensions`
2. Activa la casilla **Modo Desarrollador** (esquina superior derecha).
3. Haz clic en el botón **"Cargar descomprimida"** (o *Load unpacked*).
4. Selecciona la carpeta:
   `...\read_ai_local\frontend\extension`
5. ¡Listo! Cuando ingreses a cualquier llamada de Google Meet, verás un widget flotante en la esquina inferior izquierda sincronizando las asistencias en tiempo real con tu panel local.

---

## 📁 Estructura del Proyecto

- `backend/`
  - `app.py`: Servidor FastAPI con WebSockets y rutas REST.
  - `attendance.py`: Lógica de cálculo de puntualidad y exportador Excel.
  - `transcriber.py`: Motor local de transcripción faster-whisper.
  - `analytics.py`: Algoritmos de Talk-Time, WPM, sentimiento y action items.
  - `rag_engine.py`: Motor conversacional "Ask Read" con citas.
  - `db.py`: Base de datos SQLite (`meetings.db`).
- `frontend/`
  - `extension/`: Extensión Manifest V3 para Chrome y Edge.
  - `templates/`: Vistas HTML modernas con Tailwind CSS y Chart.js.
  - `static/`: Estilos CSS y scripts del cliente.
- `data/`
  - `reports/`: Informes Excel generados descargables.
  - `uploads/`: Grabaciones multimedia subidas.
