from fastapi import FastAPI
from backend.routes import router
from backend.models import Base
from backend.database import engine
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Create DB tables
Base.metadata.create_all(bind=engine)

# Serve uploaded images
app.mount("/data", StaticFiles(directory="data"), name="data")

# Include routes
app.include_router(router)