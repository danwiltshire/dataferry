from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dataferry.routes import admin, agent, oauth

app = FastAPI()
# admin/* already has no auth of its own (see ARCH_V2.md), so an open CORS
# policy doesn't weaken anything; it lets the frontend call this API directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(admin.router)
app.include_router(agent.router)
app.include_router(oauth.router)


@app.get("/")
def read_root():
    return {"status": "ok"}