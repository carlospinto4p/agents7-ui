from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/run", tags=["run"])


@router.post("/{agent_name}")
async def run_agent(agent_name: str, request: Request) -> dict:
    return {"status": "not_implemented", "agent": agent_name}
