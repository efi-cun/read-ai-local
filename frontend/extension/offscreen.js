// ReadAI Local - Offscreen Document MediaRecorder
console.log("[ReadAI Offscreen] Documento cargado para procesamiento multimedia.");

let mediaRecorder = null;
let recordedChunks = [];
let currentMeetCode = null;

chrome.runtime.onMessage.addListener(async (message) => {
    if (message.type === 'OFFSCREEN_START_CAPTURE') {
        const streamId = message.streamId;
        currentMeetCode = message.meetCode;
        recordedChunks = [];

        try {
            // Capturar Audio y Video de la pestaña
            const mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    mandatory: {
                        chromeMediaSource: 'tab',
                        chromeMediaSourceId: streamId
                    }
                },
                video: {
                    mandatory: {
                        chromeMediaSource: 'tab',
                        chromeMediaSourceId: streamId,
                        maxFrameRate: 30
                    }
                }
            });

            // Configurar MediaRecorder
            let options = { mimeType: 'video/webm;codecs=vp8,opus' };
            if (!MediaRecorder.isTypeSupported(options.mimeType)) {
                options = { mimeType: 'video/webm' };
            }

            mediaRecorder = new MediaRecorder(mediaStream, options);

            mediaRecorder.ondataavailable = (event) => {
                if (event.data && event.data.size > 0) {
                    recordedChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = async () => {
                console.log("[ReadAI Offscreen] Grabación terminada. Enviando al servidor local...");
                const blob = new Blob(recordedChunks, { type: 'video/webm' });
                await uploadRecording(blob, currentMeetCode);

                // Detener todas las pistas de la pestaña
                mediaStream.getTracks().forEach(t => t.stop());
            };

            mediaRecorder.start(1000); // Grabar en bloques de 1 segundo
            console.log("[ReadAI Offscreen] MediaRecorder activo grabando audio y video.");
        } catch (err) {
            console.error("[ReadAI Offscreen] Error obteniendo UserMedia:", err);
        }
    } else if (message.type === 'OFFSCREEN_STOP_CAPTURE') {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }
    }
});

// Enviar el archivo de video al servidor local FastAPI
async function uploadRecording(blob, meetCode) {
    try {
        const formData = new FormData();
        const filename = `meet_${meetCode || 'sesion'}_${Date.now()}.webm`;
        formData.append("title", `Sesión Meet: ${meetCode || 'Grabación Automática'}`);
        formData.append("meet_code", meetCode || "");
        formData.append("file", blob, filename);

        const response = await fetch("http://localhost:8000/api/upload", {
            method: "POST",
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            console.log("[ReadAI Offscreen] Video subido exitosamente a :8000:", data);
        } else {
            console.warn("[ReadAI Offscreen] Error al subir video a :8000:", response.status);
        }
    } catch (err) {
        console.error("[ReadAI Offscreen] Error de red al subir la grabación:", err);
    }
}
