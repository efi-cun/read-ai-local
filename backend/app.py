import os
import uuid
import json
import shutil
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from pydantic import BaseModel

from .config import BASE_DIR, UPLOADS_DIR, REPORTS_DIR, ROSTERS_DIR
from .db import (
    init_db, get_meeting, list_meetings, create_meeting,
    get_meeting_participants, get_meeting_transcripts, get_meeting_action_items,
    get_db_connection
)
from .attendance import record_participant_event, export_attendance_excel, load_roster_into_meeting
from .analytics import calculate_talk_metrics, extract_action_items
from .transcriber import transcribe_audio_file
from .rag_engine import ask_read_agent
from .calendar_sync import get_calendar_url, save_calendar_url, fetch_calendar_events, find_calendar_event_for_meet

# Inicializar Base de Datos
init_db()

app = FastAPI(title="ReadAI Local - MeetSense", version="1.0.0")

# Montar estáticos y plantillas
templates = Jinja2Templates(directory=str(BASE_DIR / "frontend" / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "frontend" / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# Gestor de conexiones WebSocket para actualizaciones en vivo de asistencia
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

# --- MODELOS PYDANTIC ---
class MeetEventRequest(BaseModel):
    meeting_id: Optional[str] = None
    meet_code: Optional[str] = "N/A"
    participant_name: str
    event_type: str  # 'JOIN' o 'LEAVE'
    timestamp: Optional[str] = None

class AskRequest(BaseModel):
    query: str
    meeting_id: Optional[str] = None

class RosterLoadRequest(BaseModel):
    meeting_id: str
    names: List[str]

# --- VISTAS HTML ---
@app.get("/", response_class=HTMLResponse)
async def view_dashboard(request: Request):
    meetings = list_meetings()
    cal_url = get_calendar_url()
    cal_events = fetch_calendar_events()
    return templates.TemplateResponse(request=request, name="index.html", context={
        "meetings": meetings,
        "calendar_url": cal_url,
        "calendar_events": cal_events
    })

@app.get("/meetings/{meeting_id}", response_class=HTMLResponse)
async def view_meeting_detail(request: Request, meeting_id: str):
    meeting = get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Reunión no encontrada")
    participants = get_meeting_participants(meeting_id)
    transcripts = get_meeting_transcripts(meeting_id)
    actions = get_meeting_action_items(meeting_id)
    metrics = calculate_talk_metrics(transcripts, meeting["duration_seconds"] or 0)
    return templates.TemplateResponse(request=request, name="meeting.html", context={
        "meeting": meeting,
        "participants": participants,
        "transcripts": transcripts,
        "actions": actions,
        "metrics": metrics
    })

@app.get("/attendance", response_class=HTMLResponse)
async def view_attendance(request: Request, meeting_id: Optional[str] = None):
    meetings = list_meetings()
    selected_id = meeting_id or (meetings[0]["id"] if meetings else None)
    participants = get_meeting_participants(selected_id) if selected_id else []
    selected_meeting = get_meeting(selected_id) if selected_id else None
    return templates.TemplateResponse(request=request, name="attendance.html", context={
        "meetings": meetings,
        "selected_id": selected_id,
        "selected_meeting": selected_meeting,
        "participants": participants
    })

@app.get("/analytics/ask", response_class=HTMLResponse)
async def view_ask_read(request: Request, meeting_id: Optional[str] = None):
    meetings = list_meetings()
    return templates.TemplateResponse(request=request, name="ask.html", context={
        "meetings": meetings, 
        "meeting_id": meeting_id
    })

# --- ENDPOINTS API REST ---
@app.get("/api/meetings")
async def api_list_meetings():
    return list_meetings()

@app.post("/api/meetings/create")
async def api_create_meeting(title: str = Form(...), meet_code: str = Form("")):
    m_id = str(uuid.uuid4())[:8]
    meeting = create_meeting(m_id, title, meet_code)
    return {"status": "ok", "meeting": meeting}

@app.post("/api/meet/event")
async def api_meet_event(payload: MeetEventRequest):
    """
    Recibe eventos desde la Extensión de Google Meet en tiempo real.
    Si no se especifica meeting_id, usa la reunión activa más reciente o crea una automática.
    """
    m_id = payload.meeting_id
    if not m_id:
        # Buscar si existe una sesión activa para este mismo código creada en los últimos 60 minutos
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, created_at, meet_code FROM meetings 
            WHERE meet_code = ? AND status = 'live'
            ORDER BY created_at DESC LIMIT 1
            """,
            (payload.meet_code,)
        )
        row = cur.fetchone()
        conn.close()

        reuse_existing = False
        if row and row["created_at"]:
            try:
                created_dt = datetime.fromisoformat(row["created_at"])
                # Si se creó hace menos de 60 minutos, es la misma llamada en curso
                if (datetime.now() - created_dt).total_seconds() < 3600:
                    m_id = row["id"]
                    reuse_existing = True
            except Exception:
                pass

        if not reuse_existing:
            # Crear nueva sesión independiente para este día y hora
            m_id = str(uuid.uuid4())[:8]
            fecha_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
            session_title = f"Sesión Meet: {payload.meet_code} ({fecha_hora})"
            
            # Buscar si existe en el calendario de Google / Outlook
            cal_event = find_calendar_event_for_meet(payload.meet_code)
            if cal_event:
                session_title = f"{cal_event['title']} ({fecha_hora})"
                
            create_meeting(m_id, session_title, payload.meet_code)
            
            # Si el calendario tenía lista de invitados, precargarlos como lista esperada
            if cal_event and cal_event.get("attendees"):
                attendee_names = [a["name"] for a in cal_event["attendees"]]
                load_roster_into_meeting(m_id, attendee_names)
            
    res = record_participant_event(
        meeting_id=m_id,
        name=payload.participant_name,
        event_type=payload.event_type,
        custom_time=payload.timestamp
    )
    
    # Notificar a la UI vía WebSocket
    await manager.broadcast({
        "type": "ATTENDANCE_UPDATE",
        "meeting_id": m_id,
        "participant": payload.participant_name,
        "event": payload.event_type,
        "time": res["time"]
    })
    
    return {"status": "success", "data": res, "meeting_id": m_id}

@app.post("/api/attendance/roster")
async def api_load_roster(payload: RosterLoadRequest):
    load_roster_into_meeting(payload.meeting_id, payload.names)
    await manager.broadcast({"type": "ROSTER_UPDATED", "meeting_id": payload.meeting_id})
    return {"status": "success", "count": len(payload.names)}

class CalendarConfigRequest(BaseModel):
    url: str

@app.get("/api/calendar/events")
async def api_get_calendar_events():
    url = get_calendar_url()
    events = fetch_calendar_events()
    return {"configured": bool(url), "events": events}

@app.post("/api/calendar/config")
async def api_config_calendar(payload: CalendarConfigRequest):
    save_calendar_url(payload.url)
    events = fetch_calendar_events()
    return {"status": "success", "count": len(events)}

@app.get("/api/attendance/export/{meeting_id}")
async def api_export_attendance(meeting_id: str):
    file_path = export_attendance_excel(meeting_id)
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.post("/api/upload")
async def api_upload_media(
    title: str = Form(...),
    meet_code: str = Form(""),
    file: UploadFile = File(...)
):
    conn = get_db_connection()
    cur = conn.cursor()
    m_id = None
    
    # Si viene meet_code, asociar a la reunión existente que tomó la asistencia
    if meet_code:
        cur.execute("SELECT id FROM meetings WHERE meet_code = ? ORDER BY created_at DESC LIMIT 1", (meet_code,))
        row = cur.fetchone()
        if row:
            m_id = row["id"]
            
    if not m_id:
        m_id = str(uuid.uuid4())[:8]
        create_meeting(m_id, title, meet_code)
    else:
        with conn:
            conn.execute("UPDATE meetings SET title = ? WHERE id = ?", (title, m_id))
            
    saved_path = UPLOADS_DIR / f"{m_id}_{file.filename}"
    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    with conn:
        conn.execute("UPDATE meetings SET audio_path = ? WHERE id = ?", (f"/uploads/{saved_path.name}", m_id))
    conn.close()
    
    # Transcribir con faster-whisper y generar analíticas
    transcripts = transcribe_audio_file(m_id, saved_path)
    extract_action_items(m_id, transcripts)
    
    return {"status": "success", "meeting_id": m_id}

@app.post("/api/ask")
async def api_ask_read(payload: AskRequest):
    result = ask_read_agent(payload.query, payload.meeting_id)
    return result

# --- WEBSOCKET EN TIEMPO REAL ---
@app.websocket("/ws/attendance/{meeting_id}")
async def websocket_attendance(websocket: WebSocket, meeting_id: str):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
