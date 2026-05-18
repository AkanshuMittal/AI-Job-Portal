# ─────────────────────────────────────────────────────────
# api/interview.py — AI Interview WebSocket Endpoint
# ─────────────────────────────────────────────────────────
# PURPOSE:
#   Handles the real-time AI interview session via WebSocket.
#   WebSocket allows two-way real-time communication between
#   the browser and the backend — no page refresh needed.
#
# FLOW:
#   1. Seeker hits POST /interview/start/{application_id}
#      → Creates interview record in DB
#   2. Frontend connects to WS /interview/ws/{interview_id}
#      → AI greets candidate and asks first question
#      → ElevenLabs TTS converts text to audio
#      → Sends back {text, audio_base64} to frontend
#   3. Candidate speaks → Web Speech API → text sent to WS
#      → AI evaluates, scores, asks next question
#      → Repeat until TOTAL_QUESTIONS reached
#   4. Interview ends → Score saved → HR can view results
# ─────────────────────────────────────────────────────────

import base64
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.database import get_db
from api.deps import get_current_seeker
from models.user import User
from models.job import Job
from models.application import Application
from models.interview import Interview
from models.seeker_profile import SeekerProfile
from schemas.interview import InterviewOut
from services.interview_service import (
    generate_ai_response,
    score_answer,
    generate_final_feedback,
    text_to_speech,
    TOTAL_QUESTIONS
)

router = APIRouter(prefix="/interview", tags=["AI Interview"])
logger = logging.getLogger(__name__)


# ── 1. Start Interview ────────────────────────────────────
@router.post("/start/{application_id}", response_model=InterviewOut, status_code=status.HTTP_201_CREATED)
async def start_interview(
    application_id: int,
    db: AsyncSession = Depends(get_db),
    seeker: User = Depends(get_current_seeker)
):
    """
    Creates a new AI Interview session for a specific job application.
    The seeker must have applied to the job before starting an interview.
    """
    # Verify the application exists and belongs to this seeker
    seeker_profile_result = await db.execute(
        select(SeekerProfile).where(SeekerProfile.user_id == seeker.id)
    )
    seeker_profile = seeker_profile_result.scalar_one_or_none()
    if not seeker_profile:
        raise HTTPException(status_code=400, detail="Create your profile before starting an interview.")

    app_result = await db.execute(
        select(Application).where(
            Application.id == application_id,
            Application.seeker_id == seeker_profile.id
        )
    )
    application = app_result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found or not authorized.")

    # Check if an interview already exists for this application
    existing = await db.execute(
        select(Interview).where(Interview.application_id == application_id)
    )
    existing_interview = existing.scalar_one_or_none()
    if existing_interview:
        return existing_interview  # Return existing one

    # Create a new interview session
    interview = Interview(
        application_id=application_id,
        chat_history=[],
        current_question_index=0,
        is_completed="scheduled"
    )
    db.add(interview)
    await db.commit()
    await db.refresh(interview)
    return interview


# ── 2. Get Interview Details ──────────────────────────────
@router.get("/{interview_id}", response_model=InterviewOut)
async def get_interview(
    interview_id: int,
    db: AsyncSession = Depends(get_db),
    seeker: User = Depends(get_current_seeker)
):
    """Get the current state of an interview session."""
    result = await db.execute(select(Interview).where(Interview.id == interview_id))
    interview = result.scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found.")
    return interview


