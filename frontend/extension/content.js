// ReadAI Local - Content Script para Google Meet (Asistencia + Grabación Automática)
console.log("[ReadAI Local] Extensión cargada en Google Meet.");

const BACKEND_URL = "http://localhost:8000/api/meet/event";
let knownParticipants = new Set();
let meetCode = window.location.pathname.replace(/^\//, "");
let isRecordingActive = false;
let recordingSeconds = 0;
let recordingTimerInterval = null;

// 1. Inyectar Widget Flotante Mejorado con Estado de Grabación y Asistencia
function injectFloatingWidget() {
    if (document.getElementById("readai-widget")) return;

    const widget = document.createElement("div");
    widget.id = "readai-widget";
    widget.style.position = "fixed";
    widget.style.bottom = "85px";
    widget.style.left = "20px";
    widget.style.zIndex = "999999";
    widget.style.background = "#0F172A";
    widget.style.color = "#FFFFFF";
    widget.style.padding = "10px 18px";
    widget.style.borderRadius = "14px";
    widget.style.boxShadow = "0 10px 30px rgba(0,0,0,0.6)";
    widget.style.fontFamily = "system-ui, -apple-system, sans-serif";
    widget.style.fontSize = "12px";
    widget.style.display = "flex";
    widget.style.alignItems = "center";
    widget.style.gap = "12px";
    widget.style.border = "1px solid #334155";

    widget.innerHTML = `
        <div style="display:flex; align-items:center; gap:8px;">
            <span id="readai-rec-dot" style="display:inline-block; width:10px; height:10px; border-radius:50%; background:#EF4444; box-shadow:0 0 10px #EF4444; animation: pulse 1.5s infinite;"></span>
            <span style="font-weight:700; color:#F8FAFC;">ReadAI Local:</span>
            <span id="readai-rec-time" style="font-family:monospace; color:#EF4444; font-weight:600;">00:00</span>
        </div>
        <div style="color:#94A3B8; font-size:11px;">|</div>
        <div>
            <span>👥 <span id="readai-count" style="font-weight:700; color:#38BDF8;">0</span> presentes</span>
        </div>
        <button id="readai-stop-btn" style="background:#DC2626; color:white; border:none; padding:4px 10px; border-radius:6px; cursor:pointer; font-size:11px; font-weight:600; display:none;">Guardar</button>
    `;

    document.body.appendChild(widget);

    document.getElementById("readai-stop-btn").addEventListener("click", () => {
        stopAutoRecording();
    });
}

// 2. Iniciar Grabación Automática de Audio y Video
function startAutoRecording() {
    if (isRecordingActive) return;

    chrome.runtime.sendMessage({
        type: 'START_AUTO_RECORDING',
        meetCode: meetCode
    }, (response) => {
        if (response && (response.status === 'recording_started' || response.status === 'already_recording')) {
            isRecordingActive = true;
            console.log("[ReadAI Local] Grabación automática de video y audio activada.");

            const stopBtn = document.getElementById("readai-stop-btn");
            if (stopBtn) stopBtn.style.display = "inline-block";

            // Timer en vivo
            if (!recordingTimerInterval) {
                recordingTimerInterval = setInterval(() => {
                    recordingSeconds++;
                    const mins = String(Math.floor(recordingSeconds / 60)).padStart(2, '0');
                    const secs = String(recordingSeconds % 60).padStart(2, '0');
                    const timeEl = document.getElementById("readai-rec-time");
                    if (timeEl) timeEl.innerText = `${mins}:${secs}`;
                }, 1000);
            }
        }
    });
}

// 3. Detener y Subir Grabación Automáticamente al Colgar
function stopAutoRecording() {
    if (!isRecordingActive) return;
    isRecordingActive = false;

    if (recordingTimerInterval) {
        clearInterval(recordingTimerInterval);
        recordingTimerInterval = null;
    }

    const dot = document.getElementById("readai-rec-dot");
    if (dot) dot.style.background = "#64748B";

    chrome.runtime.sendMessage({
        type: 'STOP_RECORDING'
    });
    console.log("[ReadAI Local] Grabación finalizada y enviada al servidor.");
}

// 4. Enviar Evento de Asistencia al Servidor Local
async function sendAttendanceEvent(name, eventType) {
    try {
        const payload = {
            meet_code: meetCode,
            participant_name: name,
            event_type: eventType,
            timestamp: new Date().toLocaleTimeString("es-CO", { hour12: false })
        };
        await fetch(BACKEND_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
    } catch (err) {
        console.warn("[ReadAI Local] No se pudo conectar con localhost:8000.", err);
    }
}

// 5. Escaneo de Participantes
function scanParticipants() {
    const namesFound = new Set();
    const participantElements = document.querySelectorAll('[data-participant-id], [data-self-name], span.zWGUib, div[role="listitem"] span');
    
    participantElements.forEach(el => {
        const name = el.innerText ? el.innerText.trim() : "";
        if (name && name.length > 2 && name.length < 50 && !name.includes("\n") && !name.includes(":") && name !== "Tú" && name !== "You") {
            namesFound.add(name);
        }
    });

    namesFound.forEach(name => {
        if (!knownParticipants.has(name)) {
            knownParticipants.add(name);
            sendAttendanceEvent(name, "JOIN");
        }
    });

    const countEl = document.getElementById("readai-count");
    if (countEl) countEl.innerText = knownParticipants.size;

    // Si ya hay participantes o estamos en la llamada, iniciar grabación automáticamente
    if (!isRecordingActive && (namesFound.size > 0 || document.querySelector('button[aria-label*="Salir"], button[aria-label*="Leave"], div[data-is-muted]'))) {
        startAutoRecording();
    }
}

// 6. Detectar cuando el usuario cuelga o abandona la reunión
function setupHangupListeners() {
    document.addEventListener("click", (e) => {
        const target = e.target.closest('button[aria-label*="Salir"], button[aria-label*="Leave"], button[data-call-ended]');
        if (target) {
            console.log("[ReadAI Local] Clic en botón de salir detectado.");
            stopAutoRecording();
        }
    });

    window.addEventListener("beforeunload", () => {
        stopAutoRecording();
    });
}

// Inicialización Continua
setInterval(injectFloatingWidget, 2500);
setInterval(scanParticipants, 3500);
setupHangupListeners();

const observer = new MutationObserver(() => {
    scanParticipants();
});
observer.observe(document.body, { childList: true, subtree: true });
