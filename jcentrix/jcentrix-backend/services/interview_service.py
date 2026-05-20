# ─────────────────────────────────────────────────────────
# services/interview_service.py — AI Interview Logic
# ─────────────────────────────────────────────────────────
# PURPOSE:
#   Handles ALL AI logic for the interview:
#   1. Generate questions using Groq (Llama 3)
#   2. Evaluate candidate answers and score them
#   3. Generate final feedback summary
#   4. Convert AI text response to audio via ElevenLabs TTS
# ─────────────────────────────────────────────────────────

import httpx
import json
import logging
import io
import os
import asyncio
import soundfile as sf
from typing import Optional
from groq import AsyncGroq
from kokoro_onnx import Kokoro

from core.config import settings

logger = logging.getLogger(__name__)

# ── Initialize Groq Client ────────────────────────────────
groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)

# ── Interview Configuration ───────────────────────────────
TOTAL_QUESTIONS = 7
MODEL = "llama-3.3-70b-versatile"  # Best free Groq model


# ── System Prompt ─────────────────────────────────────────
def build_system_prompt(job_title: str, job_description: str, candidate_skills: str, resume_data: dict) -> str:
    """
    Builds the AI interviewer's persona and instructions.
    Tailors the conversation dynamically based on resume text and adaptive responses.
    """
    extracted_text = ""
    if isinstance(resume_data, dict):
        extracted_text = resume_data.get("extracted_text", "")
        if not extracted_text:
            # Fallback to general JSON dump if not standard format
            extracted_text = json.dumps(resume_data, indent=1)
    
    # Cap the resume text length to 4000 characters to keep context clean and tight
    resume_block = extracted_text[:4000].strip() if extracted_text else "Not provided"

    return f"""You are Aria, an exceptionally warm, encouraging, and sharp human technical recruiter at Jcentrix.
You are interviewing a candidate for the position of: {job_title}.

Job Description context:
{job_description}

Candidate's Declared Skills: {candidate_skills}

Candidate's Extracted Resume Text:
=========================================
{resume_block}
=========================================

CRITICAL RULES FOR ADAPTIVE CONVERSATION:
1. GREETING & FIRST QUESTION: If this is the very first message of the interview, you MUST greet the candidate warmly (using their name if found in the resume) and ask them to introduce themselves. (e.g., "Hello [Name]! Welcome to your interview for the {job_title} role. To start us off, could you tell me a little bit about yourself and your background?"). Do NOT ask specific technical or resume questions in the first message.
2. TRUE DYNAMIC FOLLOW-UPS: For all subsequent turns, you must listen closely to the candidate's previous answer and base your next question directly on what they just said.
   - If they explain a concept, drill down: e.g., "That's a solid explanation. Can you give me an example of how you implemented that in your project [Project Name]?"
   - If their answer is very short or brief, politely ask them to expand: e.g., "Interesting. Could you elaborate on how you handled the scalability aspect in that scenario?"
   - Never just dump a generic pre-written list of questions. Keep it a back-and-forth dialogue!
3. RESUME INTELLIGENCE: After the initial introduction, you MUST dive into their resume! Directly ask about specific details in their resume block! If they list a technology, ask how they used it in the specific work experience or projects listed on their resume.
4. CONCISE & PROFESSIONAL: Ask exactly ONE question at a time. Keep your spoken responses concise and conversational (max 3 sentences total).
5. TONE: Be warm, encouraging, and conversational. Do not sound like a rigid robot.
6. EVALUATION & CORRECTION: Do not say things like "Score 8/10." However, if the candidate gives an explicitly incorrect or partially incorrect technical answer, politely and briefly explain the correct answer to them before moving on to the next question. (e.g., "Actually, React uses a Virtual DOM instead of directly manipulating the real DOM. But moving on...")
"""


