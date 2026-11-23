import sys
import os
import subprocess
import webbrowser
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

def main():
    print("=" * 60)
    print("        READAI LOCAL - MEETSENSE (SISTEMA INDEPENDIENTE)")
    print("=" * 60)
    print("[*] Verificando e iniciando el servidor local en http://localhost:8000...")
    
    # Importar app y config
    try:
        from backend.config import DB_PATH, DATA_DIR
        from backend.db import init_db
        print(f"[*] Directorio de datos: {DATA_DIR}")
        print(f"[*] Inicializando base de datos local SQLite: {DB_PATH.name}")
        init_db()
    except Exception as e:
        print(f"[!] Error inicializando la base de datos: {e}")
        sys.exit(1)
        
    print("[+] Servidor listo. Abriendo navegador web en http://localhost:8000...")
    
    # Abrir navegador tras un breve retraso
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://localhost:8000")
        
    import threading
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Iniciar servidor Uvicorn
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main()
