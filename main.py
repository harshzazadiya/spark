from fastapi import FastAPI
from database import Base
from database import engine
from routers import auth, user, admin, gate
from fastapi.staticfiles import StaticFiles

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.mount("/qr_codes", StaticFiles(directory="qr_codes"), name="qr_codes")

@app.get("/healthy")
def health_check():
    return {'status': 'Healthy'}

# Include routers
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(admin.router)
app.include_router(gate.router)