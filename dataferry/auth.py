from authlib.jose import JoseError, jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dataferry.config import get_settings
from dataferry.db import get_db
from dataferry.models import Agent

_bearer_scheme = HTTPBearer()


async def get_current_agent(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    settings = get_settings()
    try:
        claims = jwt.decode(credentials.credentials, settings.jwt_secret_key)
        claims.validate()
    except JoseError as exc:
        raise HTTPException(status_code=401, detail="invalid_token") from exc

    result = await db.execute(select(Agent).where(Agent.client_id == claims.get("sub")))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=401, detail="invalid_token")
    return agent
