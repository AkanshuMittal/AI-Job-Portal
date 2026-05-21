from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class InterviewOut(BaseModel):
    id: int
    application_id: int
    chat_history: Optional[List[Any]] = []
    current_question_index: int
    interview_score: Optional[float] = None
    feedback_summary: Optional[str] = None
    candidate_feedback: Optional[str] = None
    is_completed: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChatMessage(BaseModel):
    """Schema for a single message sent from the frontend via WebSocket."""
    text: str  # The candidate's spoken answer (converted from speech to text on frontend)


class WebSocketResponse(BaseModel):
    """Schema for what the backend sends back via WebSocket."""
    type: str          # "question", "completed", "error"
    text: str          # The AI's text response (for avatar/display)
    audio_base64: Optional[str] = None  # Base64-encoded MP3 from ElevenLabs
    question_number: int = 0
    total_questions: int = 0
    is_final: bool = False

