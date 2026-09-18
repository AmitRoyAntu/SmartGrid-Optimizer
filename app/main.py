from fastapi import FastAPI
from app.core.schemas import OptimizeEnergyRequest, OptimizeEnergyResponse
from app.core.orchestrator import orchestrate

app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post(
    "/optimize-energy",
    response_model=OptimizeEnergyResponse
)
async def optimize_energy(request: OptimizeEnergyRequest):
    return await orchestrate(request)