// ReadAI Local - Content Script para Google Meet
console.log("[ReadAI Local] Extensión cargada en Google Meet.");

const BACKEND_URL = "http://localhost:8000/api/meet/event";
let knownParticipants = new Set();
let meetCode = window.location.pathname.replace(/^\//, "");

// 1. Inyectar Widget Flotante en la pantalla de Meet
function injectFloatingWidget() {
    if (document.getElementById("readai-widget")) return;

    const widget = document.createElement("div");
    widget.id = "readai-widget";
    widget.style.position = "fixed";
    widget.style.bottom = "85px";
    widget.style.left = "20px";
    widget.style.zIndex = "999999";
    widget.style.background = "#1E293B";
    widget.style.color = "#FFFFFF";
    widget.style.padding = "10px 16px";
    widget.style.borderRadius = "12px";
    widget.style.boxShadow = "0 10px 25px rgba(0,0,0,0.5)";
    widget.style.fontFamily = "system-ui, -apple-system, sans-serif";
    widget.style.fontSize = "13px";
    widget.style.display = "flex";
    widget.style.alignItems = "center";
    widget.style.gap = "10px";
    widget.style.border = "1px solid #334155";

    widget.innerHTML = `
        <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:#22C55E; box-shadow:0 0 8px #22C55E;"></span>
        <span><b>ReadAI Local:</b> <span id="readai-count">0</span> asistencias</span>
        <button id="readai-sync-btn" style="background:#3B82F6; color:white; border:none; padding:4px 10px; border-radius:6px; cursor:pointer; font-size:11px; font-weight:600;">Sincronizar</button>
    `;

    document.body.appendChild(widget);

    document.getElementById("readai-sync-btn").addEventListener("click", () => {
        scanParticipants();
    });
}

// 2. Enviar evento al servidor local
async function sendEvent(name, eventType) {
    try {
        const payload = {
            meet_code: meetCode,
            participant_name: name,
            event_type: eventType,
            timestamp: new Date().toLocaleTimeString("es-CO", { hour12: false })
        };
        const res = await fetch(BACKEND_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            console.log(`[ReadAI Local] Sincronizado: ${name} (${eventType})`);
        }
    } catch (err) {
        console.warn("[ReadAI Local] No se pudo contactar localhost:8000. Asegúrate de ejecutar 'python run.py'.", err);
    }
}

// 3. Escanear el DOM de Google Meet en busca de nombres de personas
function scanParticipants() {
    const namesFound = new Set();

    // Selector 1: Tarjetas de participantes y subtítulos
    const participantElements = document.querySelectorAll('[data-participant-id], [data-self-name], span.zWGUib, div[role="listitem"] span');
    participantElements.forEach(el => {
        const name = el.innerText ? el.innerText.trim() : "";
        if (name && name.length > 2 && name.length < 50 && !name.includes("\n") && !name.includes(":") && name !== "Tú" && name !== "You") {
            namesFound.add(name);
        }
    });

    // Detectar quiénes acaban de unirse
    namesFound.forEach(name => {
        if (!knownParticipants.has(name)) {
            knownParticipants.add(name);
            sendEvent(name, "JOIN");
        }
    });

    // Actualizar contador del widget flotante
    const countEl = document.getElementById("readai-count");
    if (countEl) countEl.innerText = knownParticipants.size;
}

// Iniciar observador continuo
setInterval(injectFloatingWidget, 3000);
setInterval(scanParticipants, 4000);

// Observar mutaciones en el DOM para detección instantánea
const observer = new MutationObserver(() => {
    scanParticipants();
});

observer.observe(document.body, { childList: true, subtree: true });
