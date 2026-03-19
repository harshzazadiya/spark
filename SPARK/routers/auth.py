import os
from datetime import timedelta, datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette import status
from jose import jwt, JWTError
from passlib.context import CryptContext
from database import SessionLocal
from model import User, Wallet
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(
    prefix='/auth',
    tags=['auth']
)

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Security
bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
oauth2_bearer = OAuth2PasswordBearer(tokenUrl='/auth/token')


# Pydantic Models
class Token(BaseModel):
    access_token : str
    token_type : str


class CreateUserRequest(BaseModel):
    username : str
    email : str
    password : str
    phone_number : str


# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]


# Helper functions
def authenticate_user(username: str, password: str, db: db_dependency):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not bcrypt_context.verify(password, user.password_hash):
        return None
    return user


def create_access_token(user_id: int, username: str, role: str):
    payload = {
        'id' : user_id,
        'sub' : username,
        'role' : role,
        'exp' : datetime.now(timezone.utc) + timedelta(minutes = ACCESS_TOKEN_EXPIRE_MINUTES)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm = ALGORITHM)


async def get_current_user(token: Annotated[str, Depends(oauth2_bearer)], db: db_dependency):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms = [ALGORITHM])
        user_id = payload.get('id')
        username = payload.get('sub')
        
        if user_id is None or username is None:
            raise HTTPException(status_code = 401, detail = "Invalid token")
        
        user = db.query(User).filter(User.id == user_id).first()
        if user is None or not user.is_active:
            raise HTTPException(status_code = 401, detail = "User not found or inactive")
        
        return user
        
    except JWTError:
        raise HTTPException(status_code = 401, detail = "Invalid token")


# Endpoints
@router.post("/user", status_code=status.HTTP_201_CREATED)
async def create_user(create_user_request: CreateUserRequest, db: db_dependency):
    existing_user = db.query(User).filter(User.username == create_user_request.username).first()
    
    if existing_user:
        raise HTTPException(status_code = status.HTTP_400_BAD_REQUEST, detail="Username or email already registered")
    
    user = User(
        username = create_user_request.username,
        email = create_user_request.email,
        password_hash = bcrypt_context.hash(create_user_request.password),
        phone = create_user_request.phone_number,
        role = "user"
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    user_wallet = Wallet(
        user_id = user.id,
        balance = 0.0
    )

    db.add(user_wallet)
    db.commit()
    db.refresh(user_wallet)
    
    return {
        "id" : user.id, 
        "username" : user.username, 
        "email" : user.email, 
        "role" : user.role,
        "wallet_id" : user_wallet.id
        }

@router.post("/admin", status_code=status.HTTP_201_CREATED)
async def create_admin(create_user_request: CreateUserRequest, db: db_dependency):
    existing_user = db.query(User).filter(User.username == create_user_request.username).first()
    if existing_user:
        raise HTTPException(status_code = status.HTTP_400_BAD_REQUEST, detail="Username or email already registered")

    user = User(
        username = create_user_request.username,
        email = create_user_request.email,
        password_hash = bcrypt_context.hash(create_user_request.password),
        phone = create_user_request.phone_number,
        role = "admin"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    user_wallet = Wallet(
        user_id = user.id,
        balance = 0.0,
        role = "admin"
    )

    db.add(user_wallet)
    db.commit()
    db.refresh(user_wallet)

    return {
        "id" : user.id, 
        "username" : user.username, 
        "email" : user.email, 
        "role" : user.role,
        "wallet_id" : user_wallet.id
        }

@router.post("/token", response_model = Token)
async def login_for_access_token(form_data : Annotated[OAuth2PasswordRequestForm, Depends()], db : db_dependency):
    user = authenticate_user(form_data.username, form_data.password, db)
    
    if not user:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED, 
            detail = "Incorrect username or password",
            headers = {"WWW-Authenticate": "Bearer"}
        )
    
    token = create_access_token(user.id, user.username, user.role)
    
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    return {
        "id" : current_user.id,
        "username" : current_user.username,
        "email" : current_user.email,
        "phone_number" : current_user.phone,
        "created_at" : current_user.created_at,
        "role" : current_user.role
    }