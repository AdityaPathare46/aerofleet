"""Authentication and user management API endpoints."""

import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import bcrypt
from jose import JWTError, jwt

from aerofleet.api.rate_limit import limiter
from aerofleet.api.schemas import UserCreate, UserResponse, Token
from aerofleet.data.models.models import User
from aerofleet.data.database import get_db_session
from aerofleet.utils.config import get_config
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()
config = get_config()

# Security configuration
SECRET_KEY = getattr(config.api, "secret_key", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_db():
    with get_db_session() as db:
        yield db

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_user_from_token(token: str, db: Session) -> Optional[User]:
    """Decode a JWT and look up its user, returning None rather than raising
    on any failure. Shared by the HTTP dependency below and by WebSocket
    routes, which can't use FastAPI's Depends()-based auth before accept()."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
    return db.query(User).filter(User.username == username).first()

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user = get_user_from_token(token, db)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def get_current_operator_user(current_user: User = Depends(get_current_active_user)):
    """Gate for endpoints that command real hardware (arm/disarm/emergency-
    stop). Deliberately narrower than get_current_active_user — being able
    to log in shouldn't be enough to fly a real drone. Granted via the
    admin panel (aerofleet/api/routes/admin.py, Phase AI)."""
    if not current_user.is_operator:
        raise HTTPException(status_code=403, detail="This action requires an operator account")
    return current_user

async def get_current_admin_user(current_user: User = Depends(get_current_active_user)):
    """Gate for the admin panel itself (listing users, granting/revoking
    is_operator/is_admin on other accounts)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="This action requires an admin account")
    return current_user

def ensure_bootstrap_admin(db: Session) -> None:
    """Called once from app.py's startup event. AEROFLEET_BOOTSTRAP_ADMIN_USERNAME
    is the one deliberate exception to "no raw SQL for granting privileges" —
    every admin system needs *some* way to mint the very first admin, and an
    env var set by whoever controls the deployment is the standard, safe way
    to do it (as opposed to, say, an unauthenticated "make me admin" endpoint,
    which would be a real vulnerability). Idempotent — safe to run on every
    startup; does nothing if the var is unset or the named user doesn't exist
    yet (e.g. before they've registered)."""
    username = os.environ.get("AEROFLEET_BOOTSTRAP_ADMIN_USERNAME")
    if not username:
        return
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        logger.warning(
            f"AEROFLEET_BOOTSTRAP_ADMIN_USERNAME='{username}' does not match any registered "
            "user yet — register that account, then restart the API to grant it admin."
        )
        return
    if not user.is_admin:
        user.is_admin = True
        db.commit()
        logger.info(f"Bootstrap admin granted to '{username}'")

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register_user(request: Request, user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter((User.username == user.username) | (User.email == user.email)).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username or email already registered")
    
    hashed_password = get_password_hash(user.password)
    new_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info(f"New user registered: {new_user.username}")
    return new_user

@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
async def login_for_access_token(
    request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user
