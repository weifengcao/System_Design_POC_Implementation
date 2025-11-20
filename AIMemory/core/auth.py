from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from .config import get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    settings = get_settings()
    if not settings.AIMEMORY_API_KEY:
        # If no key is configured, we might allow open access or fail secure.
        # For Zero Trust, we should fail secure, but for ease of setup, let's warn or require it.
        # Let's require it.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: AIMEMORY_API_KEY not set"
        )
        
    if api_key_header == settings.AIMEMORY_API_KEY:
        return api_key_header
        
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Could not validate credentials"
    )
