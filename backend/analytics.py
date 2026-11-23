import re
from typing import List, Dict, Any
from .db import get_db_connection

# Diccionarios léxicos en español para análisis de sentimiento rápido y ligero
POSITIVE_WORDS = {
    "excelente", "bien", "bueno", "perfecto", "acuerdo", "gracias", "genial",
    "éxito", "correcto", "aprobado", "felicitaciones", "avance", "solución",
    "claro", "positivo", "listo", "logrado", "oportunidad", "mejor", "gran"
}

NEGATIVE_WORDS = {
    "problema", "error", "mal", "retraso", "difícil", "complicado", "bloqueo",
    "fallo", "riesgo", "grave", "duda", "cancelado", "urgente", "crítico",
    "preocupación", "rechazado", "conflicto", "pérdida", "negativo", "costoso"
}

ACTION_KEYWORDS = [
    r"(?:vamos a|se debe|hay que|acordamos|compromiso de|tarea para|encargado|responsable)\s+([^\.]+)",
    r"(?:revisar|enviar|entregar|preparar|agendar|actualizar)\s+([^\.]+)",
    r"(?:pendiente|action item|to-do):\s*([^\.]+)"
]

def analyze_sentiment(text: str) -> str:
    words = re.findall(r'\b\w+\b', text.lower())
    if not words:
        return "neutral"
    
    pos_count = sum(1 for w in words if w in POSITIVE_WORDS)
    neg_count = sum(1 for w in words if w in NEGATIVE_WORDS)
    
    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    return "neutral"

def calculate_talk_metrics(transcripts: List[Dict[str, Any]], total_duration_seconds: float) -> Dict[str, Any]:
    """
    Calcula porcentaje de habla (% Talk-Time) y ritmo (WPM - Words Per Minute) por hablante.
    """
    speakers_data: Dict[str, Dict[str, Any]] = {}
    
    for t in transcripts:
        spk = t.get("speaker", "Hablante Desconocido")
        dur = max(0.0, float(t.get("end_time", 0)) - float(t.get("start_time", 0)))
        words = len(t.get("text", "").split())
        
        if spk not in speakers_data:
            speakers_data[spk] = {
                "name": spk,
                "seconds_spoken": 0.0,
                "word_count": 0,
                "turns": 0
            }
        
        speakers_data[spk]["seconds_spoken"] += dur
        speakers_data[spk]["word_count"] += words
        speakers_data[spk]["turns"] += 1
        
    duration = total_duration_seconds if total_duration_seconds > 0 else sum(s["seconds_spoken"] for s in speakers_data.values())
    duration = max(1.0, duration)
    
    results = []
    for spk, data in speakers_data.items():
        pct = (data["seconds_spoken"] / duration) * 100.0
        minutes = max(0.1, data["seconds_spoken"] / 60.0)
        wpm = round(data["word_count"] / minutes)
        results.append({
            "speaker": spk,
            "seconds_spoken": round(data["seconds_spoken"], 1),
            "percentage": round(pct, 1),
            "wpm": wpm,
            "turns": data["turns"]
        })
        
    results.sort(key=lambda x: x["percentage"], reverse=True)
    return {
        "speakers": results,
        "total_speakers": len(results),
        "total_duration": round(duration, 1)
    }

def extract_action_items(meeting_id: str, transcripts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extrae compromisos, tareas y tareas pendientes de la transcripción y las guarda en la base de datos.
    """
    items = []
    conn = get_db_connection()
    
    for t in transcripts:
        text = t.get("text", "")
        speaker = t.get("speaker", "Equipo")
        for pattern in ACTION_KEYWORDS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                clean_task = m.strip()
                if len(clean_task) > 8 and len(clean_task) < 150:
                    items.append({
                        "meeting_id": meeting_id,
                        "task": clean_task,
                        "assignee": speaker,
                        "completed": 0
                    })
                    
    # Guardar en DB
    with conn:
        for item in items:
            conn.execute(
                "INSERT INTO action_items (meeting_id, task, assignee, completed) VALUES (?, ?, ?, 0)",
                (meeting_id, item["task"], item["assignee"])
            )
    conn.close()
    return items
