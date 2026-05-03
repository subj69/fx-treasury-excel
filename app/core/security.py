from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.core.config import get_settings

security = HTTPBasic()
settings = get_settings()

def verify_treasury_credentials(
    credentials: HTTPBasicCredentials = Depends(security)
):
    """Проверка логина/пароля для доступа к панели казначея"""
    correct_username = credentials.username == settings.TREASURY_USERNAME
    correct_password = credentials.password == settings.TREASURY_PASSWORD
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверные учётные данные",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username