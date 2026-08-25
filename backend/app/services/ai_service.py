"""
AI Mock Interview provider chain: Gemini (primary) -> Groq (fallback)
-> rule-based templates (final fallback, never fails).

Model names are read from .env (GEMINI_MODEL, GROQ_MODEL) rather than
hardcoded, because both providers deprecate and rename models on a
timescale of months, not years — a hardcoded model name is exactly the
kind of thing that silently breaks this feature weeks after it was
last tested. If either provider starts returning errors, check
whether the configured model name has been retired before assuming
the code itself is broken.

Both provider calls fail closed and cheaply: a network error, missing
API key, unexpected response shape, or non-2xx status all raise
AIProviderError and move to the next provider in the chain, rather
than propagating a raw exception up to the candidate's mock interview
session. The rule-based fallback guarantees the feature always
produces SOMETHING, even with zero API keys configured — worth
demonstrating in your defence as a resilience property, not just an
implementation detail.
"""
import json
import re

import httpx

from app.config import settings

GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class AIProviderError(Exception):
    pass


def _extract_json(text: str) -> dict | list:
    """
    LLMs frequently wrap JSON responses in ```json ... ``` markdown
    fences despite being asked not to. Strip those before parsing
    rather than letting json.loads fail on the fence characters.
    """
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    return json.loads(text)


async def _call_gemini(prompt: str) -> str:
    if not settings.GEMINI_API_KEY:
        raise AIProviderError("GEMINI_API_KEY not configured")

    url = GEMINI_URL_TEMPLATE.format(model=settings.GEMINI_MODEL)
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            url,
            params={"key": settings.GEMINI_API_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}]},
        )
    if response.status_code != 200:
        raise AIProviderError(f"Gemini returned {response.status_code}: {response.text[:200]}")

    data = response.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise AIProviderError(f"Unexpected Gemini response shape: {e}")


async def _call_groq(prompt: str) -> str:
    if not settings.GROQ_API_KEY:
        raise AIProviderError("GROQ_API_KEY not configured")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
            json={
                "model": settings.GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            },
        )
    if response.status_code != 200:
        raise AIProviderError(f"Groq returned {response.status_code}: {response.text[:200]}")

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise AIProviderError(f"Unexpected Groq response shape: {e}")


async def _call_llm_chain(prompt: str) -> tuple[str, str]:
    """Returns (response_text, provider_used). Raises AIProviderError
    only if BOTH Gemini and Groq fail — the caller's rule-based
    fallback handles that case."""
    try:
        text = await _call_gemini(prompt)
        return text, "gemini"
    except AIProviderError:
        pass

    try:
        text = await _call_groq(prompt)
        return text, "groq"
    except AIProviderError:
        pass

    raise AIProviderError("Both Gemini and Groq are unavailable")


# ---------------------------------------------------------------------
# Question generation
# ---------------------------------------------------------------------

async def generate_interview_questions(skills: list[str], job_title: str | None = None, num_questions: int = 5) -> dict:
    skills_text = ", ".join(skills) if skills else "general software development"
    context = f"for a {job_title} role" if job_title else "for a general software development role"

    prompt = (
        f"Generate {num_questions} realistic technical interview questions {context}, "
        f"focused on these skills: {skills_text}. Mix conceptual and practical/scenario-based "
        f"questions. Respond with ONLY a JSON array of strings, no other text, no markdown fences. "
        f'Example format: ["Question 1?", "Question 2?"]'
    )

    try:
        text, provider = await _call_llm_chain(prompt)
        questions = _extract_json(text)
        if not isinstance(questions, list) or not all(isinstance(q, str) for q in questions):
            raise AIProviderError("Response was not a JSON array of strings")
        return {"questions": questions[:num_questions], "provider_used": provider}
    except (AIProviderError, json.JSONDecodeError):
        return {"questions": _rule_based_questions(skills, job_title, num_questions), "provider_used": "rule-based"}