# ── Generate AI Response ──────────────────────────────────
async def generate_ai_response(
    chat_history: list,
    job_title: str,
    job_description: str,
    candidate_skills: str,
    resume_data: dict = None,
    time_is_up: bool = False,
    user_wants_to_stop: bool = False
) -> str:
    """
    Sends the full conversation history to Groq and gets the next AI message.

    Args:
        chat_history: List of {"role": "user"/"assistant", "content": "..."} dicts
        job_title: The job being interviewed for
        job_description: Full job description text
        candidate_skills: Candidate's listed skills

    Returns:
        AI's next response text
    """
    try:
        system_prompt = build_system_prompt(job_title, job_description, candidate_skills, resume_data or {})
        
        if time_is_up:
            system_prompt += "\n\nCRITICAL INSTRUCTION: The 15-minute interview limit has been reached! You MUST immediately thank the candidate for their time, conclude the interview gracefully, and DO NOT ask any more questions."
        elif user_wants_to_stop:
            system_prompt += "\n\nCRITICAL INSTRUCTION: The candidate has explicitly requested to stop/end the interview! You MUST immediately acknowledge their request to stop, thank them for their time, conclude the interview gracefully, and DO NOT ask any more questions."

        # Clean chat history to prevent sending extra properties (like score, feedback, ideal_answer) to Groq.
        # Groq strict API raises BadRequestError if unrecognized fields exist in messages.
        cleaned_history = []
        for msg in chat_history:
            if isinstance(msg, dict):
                cleaned_history.append({
                    "role": msg.get("role"),
                    "content": msg.get("content")
                })

        messages = [{"role": "system", "content": system_prompt}] + cleaned_history
        response = await groq_client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=300,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"DEBUG: Groq API Error inside service: {e}", flush=True)
        import traceback
        traceback.print_exc()
        logger.error(f"Groq API error: {e}")
        return "I apologize, I'm having a technical issue. Could you please repeat your answer?"


# ── Score a Single Answer ─────────────────────────────────
async def score_answer(question: str, answer: str, job_title: str) -> dict:
    """
    Asks Groq to evaluate a single Q&A pair and return a score.
    Returns a dict with score (0-10) and brief feedback.
    """
    try:
        prompt = f"""You are evaluating an interview answer for a {job_title} position.

Question: {question}
Candidate Answer: {answer}

Rate this answer on a scale of 0-10, provide ONE sentence of feedback, and provide what a brief "Ideal/Compatible Answer" would have been.
Respond ONLY with valid JSON in this exact format:
{{"score": 7, "feedback": "Good understanding of the concept but lacked specific examples.", "ideal_answer": "The candidate should have mentioned X and Y."}}
"""
        response = await groq_client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200,
        )

        raw = response.choices[0].message.content.strip()
        # Extract JSON even if surrounded by markdown
        start = raw.find("{")
        end = raw.rfind("}") + 1
        return json.loads(raw[start:end])

    except Exception as e:
        logger.error(f"Scoring error: {e}")
        return {"score": 5, "feedback": "Unable to evaluate answer."}


# ── Generate Final Feedback Summary ──────────────────────
async def generate_final_feedback(chat_history: list, job_title: str, total_score: float) -> str:
    """
    Generates a highly structured Markdown feedback report for HR and the Candidate.
    """
    try:
        # Build a detailed transcript with scoring context
        transcript = ""
        qa_pairs = []
        
        # Iterate through pairs of Assistant -> User
        for i in range(len(chat_history)):
            if chat_history[i]["role"] == "assistant":
                q = chat_history[i]["content"]
                a = ""
                score = 0
                ideal = ""
                if i + 1 < len(chat_history) and chat_history[i+1]["role"] == "user":
                    user_msg = chat_history[i+1]
                    a = user_msg["content"]
                    score = user_msg.get("score", 0)
                    ideal = user_msg.get("ideal_answer", "N/A")
                
                qa_pairs.append((q, a, score, ideal))

        # Build prompt for Groq to write the top-level summary
        prompt = f"""You are a senior HR analyst. Evaluate this candidate for the {job_title} position based on the transcript.
Overall Average Score: {total_score:.1f}/10.

Provide your evaluation EXACTLY in this Markdown format:

**Executive Summary:**
(Write 2 sentences summarizing their overall performance and your hiring recommendation.)

**Categorized Scoring:**
* 🧠 Technical Expertise: (Score 0-10)
* 🗣️ Communication Clarity: (Score 0-10)
* 🧩 Problem Solving / Depth: (Score 0-10)

**🚩 Red Flags & 🟢 Green Flags:**
* 🟢 (Green flag 1)
* 🟢 (Green flag 2)
* 🚩 (Red flag 1, or "None")
"""
        summary_response = await groq_client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=500,
        )
        overall_summary = summary_response.choices[0].message.content.strip()

        # Build the final structured Markdown report
        report = f"## 📊 HR Evaluation Report\n\n"
        report += f"{overall_summary}\n\n"
        report += f"---\n## 📝 Question-by-Question Breakdown\n\n"

        for idx, (q, a, score, ideal) in enumerate(qa_pairs, 1):
            if not a: continue  # Skip unanswered questions (like the closing statement)
            report += f"### Question {idx}\n"
            report += f"**🗣️ AI Interviewer:** {q}\n\n"
            report += f"**👤 Candidate Answer:** {a}\n\n"
            report += f"**✅ Compatible/Ideal Answer:** {ideal}\n\n"
            report += f"**🎯 Score:** {score}/10\n\n"
            
        return report

    except Exception as e:
        logger.error(f"Final feedback error: {e}")
        return "Interview completed. Manual review recommended."

