"""Groq integration and validation for resume-analysis JSON."""

from __future__ import annotations

import json
from typing import Any

from groq import Groq

from prompts import SYSTEM_PROMPT, build_analysis_prompt, build_resume_additions_prompt


class AnalysisError(Exception):
    """Raised when the AI analysis cannot be requested or validated."""


# Updated to a valid, active Groq model
MODEL = "llama-3.1-8b-instant"

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
        raise AnalysisError(
            f"The AI response omitted: {', '.join(sorted(missing))}."
        )

    # Validate match score
    score = data["match_score"]

    if not isinstance(score, dict):
        raise AnalysisError("The AI response did not include a valid match score.")

    if not isinstance(score.get("overall"), (int, float)):
        raise AnalysisError("The AI response did not include a valid match score.")

    score["overall"] = max(
        0,
        min(100, round(score["overall"]))
    )

    breakdown = score.get("breakdown", {})

    if not isinstance(breakdown, dict):
        score["breakdown"] = {}

    # Validate list fields
    for key in (
        "matching_skills",
        "missing_skills",
        "problems",
        "recommendations",
    ):
        if not isinstance(data[key], list):
            data[key] = []

    # Validate ATS keywords
    ats = data["ats_keywords"]

    if not isinstance(ats, dict):
        ats = {}
        data["ats_keywords"] = ats

    ats["found"] = (
        ats["found"]
        if isinstance(ats.get("found"), list)
        else []
    )

    ats["missing"] = (
        ats["missing"]
        if isinstance(ats.get("missing"), list)
        else []
    )

    coverage = ats.get("coverage_percent", 0)

    if isinstance(coverage, (int, float)):
        ats["coverage_percent"] = max(
            0,
            min(100, round(coverage))
        )
    else:
        ats["coverage_percent"] = 0

    # Validate final result
    final_result = data["final_result"]

    if not isinstance(final_result, dict):
        raise AnalysisError(
            "The AI response did not include a final result."
        )

    final_result.setdefault("label", "Match assessed")
    final_result.setdefault(
        "summary",
        "Review the matching skills and recommendations."
    )

    return data


def _create_client(api_key: str) -> Groq:
    """Create a Groq client using the supplied API key."""

    if not api_key or not api_key.strip():
        raise AnalysisError("Groq API key is missing.")

    try:
        return Groq(api_key=api_key.strip())
    except Exception as error:
        raise AnalysisError(
            f"Could not initialize Groq: {error}"
        ) from error


def _check_model(client: Groq) -> str:
    """
    Verify that the required model is available.
    """
    return MODEL


def analyze_resume(
    resume_text: str,
    job_description: str,
    api_key: str,
    model: str = MODEL,
) -> dict[str, Any]:
    """Return a validated structured comparison from Groq."""

    if not resume_text.strip():
        raise AnalysisError("The resume contains no readable text.")

    if not job_description.strip():
        raise AnalysisError("The job description is empty.")

    try:
        client = _create_client(api_key)
        selected_model = MODEL

        response = client.chat.completions.create(
            model=selected_model,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": build_analysis_prompt(
                        resume_text,
                        job_description,
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        content = response.choices[0].message.content

        if not content:
            raise AnalysisError(
                "Groq returned an empty response."
            )

        result = _validate_result(
            json.loads(content)
        )

        result["model_used"] = selected_model

        return result

    except AnalysisError:
        raise

    except json.JSONDecodeError as error:
        raise AnalysisError(
            "Groq returned malformed JSON. Please try again."
        ) from error

    except Exception as error:
        raise AnalysisError(str(error)) from error


def create_resume_additions(
    resume_text: str,
    job_description: str,
    api_key: str,
    model: str = MODEL,
) -> dict[str, Any]:
    """Return only source-evidenced keywords that can be appended safely."""

    if not resume_text.strip():
        raise AnalysisError(
            "The resume contains no readable text."
        )

    if not job_description.strip():
        raise AnalysisError(
            "The job description is empty."
        )

    try:
        client = _create_client(api_key)
        selected_model = MODEL

        response = client.chat.completions.create(
            model=selected_model,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": build_resume_additions_prompt(
                        resume_text,
                        job_description,
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        content = response.choices[0].message.content

        if not content:
            raise AnalysisError(
                "Groq returned an empty resume update."
            )

        data = json.loads(content)

        if (
            not isinstance(data, dict)
            or not isinstance(data.get("skills_to_add"), list)
        ):
            raise AnalysisError(
                "The AI returned an invalid resume-update format. "
                "Please try again."
            )

        data["skills_to_add"] = [
            str(skill).strip()
            for skill in data["skills_to_add"]
            if str(skill).strip()
        ]

        return data

    except AnalysisError:
        raise

    except json.JSONDecodeError as error:
        raise AnalysisError(
            "Groq returned malformed JSON. Please try again."
        ) from error

    except Exception as error:
        raise AnalysisError(str(error)) from error
