from fastapi import APIRouter
from app.models import GeminiApiCallLog
from app.database import SessionLocal

router = APIRouter()

@router.get("/api/debug/gemini-calls")
async def get_gemini_api_calls():
    db = SessionLocal()
    try:
        logs = db.query(GeminiApiCallLog).order_by(GeminiApiCallLog.timestamp.desc()).limit(50).all()
        total = db.query(GeminiApiCallLog).count()
        return {
            "logs": [
                {
                    "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                    "purpose": log.purpose
                }
                for log in logs
            ],
            "total": total
        }
    finally:
        db.close() 