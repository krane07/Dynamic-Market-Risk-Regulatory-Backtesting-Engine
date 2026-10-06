from fastapi import APIRouter

router = APIRouter(prefix="/risk", tags=["portfolio-risk"])

@router.post("/risk/{measure}")
def risk(measure: Literal["var", "expected-shortfall"], req: RiskRequest):
    value = compute_risk(measure, req)               # your maths
    return {"measure": measure, "value": value,
            "confidence": req.confidence, "horizon_days": req.horizon_days}