from fastapi import FastAPI
from api.routes import router as api_router

app = FastAPI(
    title="LLM Memory Layer",
    description="A system to provide long-term memory for LLMs",
    version="0.1.0",
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
