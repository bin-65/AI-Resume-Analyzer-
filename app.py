"""Streamlit entry point for the AI Resume Analyzer."""

from __future__ import annotations

import os
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from analyzer import AnalysisError, analyze_resume, create_improved_resume
from document_generator import create_docx, create_pdf
from resume_parser import ResumeParseError, extract_resume_text, supported_file_types


load_dotenv()


def _get_groq_api_key() -> str | None:
    """Read the key from Streamlit secrets first, then a local .env file."""
    try:
        return st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    except FileNotFoundError:
        return os.getenv("GROQ_API_KEY")


def _get_groq_model() -> str:
    """Allow a supported model to be selected without editing application code."""
    try:
        return st.secrets.get("GROQ_MODEL") or os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"
    except FileNotFoundError:
        return os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"


def _tags(values: list[str]) -> None:
    if values:
        st.write(" · ".join(f"`{value}`" for value in values))
    else:
        st.caption("None identified")


def _list_section(title: str, values: list[str]) -> None:
    st.subheader(title)
    if values:
        for value in values:
            st.markdown(f"- {value}")
    else:
        st.caption("None identified")


def _show_results(result: dict[str, Any]) -> None:
    score = result["match_score"]
    st.header("Analysis result")
    left, middle, right = st.columns(3)
    left.metric("Match score", f"{score['overall']}/100")
    middle.metric("Final result", result["final_result"]["label"])
    right.metric("ATS keyword coverage", f"{result['ats_keywords']['coverage_percent']}%")
    st.progress(score["overall"] / 100)
    st.write(result["final_result"]["summary"])
    st.caption(f"Analysis model: {result.get('model_used', 'Groq')}")

    st.subheader("Score breakdown")
    breakdown = score["breakdown"]
    st.dataframe(
        [{"Category": key.replace("_", " ").title(), "Score": value} for key, value in breakdown.items()],
        hide_index=True,
        use_container_width=True,
    )

    first, second = st.columns(2)
    with first:
        _list_section("Matching skills", result["matching_skills"])
        _list_section("Missing skills", result["missing_skills"])
    with second:
        _list_section("ATS keywords found", result["ats_keywords"]["found"])
        _list_section("ATS keywords missing", result["ats_keywords"]["missing"])

    _list_section("Problems to address", result["problems"])
    _list_section("Recommendations", result["recommendations"])

    with st.expander("View structured JSON"):
        st.json(result)


def _improved_resume_section() -> None:
    """Show automatically generated resume downloads after analysis."""
    st.divider()
    if "improved_resume_docx" in st.session_state:
        st.header("Your improved resume is ready")
        st.write("It has been automatically reformatted and tailored using the information already present in your CV.")
        left, right = st.columns(2)
        left.download_button(
            "Download Word resume",
            data=st.session_state["improved_resume_docx"],
            file_name="improved_resume.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
        right.download_button(
            "Download PDF resume",
            data=st.session_state["improved_resume_pdf"],
            file_name="improved_resume.pdf",
            mime="application/pdf",
            use_container_width=True,
        )


def main() -> None:
    st.set_page_config(page_title="AI Resume Analyzer", page_icon="📄", layout="wide")
    st.title("AI Resume Analyzer")
    st.caption("Compare a resume with a job description and receive structured, evidence-based feedback.")

    api_key = _get_groq_api_key()
    model = _get_groq_model()
    if not api_key:
        st.warning("Add `GROQ_API_KEY` to `.streamlit/secrets.toml` before analyzing a resume.")

    with st.form("analysis_form"):
        resume_file = st.file_uploader("Upload resume", type=supported_file_types())
        job_description = st.text_area(
            "Paste the job description", height=260, placeholder="Paste the complete job description here..."
        )
        submitted = st.form_submit_button("Analyze resume", type="primary")

    if submitted:
        if not resume_file or not job_description.strip():
            st.error("Upload a resume and paste a job description.")
            return
        if not api_key:
            st.error("A Groq API key is required. Add it to `.streamlit/secrets.toml`.")
            return

        try:
            with st.spinner("Extracting resume text..."):
                resume_text = extract_resume_text(resume_file.getvalue(), resume_file.name)
            with st.spinner("Analyzing fit with Groq..."):
                result = analyze_resume(resume_text, job_description, api_key, model)
            with st.spinner("Automatically creating your improved resume..."):
                structured_resume = create_improved_resume(resume_text, job_description, api_key, model)
                improved_resume_docx = create_docx(structured_resume)
                improved_resume_pdf = create_pdf(structured_resume)
            st.session_state["analysis"] = result
            st.session_state["resume_text"] = resume_text
            st.session_state["job_description"] = job_description
            st.session_state["improved_resume_docx"] = improved_resume_docx
            st.session_state["improved_resume_pdf"] = improved_resume_pdf
        except ResumeParseError as error:
            st.error(f"Could not read the resume: {error}")
        except AnalysisError as error:
            st.error(f"Analysis could not be completed: {error}")

    if "analysis" in st.session_state:
        _show_results(st.session_state["analysis"])
        _improved_resume_section()


if __name__ == "__main__":
    main()
