"""Groq integration and validation for resume-analysis JSON."""

from __future__ import annotations

import json
from typing import Any

from groq import Groq

from prompts import SYSTEM_PROMPT, build_analysis_prompt, build_resume_additions_prompt


class AnalysisError(Exception):
    """Raised when the AI analysis cannot be requested or validated."""


# A current Groq production model that supports JSON/structured responses.
MODEL = "openai/gpt-oss-120b"
PREFERRED_MODELS = (
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "qwen/qwen3.6-27b",
    "llama-3.1-8b-instant",
)
REQUIRED_TOP_LEVEL_FIELDS = {
    "match_score",
    "matching_skills",
    "missing_skills",
    "ats_keywords",
    "problems",
    "recommendations",
    "final_result",
}


def _validate_result(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise AnalysisError("The AI returned an invalid response format.")
    missing = REQUIRED_TOP_LEVEL_FIELDS - data.keys()
    if missing:
        raise AnalysisError(f"The AI response omitted: {', '.join(sorted(missing))}.")

    score = data["match_score"]
    if not isinstance(score, dict) or not isinstance(score.get("overall"), (int, float)):
        raise AnalysisError("The AI response did not include a valid match score.")
    score["overall"] = max(0, min(100, round(score["overall"])))

    breakdown = score.get("breakdown", {})
    if not isinstance(breakdown, dict):
        score["breakdown"] = {}

    for key in ("matching_skills", "missing_skills", "problems", "recommendations"):
        if not isinstance(data[key], list):
            data[key] = []

    ats = data["ats_keywords"]
    if not isinstance(ats, dict):
        ats = {}
        data["ats_keywords"] = ats
    ats["found"] = ats["found"] if isinstance(ats.get("found"), list) else []
    ats["missing"] = ats["missing"] if isinstance(ats.get("missing"), list) else []
    coverage = ats.get("coverage_percent", 0)
    ats["coverage_percent"] = max(0, min(100, round(coverage))) if isinstance(coverage, (int, float)) else 0

    final_result = data["final_result"]
    if not isinstance(final_result, dict):
        raise AnalysisError("The AI response did not include a final result.")
    final_result.setdefault("label", "Match assessed")
    final_result.setdefault("summary", "Review the matching skills and recommendations.")
    return data


def _available_model_ids(client: Groq) -> set[str]:
    """Retrieve the model IDs enabled for this specific Groq API key."""
    models = client.models.list()
    return {model.id for model in models.data if getattr(model, "id", None)}


def _select_model(client: Groq, requested_model: str | None) -> str:
    """Choose a configured model only if the current API key can access it."""
    try:
        available = _available_model_ids(client)
    except Exception:
        # The chat request will still provide Groq's original error if model discovery is unavailable.
        return requested_model or MODEL

    if requested_model and requested_model in available:
        return requested_model
    for model in PREFERRED_MODELS:
        if model in available:
            return model
    raise AnalysisError(
        "No compatible Groq chat model was found for this API key. "
        "Check the enabled models in your Groq console."
    )


def analyze_resume(resume_text: str, job_description: str, api_key: str, model: str = MODEL) -> dict[str, Any]:
    """Return a validated structured comparison from Groq."""
    if not resume_text.strip():
        raise AnalysisError("The resume contains no readable text.")
    if not job_description.strip():
        raise AnalysisError("The job description is empty.")

    try:
        client = Groq(api_key=api_key)
        selected_model = _select_model(client, model)
        response = client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_analysis_prompt(resume_text, job_description)},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = response.choices[0].message.content
        if not content:
            raise AnalysisError("Groq returned an empty response.")
        result = _validate_result(json.loads(content))
        result["model_used"] = selected_model
        return result
    except AnalysisError:
        raise
    except json.JSONDecodeError as error:
        raise AnalysisError("Groq returned malformed JSON. Please try again.") from error
    except Exception as error:
        raise AnalysisError(str(error)) from error


def create_resume_additions(
    resume_text: str, job_description: str, api_key: str, model: str = MODEL
) -> dict[str, Any]:
    """Return only source-evidenced keywords that can be appended safely."""
    try:
        client = Groq(api_key=api_key)
        selected_model = _select_model(client, model)
        response = client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_resume_additions_prompt(resume_text, job_description)},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        content = response.choices[0].message.content
        if not content:
            raise AnalysisError("Groq returned an empty resume update.")
        data = json.loads(content)
        if not isinstance(data, dict) or not isinstance(data.get("skills_to_add"), list):
            raise AnalysisError("The AI returned an invalid resume-update format. Please try again.")
        data["skills_to_add"] = [str(skill).strip() for skill in data["skills_to_add"] if str(skill).strip()]
        return data
    except AnalysisError:
        raise
    except json.JSONDecodeError as error:
        raise AnalysisError("Groq returned malformed JSON. Please try again.") from error
    except Exception as error:
        raise AnalysisError(str(error)) from error
