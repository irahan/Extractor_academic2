import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class Config:
    BASE_DIR = Path(__file__).resolve().parent
    SECRET_KEY = os.getenv('SECRET_KEY', 'clave-por-defecto-insegura')
    
    # Configuración de subida de archivos
    UPLOAD_FOLDER = BASE_DIR / 'uploads'
    OUTPUT_FOLDER = BASE_DIR / 'outputs'
    LOGS_FOLDER = BASE_DIR / 'logs'
    JOBS_FOLDER = BASE_DIR / 'jobs'
    
    # Asegurar que las carpetas existan
    UPLOAD_FOLDER.mkdir(exist_ok=True)
    OUTPUT_FOLDER.mkdir(exist_ok=True)
    LOGS_FOLDER.mkdir(exist_ok=True)
    JOBS_FOLDER.mkdir(exist_ok=True)
    
    # 50 MB por defecto
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 50 * 1024 * 1024))
    
    ALLOWED_EXTENSIONS = {'pdf', 'docx'}
    
    # Configuración de IA
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_API_BASE = os.getenv('OPENAI_API_BASE')
    OPENAI_MODEL_NAME = os.getenv('OPENAI_MODEL_NAME', 'gpt-3.5-turbo-0125')
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    LOCAL_LLM_URL = os.getenv('LOCAL_LLM_URL', 'http://localhost:11434/api/generate')
    LOCAL_LLM_MODEL = os.getenv('LOCAL_LLM_MODEL', 'llama3')
