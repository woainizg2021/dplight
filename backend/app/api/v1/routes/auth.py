from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from backend.app.core.security import verify_password, create_access_token, MOCK_USERS_DB
from backend.app.models.schemas import Token

router = APIRouter()

@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = MOCK_USERS_DB.get(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Include role and allowed_companies in token
    access_token_expires = timedelta(minutes=60 * 24 * 7)
    access_token = create_access_token(
        data={
            "sub": user["username"],
            "role": user["role"],
            "allowed_companies": user["allowed_companies"],
            "is_superuser": user["is_superuser"]
        },
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
