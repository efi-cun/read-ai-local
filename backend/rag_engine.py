import os
import re
import requests
from typing import List, Dict, Any, Optional
from .db import get_db_connection, list_meetings, get_meeting_participants, get_meeting_transcripts, get_meeting_action_items
from .config import OLLAMA_URL, OLLAMA_MODEL, GEMINI_API_KEY, GROQ_API_KEY

def format_seconds_to_time(seconds: float) -> str:
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"

def query_attendance_intent(query: str, meeting_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Detecta si la pregunta del usuario es sobre asistencia o puntualidad."""
    q_lower = query.lower()
    attendance_keywords = [
        "asist", "falto", "faltó", "ausente", "presente", "tarde", "tardanza", 
        "hora de entrada", "hora de ingreso", "ingres", "ingresó", "ingreso", 
        "entró", "entro", "llegó", "llego", "estuvo"
    ]
    if not any(k in q_lower for k in attendance_keywords):
        return None
        
    conn = get_db_connection()
    cur = conn.cursor()
    
    if meeting_id:
        cur.execute("SELECT * FROM participants WHERE meeting_id = ?", (meeting_id,))
    else:
        # Última reunión
        cur.execute("SELECT * FROM participants ORDER BY id DESC LIMIT 50")
    
    participants = [dict(r) for r in cur.fetchall()]
    conn.close()
    
    if not participants:
        return None
        
    presentes = [p["name"] for p in participants if p["status"] == "Presente"]
    tardanzas = [f"{p['name']} (ingresó a las {p['entry_time']})" for p in participants if p["status"] == "Tardanza"]
    ausentes = [p["name"] for p in participants if p["status"] == "Ausente"]
    
    # Comprobar si pregunta por alguien específico
    for p in participants:
        if p["name"].lower() in q_lower:
            status_text = f"El participante **{p['name']}** figura como **{p['status']}**."
            if p["entry_time"]:
                status_text += f" Registró su ingreso a las **{p['entry_time']}**."
            if p["exit_time"]:
                status_text += f" Última salida: {p['exit_time']}."
            return {
                "answer": status_text,
                "sources": [{"title": f"Registro de Asistencia: {p['name']}", "timestamp": p["entry_time"] or "--:--"}]
            }
            
    # Respuesta general de asistencia
    answer_parts = []
    if "falto" in q_lower or "faltó" in q_lower or "ausente" in q_lower:
        if ausentes:
            answer_parts.append(f"❌ **Ausentes ({len(ausentes)}):**\n- " + "\n- ".join(ausentes))
        else:
            answer_parts.append("✅ No hubo ausentes; todos los convocados asistieron a la reunión.")
    elif "tarde" in q_lower or "tardanza" in q_lower:
        if tardanzas:
            answer_parts.append(f"⚠️ **Tardanzas ({len(tardanzas)}):**\n- " + "\n- ".join(tardanzas))
        else:
            answer_parts.append("✅ No se registraron tardanzas; todos ingresaron puntualmente.")
    else:
        answer_parts.append(f"📊 **Resumen General de Asistencia:**\n- **Presentes:** {len(presentes)}\n- **Tardanzas:** {len(tardanzas)}\n- **Ausentes:** {len(ausentes)}")
        if ausentes:
            answer_parts.append(f"\n❌ **Ausentes:** {', '.join(ausentes)}")
        if tardanzas:
            answer_parts.append(f"\n⚠️ **Tardanzas:** {', '.join(tardanzas)}")
            
    return {
        "answer": "\n".join(answer_parts),
        "sources": [{"title": "Reporte de Asistencia en Tiempo Real", "timestamp": "Asistencia"}]
    }

def ask_read_agent(query: str, meeting_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Motor RAG principal de 'Ask Read'.
    Busca semánticamente en las reuniones y sintetiza una respuesta con citas de tiempo y hablante.
    """
    # 1. Verificar si es una consulta de asistencia
    attendance_resp = query_attendance_intent(query, meeting_id)
    if attendance_resp:
        return attendance_resp
        
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 2. Recuperar transcripciones relevantes
    if meeting_id:
        cur.execute("SELECT * FROM transcripts WHERE meeting_id = ? ORDER BY start_time ASC", (meeting_id,))
    else:
        cur.execute("SELECT * FROM transcripts ORDER BY id DESC LIMIT 200")
        
    transcripts = [dict(r) for r in cur.fetchall()]
    
    # Recuperar compromisos / action items
    if meeting_id:
        cur.execute("SELECT * FROM action_items WHERE meeting_id = ?", (meeting_id,))
    else:
        cur.execute("SELECT * FROM action_items ORDER BY id DESC LIMIT 50")
    actions = [dict(r) for r in cur.fetchall()]
    conn.close()
    
    if not transcripts and not actions:
        return {
            "answer": "No hay transcripciones o reuniones grabadas todavía. Sube un archivo de audio/video o conéctate a una llamada de Google Meet para comenzar a consultar.",
            "sources": []
        }
        
    # 3. Búsqueda semántica / por palabras clave en los segmentos
    keywords = [w.lower() for w in re.findall(r'\b\w{4,}\b', query)]
    matched_segments = []
    
    for t in transcripts:
        text_lower = t["text"].lower()
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            matched_segments.append((score, t))
            
    matched_segments.sort(key=lambda x: x[0], reverse=True)
    top_segments = [s[1] for s in matched_segments[:6]]
    
    # Si no hubo match específico, tomar los primeros segmentos clave
    if not top_segments:
        top_segments = transcripts[:5]
        
    sources = []
    context_lines = []
    for seg in top_segments:
        ts = format_seconds_to_time(seg["start_time"])
        speaker = seg["speaker"]
        text = seg["text"]
        context_lines.append(f"[{ts}] {speaker}: {text}")
        sources.append({
            "title": f"{speaker} ({ts})",
            "timestamp": ts,
            "text": text[:80] + "..." if len(text) > 80 else text
        })
        
    context_str = "\n".join(context_lines)
    
    # 4. Generación con LLM (Ollama / Gemini o Extractor Local)
    # Intentar Ollama si está activo
    try:
        ollama_resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": f"Eres el asistente inteligente de reuniones 'Ask Read'. Responde la siguiente pregunta del usuario basándote únicamente en el contexto de la reunión proporcionado. Cita la hora [MM:SS] y quién lo dijo.\n\nContexto:\n{context_str}\n\nPregunta: {query}\n\nRespuesta precisa en español:",
                "stream": False
            },
            timeout=3
        )
        if ollama_resp.status_code == 200:
            ai_text = ollama_resp.json().get("response", "").strip()
            if ai_text:
                return {"answer": ai_text, "sources": sources}
    except Exception:
        pass
        
    # Extractor inteligente local offline (Garantizado sin requerir internet ni GPU pesada)
    summary_bullets = []
    for seg in top_segments[:3]:
        ts = format_seconds_to_time(seg["start_time"])
        summary_bullets.append(f"- En el minuto **[{ts}]**, **{seg['speaker']}** mencionó: *\"{seg['text']}\"*")
        
    answer = f"Según el análisis de las intervenciones registradas:\n\n" + "\n".join(summary_bullets)
    if actions:
        answer += "\n\n📌 **Compromisos y Tareas identificadas:**\n" + "\n".join([f"- **{a['assignee']}**: {a['task']}" for a in actions[:3]])
        
    return {
        "answer": answer,
        "sources": sources
    }
