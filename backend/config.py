import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
REPORTS_DIR = DATA_DIR / "reports"
ROSTERS_DIR = DATA_DIR / "rosters"
DB_PATH = DATA_DIR / "meetings.db"

# Create directories
for directory in [DATA_DIR, UPLOADS_DIR, REPORTS_DIR, ROSTERS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Application Settings
APP_NAME = "ReadAI Local - MeetSense"
HOST = "0.0.0.0"
PORT = 8000
LATE_THRESHOLD_MINUTES = 10  # Minutos de gracia antes de marcar tardanza
WHISPER_MODEL = "base"       # 'tiny', 'base', 'small', 'medium'
WHISPER_DEVICE = "auto"      # 'cuda' o 'cpu' (auto detecta)
WHISPER_COMPUTE_TYPE = "int8"

# LLM Settings (Ollama o API externa opcional)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
