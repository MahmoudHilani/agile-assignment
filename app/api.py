from fastapi import APIRouter, UploadFile, File, Header, HTTPException
import os
import tempfile
import shutil

from app.config import ADMIN_API_KEY
from app.document_service import replace_company_document
from app import config

router = APIRouter()


@router.post("/admin/company-doc")
async def upload_doc(
    file: UploadFile = File(...),
    x_api_key: str = Header(...)
):
    # ✅ AUTH CHECK (correct)
    if x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if file.filename == "":
        raise HTTPException(status_code=400, detail="Empty file")

    ext = file.filename.split(".")[-1].lower()
    if ext not in ["pdf", "docx", "txt"]:
        raise HTTPException(status_code=400, detail="Unsupported format")

    fd, temp_path = tempfile.mkstemp(suffix=f".{ext}")
    os.close(fd)
    
    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        result = replace_company_document(temp_path)
        return {"message": "Document replaced", "version": result["version"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)