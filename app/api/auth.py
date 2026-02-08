from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from app.db.session import get_db
from app.models import models
from app.schemas import schemas
from app.core import security
from app.core.config import settings
from app.api import deps

router = APIRouter()

@router.get("/setup/status")
def check_setup_status(db: Session = Depends(get_db)):
    """
    Checks if the system is already set up (has at least one admin).
    """
    admin = db.query(models.User).filter(models.User.is_active == 1).first()
    return {"is_setup": admin is not None, "wizard_enabled": settings.ENABLE_SETUP_WIZARD}

@router.post("/setup")
def initial_setup(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Initial System Setup: Creates the first admin user.
    Only allows creation if no users exist.
    """
    if not settings.ENABLE_SETUP_WIZARD:
         raise HTTPException(status_code=403, detail="Setup Wizard is disabled.")
         
    existing_user = db.query(models.User).first()
    if existing_user:
        raise HTTPException(
            status_code=403,
            detail="System already set up. Please login.",
        )
        
    db_user = models.User(
        email=user_in.email,
        full_name=user_in.full_name or "System Administrator",
        hashed_password=security.get_password_hash(user_in.password),
        is_active=1
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.post("/register", response_model=schemas.User)
def register_user(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists in the system.",
        )
    db_user = models.User(
        email=user_in.email,
        hashed_password=security.get_password_hash(user_in.password),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.post("/login", response_model=schemas.Token)
def login_access_token(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }

@router.get("/me", response_model=schemas.User)
def read_user_me(current_user: models.User = Depends(deps.get_current_user)):
    return current_user
