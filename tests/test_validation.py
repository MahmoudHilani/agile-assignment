import pytest
from app.document_service import parse


def test_invalid_file():
    with pytest.raises(ValueError, match="Unsupported format"):
        parse("invalid.exe")
