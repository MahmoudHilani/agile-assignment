import os
import shutil
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import fitz
from docx import Document

from app.vector_store import store
from app import config

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def parse(file_path):
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        elif ext == ".pdf":
            text = ""
            with fitz.open(file_path) as doc:
                for page in doc:
                    text += page.get_text()
        elif ext == ".docx":
            doc = Document(file_path)
            text = "\n".join(p.text for p in doc.paragraphs)
        else:
            raise ValueError("Unsupported format")
            
        if not text.strip():
            raise ValueError("Empty document")
            
        return text
    except ValueError:
        raise
    except Exception as e:
        raise ValueError("Invalid document") from e


def chunk(text, size=500, overlap=100):
    if overlap >= size:
        raise ValueError("Overlap must be strictly less than size")

    words = text.split()
    chunks = []

    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i:i + size]))
        i += size - overlap

    return chunks


def embed(chunks):
    res = client.embeddings.create(
        model="text-embedding-3-small",
        input=chunks  # ✅ batch
    )
    return [item.embedding for item in res.data]


def process_document(file_path, version, use_mock=False):
    text = parse(file_path)

    if not text.strip():
        raise ValueError("Empty document")

    chunks = chunk(text)
    if use_mock:
        embeddings = [[0.1] * 1536 for _ in chunks]
    else:
        embeddings = embed(chunks)

    store(chunks, embeddings, version, replace=True)


def initialize_company_document(use_mock=False):
    canonical_path = config.get_canonical_company_document_path()
    if canonical_path.exists():
        process_document(canonical_path, config.CANONICAL_DOC_VERSION, use_mock=use_mock)
        config.ACTIVE_DOC_VERSION = config.CANONICAL_DOC_VERSION
        return canonical_path
    return None


def replace_company_document(file_path, use_mock=False):
    # Process, index, and update vector store first. If it fails, the canonical file remains safe.
    process_document(file_path, config.CANONICAL_DOC_VERSION, use_mock=use_mock)
    
    canonical_path = config.get_canonical_company_document_path()
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    
    shutil.copy(str(file_path), canonical_path)
    
    config.ACTIVE_DOC_VERSION = config.CANONICAL_DOC_VERSION
    
    return {"version": config.CANONICAL_DOC_VERSION}