# ── Generate Candidate Feedback (Sanitized) ────────────────
async def generate_candidate_feedback(chat_history: list, job_title: str) -> str:
    """
    Generates a constructive, encouraging feedback report meant exclusively
    for the candidate. Hides cheating/proctoring flags and exact scoring metrics.
    """
    try:
        qa_pairs = []
        for i in range(len(chat_history)):
            if chat_history[i]["role"] == "assistant":
                q = chat_history[i]["content"]
                a = ""
                ideal = ""
                if i + 1 < len(chat_history) and chat_history[i+1]["role"] == "user":
                    user_msg = chat_history[i+1]
                    a = user_msg["content"]
                    ideal = user_msg.get("ideal_answer", "N/A")
                qa_pairs.append((q, a, ideal))

        prompt = f"""You are an encouraging AI Interview Coach. Based on this interview transcript for a {job_title} position, write a brief personalized summary telling the candidate what they did well. 
Then, provide a bulleted list of the specific technical concepts they struggled with (if any) that they should study to improve. If they did perfectly, provide a minor advanced topic they could explore next. 
Do not mention scores or cheating.
"""
        summary_response = await groq_client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=400,
        )
        overall_summary = summary_response.choices[0].message.content.strip()

        report = f"## 🌟 Your Interview Feedback\n\n"
        report += f"{overall_summary}\n\n"
        report += f"---\n## 📚 Interview Review (Learn & Grow)\n\n"

        for idx, (q, a, ideal) in enumerate(qa_pairs, 1):
            if not a: continue
            report += f"### Question {idx}\n"
            report += f"**🗣️ Question:** {q}\n\n"
            report += f"**👤 Your Answer:** {a}\n\n"
            report += f"**💡 Ideal Answer Strategy:** {ideal}\n\n"
            
        return report

    except Exception as e:
        logger.error(f"Candidate feedback error: {e}")
        return "Thank you for completing the interview! Your results have been saved."


# ── Kokoro-82M (Local Neural Voice) ─────────────────────────────
MODEL_DIR = r"c:\Users\shreyans\Desktop\Job Portal\jcentrix\jcentrix-backend\models_tts"
model_path = os.path.join(MODEL_DIR, "kokoro-v1.0.onnx")
voices_path = os.path.join(MODEL_DIR, "voices-v1.0.bin")

_kokoro_instance = None

def get_kokoro():
    global _kokoro_instance
    if _kokoro_instance is None:
        if os.path.exists(model_path) and os.path.exists(voices_path):
            try:
                logger.info("Initializing local Kokoro TTS engine...")
                _kokoro_instance = Kokoro(model_path, voices_path)
            except Exception as e:
                logger.error(f"Failed to load Kokoro model: {e}")
        else:
            logger.error(f"Kokoro model files not found at {MODEL_DIR}!")
    return _kokoro_instance

async def text_to_speech(text: str) -> Optional[bytes]:
    """
    Converts AI text response to realistic speech audio using local Kokoro ONNX model.
    Returns raw WAV audio bytes, or None if it fails.
    """
    try:
        kokoro = get_kokoro()
        if kokoro is None:
            logger.warning("Kokoro instance not available.")
            return None

        # Generate audio samples asynchronously in a worker thread
        # af_bella is a high-quality professional female voice.
        samples, sample_rate = await asyncio.to_thread(
            kokoro.create,
            text,
            voice="af_bella",
            speed=1.0,
            lang="en-us"
        )

        audio_buffer = io.BytesIO()
        sf.write(audio_buffer, samples, sample_rate, format="WAV")
        return audio_buffer.getvalue()

    except Exception as e:
        logger.error(f"Kokoro TTS error: {e}")
        import traceback
        traceback.print_exc()
        return None

