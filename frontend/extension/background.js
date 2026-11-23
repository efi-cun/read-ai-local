// ReadAI Local - Background Service Worker (Manifest V3)
console.log("[ReadAI Local Background] Service Worker iniciado.");

let recordingState = {
    isRecording: false,
    meetCode: null,
    tabId: null
};

// Crear o verificar el documento Offscreen para grabación
async function setupOffscreenDocument() {
    const existingContexts = await chrome.runtime.getContexts({
        contextTypes: ['OFFSCREEN_DOCUMENT']
    });

    if (existingContexts.length === 0) {
        await chrome.offscreen.createDocument({
            url: 'offscreen.html',
            reasons: ['USER_MEDIA'],
            justification: 'Grabación de audio y video de la pestaña de Google Meet para ReadAI Local'
        });
        console.log("[ReadAI Background] Documento Offscreen creado.");
    }
}

// Escuchar mensajes de content.js
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    (async () => {
        if (message.type === 'START_AUTO_RECORDING') {
            if (recordingState.isRecording) {
                sendResponse({ status: 'already_recording' });
                return;
            }

            try {
                const targetTabId = sender.tab ? sender.tab.id : null;
                if (!targetTabId) {
                    sendResponse({ status: 'error', message: 'No tab id' });
                    return;
                }

                await setupOffscreenDocument();

                // Obtener ID del Stream de la pestaña
                const streamId = await chrome.tabCapture.getMediaStreamId({
                    targetTabId: targetTabId
                });

                recordingState.isRecording = true;
                recordingState.meetCode = message.meetCode;
                recordingState.tabId = targetTabId;

                // Enviar comando a offscreen.js
                chrome.runtime.sendMessage({
                    type: 'OFFSCREEN_START_CAPTURE',
                    streamId: streamId,
                    meetCode: message.meetCode
                });

                console.log(`[ReadAI Background] Grabación iniciada para Meet: ${message.meetCode}`);
                sendResponse({ status: 'recording_started' });
            } catch (err) {
                console.error("[ReadAI Background] Error iniciando captura:", err);
                sendResponse({ status: 'error', error: err.toString() });
            }
        } else if (message.type === 'STOP_RECORDING') {
            if (!recordingState.isRecording) {
                sendResponse({ status: 'not_recording' });
                return;
            }

            recordingState.isRecording = false;
            chrome.runtime.sendMessage({
                type: 'OFFSCREEN_STOP_CAPTURE',
                meetCode: recordingState.meetCode
            });

            console.log(`[ReadAI Background] Grabación finalizada para Meet: ${recordingState.meetCode}`);
            sendResponse({ status: 'recording_stopped' });
        } else if (message.type === 'GET_RECORDING_STATUS') {
            sendResponse(recordingState);
        }
    })();
    return true; // Asíncrono
});
