import re
import requests
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from .db import get_db_connection

def parse_ics_date(dt_str: str) -> Optional[datetime]:
    """Parsea formatos de fecha estándar de iCalendar (UTC o local)."""
    clean_str = dt_str.replace("Z", "")
    for fmt in ["%Y%m%dT%H%M%S", "%Y%m%d"]:
        try:
            return datetime.strptime(clean_str, fmt)
        except Exception:
            continue
    return None

def save_calendar_url(url: str):
    conn = get_db_connection()
    with conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('calendar_url', ?)", (url.strip(),))
    conn.close()

def get_calendar_url() -> Optional[str]:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = 'calendar_url'")
    row = cur.fetchone()
    conn.close()
    return row["value"] if row else None

def parse_ics_content(ics_text: str) -> List[Dict[str, Any]]:
    """Parsea el contenido iCal en una lista estructurada de reuniones."""
    events = []
    # Separar por VEVENT
    raw_events = re.findall(r'BEGIN:VEVENT(.*?)END:VEVENT', ics_text, re.DOTALL)
    now = datetime.now()
    two_weeks = now + timedelta(days=14)

    for raw in raw_events:
        summary_m = re.search(r'SUMMARY:(.*?)(?:\r?\n[A-Z]|\r?\nEND)', raw, re.DOTALL)
        dtstart_m = re.search(r'DTSTART(?:;[^:]+)?:([0-9TZ]+)', raw)
        dtend_m = re.search(r'DTEND(?:;[^:]+)?:([0-9TZ]+)', raw)
        location_m = re.search(r'LOCATION:(.*?)(?:\r?\n[A-Z]|\r?\nEND)', raw, re.DOTALL)
        desc_m = re.search(r'DESCRIPTION:(.*?)(?:\r?\n[A-Z]|\r?\nEND)', raw, re.DOTALL)
        
        # Extraer asistentes (ATTENDEE)
        attendees = []
        attendee_matches = re.findall(r'ATTENDEE.*?(?:CN=([^:;]+))?.*?mailto:([^\r\n;]+)', raw, re.IGNORECASE)
        for cn, email in attendee_matches:
            name = cn.strip(' "\'') if cn else email.split('@')[0].replace('.', ' ').title()
            attendees.append({"name": name, "email": email.strip()})

        title = summary_m.group(1).replace('\r', '').replace('\n', '').strip() if summary_m else "Reunión de Calendario"
        desc = desc_m.group(1) if desc_m else ""
        loc = location_m.group(1) if location_m else ""
        
        # Buscar enlace de Google Meet
        combined_text = f"{loc} {desc} {raw}"
        meet_match = re.search(r'meet\.google\.com/([a-z0-9\-]+)', combined_text, re.IGNORECASE)
        meet_code = meet_match.group(1).lower() if meet_match else ""

        start_dt = parse_ics_date(dtstart_m.group(1)) if dtstart_m else None
        end_dt = parse_ics_date(dtend_m.group(1)) if dtend_m else None

        if start_dt and start_dt >= (now - timedelta(days=1)) and start_dt <= two_weeks:
            events.append({
                "title": title,
                "meet_code": meet_code,
                "start_time": start_dt.strftime("%Y-%m-%d %H:%M"),
                "end_time": end_dt.strftime("%Y-%m-%d %H:%M") if end_dt else "",
                "is_today": start_dt.date() == now.date(),
                "is_tomorrow": start_dt.date() == (now + timedelta(days=1)).date(),
                "attendees": attendees,
                "attendees_count": len(attendees)
            })

    events.sort(key=lambda x: x["start_time"])
    return events

def fetch_calendar_events() -> List[Dict[str, Any]]:
    """Descarga y parsea los eventos del calendario configurado."""
    url = get_calendar_url()
    if not url:
        return []

    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            return parse_ics_content(resp.text)
    except Exception as e:
        print(f"[!] Error sincronizando calendario: {e}")
    return []

def find_calendar_event_for_meet(meet_code: str) -> Optional[Dict[str, Any]]:
    """
    Busca si en el calendario existe una reunión programada para HOY con este código de Meet.
    Retorna el título de la clase/reunión y la lista de asistentes invitados.
    """
    clean_code = meet_code.lower().strip()
    events = fetch_calendar_events()
    for ev in events:
        if ev["meet_code"] and ev["meet_code"].lower() == clean_code:
            if ev["is_today"]:
                return ev
    return None
