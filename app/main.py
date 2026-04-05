from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, validation

app = FastAPI(
    title="File Validator API",
    description="Sistem validasi file klien — Price, Inventory, Master Product",
    version="1.0.0",
)

# CORS — izinkan React dev server dan production domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(validation.router)

@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "message": "File Validator API is running"}

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}
