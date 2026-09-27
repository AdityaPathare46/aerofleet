"""Authentication and user management API endpoints."""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
import bcrypt
from jose import JWTError, jwt

from aerofleet.api.rate_limit import limiter
from aerofleet.api.secret_key import resolve_secret_key
from aerofleet.api.schemas import UserCreate, UserResponse, Token
from aerofleet.data.models.models import User
from aerofleet.data.database import get_db_session
from aerofleet.utils.config import get_config
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()
config = get_config()

# Security configuration — see aerofleet/api/secret_key.py: env var, then a non-placeholder config
# value, then a random per-install key. Never a constant from the repository.
SECRET_KEY = resolve_secret_key(getattr(config, "secret_key", None))
ALGORITHM = "HS256"
# Short-lived access tokens, renewed silently with a longer-lived refresh token (POST /auth/refresh),
# so an operator isn't logged out mid-session and a leaked access token expires quickly.
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("AEROFLEET_ACCESS_TOKEN_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("AEROFLEET_REFRESH_TOKEN_DAYS", "14"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def get_or_create_default_demo_user(db: Session) -> User:
    demo = db.query(User).filter(User.username == "operator").first()
    if demo is None:
        demo = User(
            username="operator",
            email="operator@aerofleet.local",
            hashed_password=get_password_hash("operator123"),
            is_active=True,
            is_operator=True,
            is_admin=True,
        )
        db.add(demo)
        db.commit()
        db.refresh(demo)
    return demo

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
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(username: str) -> str:
    """Long-lived token whose only use is POST /auth/refresh — rejected everywhere else."""
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": username, "exp": expire, "type": "refresh", "jti": secrets.token_hex(8)},
                      SECRET_KEY, algorithm=ALGORITHM)


def issue_tokens(username: str) -> dict:
    return {
        "access_token": create_access_token({"sub": username}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)),
        "token_type": "bearer",
        "refresh_token": create_refresh_token(username),
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }

def get_user_from_token(token: str, db: Session) -> Optional[User]:
    """Decode a JWT and look up its user, returning None rather than raising
    on any failure. Shared by the HTTP dependency below and by WebSocket
    routes, which can't use FastAPI's Depends()-based auth before accept()."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        # A refresh token is not a login: it only buys a new access token at /auth/refresh.
        if username is None or payload.get("type") == "refresh":
            return None
    except JWTError:
        return None
    return db.query(User).filter(User.username == username).first()

async def get_current_user(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Real auth, no fallback. A missing or invalid token must be rejected,
    not silently upgraded to a privileged demo account — the previous
    behavior here (falling back to get_or_create_default_demo_user, an
    is_admin=True/is_operator=True account, for *any* unauthenticated or
    unresolvable-token request) meant failed auth granted maximum
    privileges instead of denying access. get_or_create_default_demo_user
    is kept below for a real, explicit demo-login flow to call — it must
    never again be something a client reaches just by omitting a token."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise unauthorized
    user = get_user_from_token(token, db)
    if user is None:
        raise unauthorized
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
    return issue_tokens(user.username)


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=Token)
@limiter.limit("30/minute")
async def refresh_access_token(request: Request, body: RefreshRequest, db: Session = Depends(get_db)):
    """Silent renewal: a valid refresh token buys a fresh access token and a new refresh token
    (rotation). The desktop app calls this before the access token expires, so an operator stays
    signed in for as long as the app is in use, up to REFRESH_TOKEN_EXPIRE_DAYS idle."""
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalid or expired",
                                 headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(body.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise unauthorized
    if payload.get("type") != "refresh" or not payload.get("sub"):
        raise unauthorized
    user = db.query(User).filter(User.username == payload["sub"]).first()
    if user is None or not user.is_active:
        raise unauthorized
    return issue_tokens(user.username)

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user
