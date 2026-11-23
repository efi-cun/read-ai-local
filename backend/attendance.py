from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from .db import get_db_connection, get_meeting
from .config import REPORTS_DIR, LATE_THRESHOLD_MINUTES

def format_timestamp(dt: Optional[datetime] = None) -> str:
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%H:%M:%S")

def parse_time_str(time_str: str) -> Optional[datetime]:
    try:
        return datetime.strptime(time_str, "%H:%M:%S")
    except Exception:
        return None

def record_participant_event(meeting_id: str, name: str, event_type: str, custom_time: Optional[str] = None) -> Dict[str, Any]:
    """
    Registra el evento de entrada ('JOIN') o salida ('LEAVE') de un participante.
    Calcula automáticamente si es 'Presente' o 'Tardanza' según la hora de inicio de la reunión.
    """
    time_now_str = custom_time or format_timestamp()
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Obtener hora de inicio de reunión
    cur.execute("SELECT created_at FROM meetings WHERE id = ?", (meeting_id,))
    meeting_row = cur.fetchone()
    
    # Determinar si ya está en la lista de la reunión
    cur.execute("SELECT * FROM participants WHERE meeting_id = ? AND LOWER(name) = LOWER(?)", (meeting_id, name.strip()))
    existing = cur.fetchone()
    
    if event_type.upper() in ["JOIN", "PARTICIPANT_JOINED"]:
        status = "Presente"
        if meeting_row and meeting_row["created_at"]:
            try:
                meeting_start = datetime.fromisoformat(meeting_row["created_at"])
                diff_minutes = (datetime.now() - meeting_start).total_seconds() / 60.0
                if diff_minutes > LATE_THRESHOLD_MINUTES:
                    status = "Tardanza"
            except Exception:
                pass

        if not existing:
            with conn:
                cur.execute(
                    """
                    INSERT INTO participants (meeting_id, name, entry_time, exit_time, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (meeting_id, name.strip(), time_now_str, "", status)
                )
        else:
            # Si existía como Ausente o no tenía hora de ingreso, actualizar a Presente/Tardanza
            if existing["status"] == "Ausente" or not existing["entry_time"]:
                with conn:
                    cur.execute(
                        """
                        UPDATE participants 
                        SET entry_time = ?, status = ?
                        WHERE id = ?
                        """,
                        (time_now_str, status, existing["id"])
                    )
    elif event_type.upper() in ["LEAVE", "PARTICIPANT_LEFT"]:
        if existing:
            with conn:
                cur.execute(
                    "UPDATE participants SET exit_time = ? WHERE id = ?",
                    (time_now_str, existing["id"])
                )
    
    conn.close()
    return {"name": name, "event": event_type, "time": time_now_str}

def load_roster_into_meeting(meeting_id: str, roster_names: List[str]):
    """
    Precarga una lista esperada de estudiantes/asistentes.
    Inicialmente todos se colocan en estado 'Ausente' hasta que ingresen.
    """
    conn = get_db_connection()
    with conn:
        for name in roster_names:
            name_clean = name.strip()
            if not name_clean:
                continue
            # Verificar si ya existe
            cur = conn.cursor()
            cur.execute("SELECT id FROM participants WHERE meeting_id = ? AND LOWER(name) = LOWER(?)", (meeting_id, name_clean))
            if not cur.fetchone():
                conn.execute(
                    """
                    INSERT INTO participants (meeting_id, name, entry_time, exit_time, status)
                    VALUES (?, ?, '', '', 'Ausente')
                    """,
                    (meeting_id, name_clean)
                )
    conn.close()

def export_attendance_excel(meeting_id: str) -> Path:
    """
    Genera un informe institucional de asistencia en formato Excel (.xlsx).
    Incluye estadísticas consolidadas, estilos y colores para Presente, Tardanza y Ausente.
    """
    meeting = get_meeting(meeting_id)
    meeting_title = meeting["title"] if meeting else f"Reunión {meeting_id}"
    meeting_code = meeting["meet_code"] if meeting and meeting["meet_code"] else "N/A"
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM participants WHERE meeting_id = ? ORDER BY status ASC, name ASC", (meeting_id,))
    participants = cur.fetchall()
    conn.close()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Control de Asistencia"
    ws.views.sheetView[0].showGridLines = True
    
    # Paleta de Colores
    NAVY_HEADER = "1E3A8A"
    WHITE = "FFFFFF"
    GREEN_FILL = "DCFCE7"
    GREEN_TEXT = "166534"
    YELLOW_FILL = "FEF9C3"
    YELLOW_TEXT = "854D0E"
    RED_FILL = "FEE2E2"
    RED_TEXT = "991B1B"
    GRAY_BORDER = "CBD5E1"
    
    thin_border = Border(
        left=Side(style='thin', color=GRAY_BORDER),
        right=Side(style='thin', color=GRAY_BORDER),
        top=Side(style='thin', color=GRAY_BORDER),
        bottom=Side(style='thin', color=GRAY_BORDER)
    )
    
    # 1. Título y Encabezado del Reporte
    ws.merge_cells("A1:G1")
    ws["A1"] = "REPORTE OFICIAL DE ASISTENCIA - REUNIONES GOOGLE MEET"
    ws["A1"].font = Font(name="Arial", size=15, bold=True, color=WHITE)
    ws["A1"].fill = PatternFill(start_color=NAVY_HEADER, end_color=NAVY_HEADER, fill_type="solid")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 35
    
    # 2. Metadatos
    ws["A3"] = "Reunión / Asignatura:"
    ws["B3"] = meeting_title
    ws["A4"] = "Código Meet:"
    ws["B4"] = meeting_code
    ws["D3"] = "Fecha de Emisión:"
    ws["E3"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    ws["D4"] = "Umbral de Tardanza:"
    ws["E4"] = f"{LATE_THRESHOLD_MINUTES} minutos"
    
    for row in [3, 4]:
        ws[f"A{row}"].font = Font(name="Arial", size=10, bold=True)
        ws[f"D{row}"].font = Font(name="Arial", size=10, bold=True)
        ws[f"B{row}"].font = Font(name="Arial", size=10)
        ws[f"E{row}"].font = Font(name="Arial", size=10)
    
    # 3. Encabezados de Tabla
    headers = ["#", "Nombre y Apellidos", "Hora de Ingreso", "Hora de Salida", "% Participación", "Estado"]
    row_idx = 6
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=row_idx, column=col_idx, value=h)
        cell.font = Font(name="Arial", size=11, bold=True, color=WHITE)
        cell.fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
    ws.row_dimensions[row_idx].height = 25
    
    # 4. Datos de Participantes
    total_presentes = 0
    total_tardanzas = 0
    total_ausentes = 0
    
    for i, p in enumerate(participants, start=1):
        row_idx += 1
        ws.row_dimensions[row_idx].height = 20
        status = p["status"] or "Ausente"
        
        if status == "Presente":
            total_presentes += 1
            status_fill = PatternFill(start_color=GREEN_FILL, end_color=GREEN_FILL, fill_type="solid")
            status_font = Font(name="Arial", size=10, bold=True, color=GREEN_TEXT)
        elif status == "Tardanza":
            total_tardanzas += 1
            status_fill = PatternFill(start_color=YELLOW_FILL, end_color=YELLOW_FILL, fill_type="solid")
            status_font = Font(name="Arial", size=10, bold=True, color=YELLOW_TEXT)
        else:
            total_ausentes += 1
            status_fill = PatternFill(start_color=RED_FILL, end_color=RED_FILL, fill_type="solid")
            status_font = Font(name="Arial", size=10, bold=True, color=RED_TEXT)
            
        cells = [
            (1, i, Alignment(horizontal="center")),
            (2, p["name"], Alignment(horizontal="left")),
            (3, p["entry_time"] or "--:--:--", Alignment(horizontal="center")),
            (4, p["exit_time"] or "--:--:--", Alignment(horizontal="center")),
            (5, f"{p['talk_percentage']:.1f}%", Alignment(horizontal="center")),
            (6, status, Alignment(horizontal="center"))
        ]
        
        for col_i, val, align in cells:
            c = ws.cell(row=row_idx, column=col_i, value=val)
            c.font = Font(name="Arial", size=10)
            c.alignment = align
            c.border = thin_border
            if col_i == 6:
                c.fill = status_fill
                c.font = status_font
    
    # 5. Resumen Estadístico al pie
    row_idx += 2
    ws.cell(row=row_idx, column=2, value="TOTAL ASISTENTES REGISTRADOS:").font = Font(bold=True)
    ws.cell(row=row_idx, column=3, value=len(participants)).font = Font(bold=True)
    
    row_idx += 1
    ws.cell(row=row_idx, column=2, value="Presentes:").font = Font(color=GREEN_TEXT, bold=True)
    ws.cell(row=row_idx, column=3, value=total_presentes).font = Font(color=GREEN_TEXT, bold=True)
    
    row_idx += 1
    ws.cell(row=row_idx, column=2, value="Tardanzas:").font = Font(color=YELLOW_TEXT, bold=True)
    ws.cell(row=row_idx, column=3, value=total_tardanzas).font = Font(color=YELLOW_TEXT, bold=True)
    
    row_idx += 1
    ws.cell(row=row_idx, column=2, value="Ausentes:").font = Font(color=RED_TEXT, bold=True)
    ws.cell(row=row_idx, column=3, value=total_ausentes).font = Font(color=RED_TEXT, bold=True)
    
    # Autoajustar anchos de columnas
    col_widths = {1: 8, 2: 34, 3: 18, 4: 18, 5: 18, 6: 18}
    for col_idx, width in col_widths.items():
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = width
        
    filename = f"asistencia_{meeting_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = REPORTS_DIR / filename
    wb.save(str(filepath))
    return filepath
