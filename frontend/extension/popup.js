// ReadAI Local - Popup Script
const CHECK_URL = "http://localhost:8000/api/meetings";

async function checkServerStatus() {
    const badge = document.getElementById("statusBadge");
    const dot = document.getElementById("statusDot");
    const text = document.getElementById("statusText");
    const btnPanel = document.getElementById("btnOpenPanel");
    const btnLaunch = document.getElementById("btnLaunchBat");
    const alertBox = document.getElementById("offlineAlert");

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 1200);
        const res = await fetch(CHECK_URL, { signal: controller.signal });
        clearTimeout(timeoutId);

        if (res.ok) {
            badge.className = "badge badge-online";
            dot.className = "dot dot-online";
            text.innerText = "Servidor Activo";
            btnPanel.style.display = "block";
            btnLaunch.style.display = "none";
            alertBox.style.display = "none";
            return;
        }
    } catch (e) {
        // Servidor apagado
    }

    badge.className = "badge badge-offline";
    dot.className = "dot dot-offline";
    text.innerText = "Servidor Apagado";
    btnPanel.style.display = "none";
    btnLaunch.style.display = "block";
    alertBox.style.display = "block";
}

// Iniciar servidor al dar clic en el botón
document.getElementById("btnLaunchBat").addEventListener("click", () => {
    // Abrir el protocolo de Windows readai:// que ejecuta iniciar_servidor.bat
    window.location.href = "readai://start";
    
    // Monitorear hasta que el servidor despierte
    const checkInterval = setInterval(async () => {
        try {
            const res = await fetch(CHECK_URL);
            if (res.ok) {
                clearInterval(checkInterval);
                checkServerStatus();
            }
        } catch (e) {}
    }, 2000);
});

checkServerStatus();