# ── 3. WebSocket Interview Session ───────────────────────
@router.websocket("/ws/{interview_id}")
async def interview_websocket(
    websocket: WebSocket,
    interview_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    The core real-time interview loop via WebSocket.

    PROTOCOL:
    - Client connects → server sends first AI question + audio
    - Client sends: {"text": "candidate's spoken answer"}
    - Server sends: {"type": "question", "text": "...", "audio_base64": "...", "question_number": N, "total_questions": N, "is_final": false}
    - On completion: {"type": "completed", "text": "closing", "is_final": true}
    """
    await websocket.accept()
    print(f"DEBUG: WebSocket ACCEPTED for interview {interview_id}")
    logger.info(f"WebSocket connected for interview {interview_id}")

    # Load interview from DB
    print("DEBUG: Loading interview from DB...")
    result = await db.execute(
        select(Interview).options(
            selectinload(Interview.application)
        ).where(Interview.id == interview_id)
    )
    interview = result.scalar_one_or_none()
    print(f"DEBUG: Interview loaded: {interview}")

    if not interview:
        await websocket.send_json({"type": "error", "text": "Interview not found."})
        await websocket.close()
        return

    # Load job details for context
    app_result = await db.execute(
        select(Application).options(
            selectinload(Application.job)
        ).where(Application.id == interview.application_id)
    )
    application = app_result.scalar_one_or_none()
    job = application.job if application else None

    if not job:
        await websocket.send_json({"type": "error", "text": "Job details not found."})
        await websocket.close()
        return

    seeker_result = await db.execute(
        select(SeekerProfile).where(SeekerProfile.id == application.seeker_id)
    )
    seeker_profile = seeker_result.scalar_one_or_none()
    candidate_skills = ", ".join(seeker_profile.skills or []) if seeker_profile else "Not specified"
    resume_data = seeker_profile.parsed_data if seeker_profile else {}

    # Mark interview as in_progress
    interview.is_completed = "in_progress"
    interview.started_at = datetime.now(timezone.utc)
    await db.commit()

    # Restore existing chat history
    chat_history = list(interview.chat_history or [])

    try:
        # ── GREETING (First Connection) ───────────────────
        if not chat_history:
            print("DEBUG: No chat history found, generating initial greeting...")
            # Generate opening greeting + first question
            greeting = await generate_ai_response(
                chat_history=[],
                job_title=job.title,
                job_description=job.description or "",
                candidate_skills=candidate_skills,
                resume_data=resume_data
            )
            print(f"DEBUG: Greeting generated: {greeting[:50]}...")
            chat_history.append({"role": "assistant", "content": greeting})

            # Get TTS audio
            print("DEBUG: Calling text_to_speech (edge-tts)...")
            audio_bytes = await text_to_speech(greeting)
            audio_b64 = base64.b64encode(audio_bytes).decode() if audio_bytes else None
            print("DEBUG: TTS audio generation complete.")

            # Send greeting to frontend
            await websocket.send_json({
                "type": "question",
                "text": greeting,
                "audio_base64": audio_b64,
                "question_number": 1,
                "total_questions": TOTAL_QUESTIONS,
                "is_final": False
            })

            # Save to DB
            interview.chat_history = chat_history
            interview.current_question_index = 1
            await db.commit()
        else:
            # ── RECONNECT (Resume Interview) ──────────────────
            print("DEBUG: Chat history exists, resuming interview...", flush=True)
            last_ai_msg = next((m["content"] for m in reversed(chat_history) if m["role"] == "assistant"), "Welcome back.")
            current_q_num = interview.current_question_index or 1
            
            # Send the last message to the frontend so it knows we are connected
            await websocket.send_json({
                "type": "question",
                "text": last_ai_msg,
                "audio_base64": None, # Skip audio on reconnect to save time/API calls
                "question_number": current_q_num,
                "total_questions": 0, # Unused, timer used instead
                "is_final": False
            })

        # Track maximum proctor violations during the entire session
        max_tab_switches = 0
        max_look_aways = 0

        # ── MAIN INTERVIEW LOOP ───────────────────────────
        while True:
            # Wait for candidate's answer
            data = await websocket.receive_text()
            message = json.loads(data)
            candidate_answer = message.get("text", "").strip()
            
            # Retrieve latest proctor violation counts from frontend
            tab_switches = message.get("tab_switches", 0)
            look_aways = message.get("look_aways", 0)
            max_tab_switches = max(max_tab_switches, tab_switches)
            max_look_aways = max(max_look_aways, look_aways)

            if not candidate_answer:
                continue

            # Save candidate's answer to history
            chat_history.append({"role": "user", "content": candidate_answer})

            current_q_num = interview.current_question_index

            # Score this answer in background
            last_ai_msg = next(
                (m["content"] for m in reversed(chat_history) if m["role"] == "assistant"),
                ""
            )
            score_result = await score_answer(last_ai_msg, candidate_answer, job.title)

            # Check if interview is complete (15 minute timer)
            elapsed = datetime.now(timezone.utc) - interview.started_at
            time_is_up = elapsed.total_seconds() >= 15 * 60

            if time_is_up:
                # Generate closing statement
                closing = await generate_ai_response(
                    chat_history=chat_history,
                    job_title=job.title,
                    job_description=job.description or "",
                    candidate_skills=candidate_skills,
                    resume_data=resume_data,
                    time_is_up=True
                )
                chat_history.append({"role": "assistant", "content": closing})

                # Calculate final average score
                scores = [
                    m.get("score", 5)
                    for m in chat_history
                    if isinstance(m, dict) and "score" in m
                ]
                final_score = sum(scores) / len(scores) if scores else score_result["score"]

                # Generate HR feedback summary
                feedback = await generate_final_feedback(chat_history, job.title, final_score)

                # Append Proctoring compliance report directly into the HR feedback
                proctor_summary = f"\n\n---\n🛡️ **AI Proctoring & Compliance Report:**\n"
                proctor_summary += f"* Window Focus Loss / Tab Switches: **{max_tab_switches}** violations\n"
                proctor_summary += f"* Head Rotation / Looking Away: **{max_look_aways}** flags\n"
                
                integrity_score = max(100 - (max_tab_switches * 15) - (max_look_aways * 4), 0)
                proctor_summary += f"* Overall Compliance Rating: **{integrity_score}%** ("
                if integrity_score >= 85:
                    proctor_summary += "🟢 Fully Compliant)\n"
                elif integrity_score >= 50:
                    proctor_summary += "🟡 Suspicious Activity Detected)\n"
                else:
                    proctor_summary += "🔴 HIGH CHEATING RISK)\n"
                
                feedback += proctor_summary

                # Get TTS for closing
                audio_bytes = await text_to_speech(closing)
                audio_b64 = base64.b64encode(audio_bytes).decode() if audio_bytes else None

                # Update interview as completed
                interview.chat_history = chat_history
                interview.interview_score = final_score
                interview.feedback_summary = feedback
                interview.is_completed = "completed"
                interview.completed_at = datetime.now(timezone.utc)
                await db.commit()

                # Send final message
                await websocket.send_json({
                    "type": "completed",
                    "text": closing,
                    "audio_base64": audio_b64,
                    "question_number": current_q_num,
                    "total_questions": 0,
                    "is_final": True,
                    "score": final_score
                })
                break

            # Generate next question
            ai_response = await generate_ai_response(
                chat_history=chat_history,
                job_title=job.title,
                job_description=job.description or "",
                candidate_skills=candidate_skills,
                resume_data=resume_data,
                time_is_up=False
            )
            # Check if it's the error fallback message
            is_error = ai_response == "I apologize, I'm having a technical issue. Could you please repeat your answer?"

            if not is_error:
                chat_history.append({"role": "assistant", "content": ai_response})
                # Save progress to DB
                interview.chat_history = chat_history
                interview.current_question_index = current_q_num + 1
                await db.commit()
            else:
                # Discard the candidate's latest answer from the temporary chat history so they can retry it
                if chat_history and chat_history[-1]["role"] == "user":
                    chat_history.pop()

            # Get TTS audio
            audio_bytes = await text_to_speech(ai_response)
            audio_b64 = base64.b64encode(audio_bytes).decode() if audio_bytes else None

            # Send next question (or retry prompt) to frontend
            await websocket.send_json({
                "type": "question",
                "text": ai_response,
                "audio_base64": audio_b64,
                "question_number": current_q_num if is_error else current_q_num + 1,
                "total_questions": TOTAL_QUESTIONS,
                "is_final": False
            })

    except WebSocketDisconnect:
        logger.info(f"Interview {interview_id} WebSocket disconnected.")
        # Save current progress on disconnect
        interview.chat_history = chat_history
        await db.commit()

    except Exception as e:
        print(f"DEBUG EXCEPTION: Interview WebSocket error: {e}")
        logger.error(f"Interview WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "text": "An error occurred. Please try again."})
        except Exception:
            pass
