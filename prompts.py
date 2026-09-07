"""Prompts and output contract for the resume-analysis model."""

from __future__ import annotations


SYSTEM_PROMPT = """You are a careful resume-to-job-description analyst. Base every finding only on the supplied resume and job description. Do not invent skills, qualifications, achievements, or missing requirements. Treat equivalent skills cautiously and mention only clear equivalents. Recommendations must improve presentation or prioritize real learning; never advise false claims. Return valid JSON only, without markdown."""


def build_analysis_prompt(resume_text: str, job_description: str) -> str:
    return f"""Analyze this resume against this job description.

RESUME:
---
{resume_text}
---

JOB DESCRIPTION:
---
{job_description}
---

Return exactly this JSON structure:
{{
  "match_score": {{
    "overall": 0,
    "breakdown": {{"skills": 0, "experience": 0, "ats_keywords": 0, "education_and_requirements": 0}}
  }},
  "matching_skills": ["skill"],
  "missing_skills": ["required or preferred skill not evidenced"],
  "ats_keywords": {{"found": ["keyword"], "missing": ["keyword"], "coverage_percent": 0}},
  "problems": ["specific, truthful resume issue"],
  "recommendations": ["specific, truthful improvement"],
  "final_result": {{"label": "Strong match|Moderate match|Low match", "summary": "brief evidence-based conclusion"}}
}}

Scoring guidance: skills 40%, experience/responsibilities 30%, ATS keywords 20%, education/other requirements 10%. Each breakdown value is 0-100; overall is the weighted score rounded to a whole number. Use Strong match for 80-100, Moderate match for 60-79, Low match below 60. Keep lists concise."""


def build_resume_improvement_prompt(resume_text: str, job_description: str) -> str:
    """Ask the model for a truthful, structured ATS-friendly resume."""
    return f"""Create an improved, ATS-friendly resume using the source resume and target job description below.

SOURCE RESUME:
---
{resume_text}
---

TARGET JOB DESCRIPTION:
---
{job_description}
---

Important rules:
- Use only facts stated in the source resume.
- Do not invent job titles, employers, dates, degrees, certifications, skills, metrics, or responsibilities.
- Improve wording, ordering, and ATS relevance, but keep uncertain or absent fields empty.
- Include a keyword only when the candidate's information supports it.
- Keep bullet points concise and professional.

Return valid JSON only in exactly this shape:
{{
  "personal_details": {{"name": "", "email": "", "phone": "", "location": "", "linkedin": ""}},
  "headline": "",
  "professional_summary": "",
  "skills": [""],
  "experience": [{{"title": "", "company": "", "dates": "", "bullets": [""]}}],
  "education": [{{"degree": "", "institution": "", "dates": "", "details": ""}}],
  "projects": [{{"name": "", "details": "", "bullets": [""]}}],
  "certifications": [""],
  "additional_sections": [{{"title": "", "items": [""]}}]
}}"""
