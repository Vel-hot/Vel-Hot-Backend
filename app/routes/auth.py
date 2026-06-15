from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import Token, TokenData, create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.logging_config import get_logger
from app.models import Utilisateur
from app.schemas import LoginIn, RegisterIn, UserOut

router = APIRouter()
logger = get_logger(__name__)


@router.post("/register", response_model=UserOut, status_code=201,
             summary="Créer un compte")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """Inscription avec nom, prénom, email et mot de passe."""
    if db.query(Utilisateur).filter(Utilisateur.email == body.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte avec cet email existe déjà",
        )
    user = Utilisateur(
        nom             = body.nom,
        prenom          = body.prenom,
        email           = body.email,
        hashed_password = hash_password(body.password),
        role            = "user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Nouveau compte créé : %s", user.email)
    return user


@router.post("/login", response_model=Token, summary="Obtenir un JWT")
def login(body: LoginIn, db: Session = Depends(get_db)):
    """Connexion avec email + mot de passe. Retourne un JWT Bearer."""
    user = db.query(Utilisateur).filter(Utilisateur.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        logger.warning("Échec de connexion pour : %s", body.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
        )
    token = create_access_token({
        "sub":   str(user.id),
        "email": user.email,
        "role":  user.role,
    })
    logger.info("Connexion réussie : %s", user.email)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserOut, summary="Profil de l'utilisateur connecté")
def get_me(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retourne les infos du compte associé au token JWT fourni."""
    user = db.query(Utilisateur).filter(Utilisateur.id == current_user.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable",
        )
    return user
