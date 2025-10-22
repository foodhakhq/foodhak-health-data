from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import timedelta
from utils.security import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter()

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: str
    device_type: str

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Generate an access token for authentication
    """
    # In a real application, you would validate the user credentials here
    # For this example, we'll accept any username/password
    # You should implement proper user authentication in production
    
    # Create token data
    token_data = {
        "sub": form_data.username,  # Use username as user_id
        "device_type": "API_CLIENT"  # You can customize this based on your needs
    }
    
    # Create access token
    access_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    } 