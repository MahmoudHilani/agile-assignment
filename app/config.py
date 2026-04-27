import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

COMPANY_DOC_DIR = Path("data/company_docs")
CANONICAL_COMPANY_DOC_DIR = COMPANY_DOC_DIR / "current"
CANONICAL_DOC_VERSION = "current"
ACTIVE_DOC_VERSION = None

def get_canonical_company_document_path() -> Path:
    return CANONICAL_COMPANY_DOC_DIR / "company_document.txt"

# optional debug (remove later)
print("DEBUG ADMIN KEY:", ADMIN_API_KEY)