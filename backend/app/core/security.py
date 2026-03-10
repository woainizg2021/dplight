from datetime import datetime, timedelta
from typing import Optional, Union, Any, List
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from backend.app.core.config import settings
from backend.app.models.schemas import TokenData, User, UserInDB

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

# Mock User Database (to be replaced with MySQL later)
# Passwords are: "password" + "." or "," as specified
# ug888, -> $2b$12$EixZaYVK1fsbw1ZfbX3OXePaWrn96pzkZePnEJVcLz18zOW1SR513 (hash of 'ug888,')
# For now I will use a simple hash function or plain text check if I can't import bcrypt easily in this env, 
# but pwd_context is already set up.
# boss888 -> shareholder -> all 5 -> is_superuser=true
# ug888, -> manager -> UGANDA
# ng999. -> manager -> NIGERIA
# ky888,. -> manager -> KENYA, KENYA_AUDIO
# demo888, -> viewer -> UGANDA

MOCK_USERS_DB = {
    "boss888": {
        "username": "boss888",
        "hashed_password": pwd_context.hash("yangjgsj123,."), # Using standard password from prompt
        "role": "shareholder",
        "allowed_companies": ["UGANDA", "NIGERIA", "KENYA", "KENYA_AUDIO", "DRC"],
        "is_superuser": True
    },
    "ug888,": {
        "username": "ug888,",
        "hashed_password": pwd_context.hash("yangjgsj123,."),
        "role": "manager",
        "allowed_companies": ["UGANDA"],
        "is_superuser": False
    },
    "ng999.": {
        "username": "ng999.",
        "hashed_password": pwd_context.hash("yangjgsj123,."),
        "role": "manager",
        "allowed_companies": ["NIGERIA"],
        "is_superuser": False
    },
    "ky888,.": {
        "username": "ky888,.",
        "hashed_password": pwd_context.hash("yangjgsj123,."),
        "role": "manager",
        "allowed_companies": ["KENYA", "KENYA_AUDIO"],
        "is_superuser": False
    },
    "demo888,": {
        "username": "demo888,",
        "hashed_password": pwd_context.hash("yangjgsj123,."),
        "role": "viewer",
        "allowed_companies": ["UGANDA"],
        "is_superuser": False
    }
}

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        
        # In a real app, we would fetch from DB here using username
        # For now, we use the token payload if it contains the user data, 
        # OR we fetch from our mock DB. 
        # To be safe and support dynamic updates, let's fetch from Mock DB
        user_dict = MOCK_USERS_DB.get(username)
        if user_dict is None:
             raise credentials_exception
             
        token_data = TokenData(
            username=username,
            role=user_dict["role"],
            allowed_companies=user_dict["allowed_companies"],
            is_superuser=user_dict["is_superuser"]
        )
    except JWTError:
        raise credentials_exception
        
    return User(**user_dict)

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user

def check_company_permission(user: User, company_key: str):
    if user.is_superuser:
        return True
    if company_key not in user.allowed_companies:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=f"Not authorized to access data for {company_key}"
        )
    return True
