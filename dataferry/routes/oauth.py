import time

import bcrypt
from authlib.jose import jwt
from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dataferry.config import get_settings
from dataferry.db import get_db
from dataferry.models import Agent
from dataferry.schemas import TokenResponse

router = APIRouter(prefix="/oauth", tags=["oauth"])


@router.post("/token", response_model=TokenResponse)
async def issue_token(
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    if grant_type != "client_credentials":
        raise HTTPException(status_code=400, detail="unsupported_grant_type")

    result = await db.execute(select(Agent).where(Agent.client_id == client_id))
    agent = result.scalar_one_or_none()
    if agent is None or not bcrypt.checkpw(
        client_secret.encode(), agent.client_secret_hash.encode()
    ):
        raise HTTPException(status_code=401, detail="invalid_client")

    settings = get_settings()
    now = int(time.time())
    claims = {
        "sub": agent.client_id,
        "iat": now,
        "exp": now + settings.jwt_access_token_expire_seconds,
    }
    header = {"alg": settings.jwt_algorithm}
    access_token = jwt.encode(header, claims, settings.jwt_secret_key).decode()

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_seconds,
    )
