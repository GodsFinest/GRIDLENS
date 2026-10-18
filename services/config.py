import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
DATA_ROOT = PROJECT_ROOT / "data"
DOCUMENTS_DIR = DATA_ROOT / "documents"
COMTRADE_DIR = DATA_ROOT / "comtrade"
INCIDENTS_FILE = DATA_ROOT / "seed" / "incidents.json"
SUBSTATION_FILE = DATA_ROOT / "seed" / "substation_ogs01.json"
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "mock").lower()
LLM_PROVIDER = os.getenv("LLM_PROVIDER", MODEL_PROVIDER).lower()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
