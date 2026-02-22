from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import settings

_api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)


async def require_api_key(header_key: str = Security(_api_key_header)) -> str:
    """
    Gemeinsame Auth-Dependency für alle Endpunkte.

    Wirft 401 wenn der Key fehlt oder falsch ist.
    Da settings.api_factory_key beim Start validiert wird (Pydantic),
    kann hier kein None-Vergleich auftreten.
    """
    if header_key != settings.api_factory_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return header_key