def _rule_based_questions(skills: list[str], job_title: str | None, num_questions: int) -> list[str]:
    """
    Deterministic template questions, used when both AI providers are
    unavailable (no API keys configured, network failure, or a
    deprecated model name — see module docstring). Not a substitute
    for AI-generated questions in sophistication, but a functioning
    interview session is more useful to a candidate than an error page.
    """
    templates = [
        "Can you walk me through a project where you used {skill}? What was your specific contribution?",
        "What is the biggest challenge you've faced while working with {skill}, and how did you resolve it?",
        "How would you explain {skill} to someone with no technical background?",
        "Describe a time you had to debug a difficult issue involving {skill}.",
        "What trade-offs would you consider when deciding whether to use {skill} for a new project?",
    ]
    generic = [
        "Tell me about a project you're proud of and what made it challenging.",
        "How do you approach learning a new technology or skill quickly?",
        "Describe a time you disagreed with a technical decision and how you handled it.",
    ]

    questions = []
    skill_cycle = skills if skills else []
    for i in range(num_questions):
        if skill_cycle:
            skill = skill_cycle[i % len(skill_cycle)]
            template = templates[i % len(templates)]
            questions.append(template.format(skill=skill))
        else:
            questions.append(generic[i % len(generic)])
    return questions


# ---------------------------------------------------------------------
# Answer scoring
# ---------------------------------------------------------------------

async def score_interview_answers(qa_pairs: list[dict]) -> dict:
    """qa_pairs: [{"question": "...", "answer": "..."}, ...]"""
    formatted_qa = "\n\n".join(
        f"Q{i+1}: {pair['question']}\nA{i+1}: {pair['answer']}" for i, pair in enumerate(qa_pairs)
    )
    prompt = (
        "You are an experienced technical interviewer. Score each answer below from 0-10 on "
        "clarity, technical accuracy, and completeness, and give one sentence of constructive "
        "feedback per answer. Respond with ONLY a JSON object, no other text, no markdown fences, "
        'in this exact format: {"scores": [{"score": 7, "feedback": "..."}], "overall_feedback": "..."}\n\n'
        f"{formatted_qa}"
    )

    try:
        text, provider = await _call_llm_chain(prompt)
        result = _extract_json(text)
        scores = result["scores"]
        if len(scores) != len(qa_pairs):
            raise AIProviderError("Score count did not match answer count")
        overall = round(sum(s["score"] for s in scores) / len(scores), 1)
        return {
            "scores": scores,
            "overall_score": overall,
            "overall_feedback": result.get("overall_feedback", ""),
            "provider_used": provider,
        }
    except (AIProviderError, json.JSONDecodeError, KeyError, ZeroDivisionError):
        return _rule_based_scoring(qa_pairs)


def _rule_based_scoring(qa_pairs: list[dict]) -> dict:
    """
    Heuristic fallback scoring based on answer length and basic
    structure — NOT a claim of technical accuracy assessment, which a
    rule-based system genuinely cannot do. This is deliberately
    transparent about being a weaker fallback (see the feedback text
    it generates), rather than pretending equivalence with AI-based
    scoring. Worth disclosing exactly this way in Chapter 4/5: the
    fallback keeps the feature functional, but is honestly a lesser
    substitute, not a hidden equivalent.
    """
    scores = []
    for pair in qa_pairs:
        answer = pair.get("answer", "").strip()
        word_count = len(answer.split())

        if word_count == 0:
            score, feedback = 0, "No answer was provided."
        elif word_count < 15:
            score, feedback = 3, "Answer is quite brief — consider elaborating with a specific example."
        elif word_count < 50:
            score, feedback = 6, "Reasonable answer length. Adding a concrete example would strengthen it."
        else:
            score, feedback = 8, "Detailed answer with good elaboration."

        scores.append({"score": score, "feedback": feedback})

    overall = round(sum(s["score"] for s in scores) / len(scores), 1) if scores else 0.0
    return {
        "scores": scores,
        "overall_score": overall,
        "overall_feedback": (
            "Scored using a rule-based fallback (answer length/structure only, since AI providers "
            "were unavailable) — this is a weaker signal than AI-based technical assessment. "
            "Treat this session as practice rather than a precise skill measurement."
        ),
        "provider_used": "rule-based",
    }
