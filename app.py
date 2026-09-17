"""Streamlit entry point for the AI Resume Analyzer."""

from __future__ import annotations

import os
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from analyzer import AnalysisError, analyze_resume, create_resume_additions
from document_generator import ResumeUpdateError, update_docx_resume
from resume_parser import (
    ResumeParseError,
    extract_resume_text,
    supported_file_types,
)


load_dotenv()


# =========================================================
# GROQ CONFIGURATION
# =========================================================

# IMPORTANT:
# Do NOT change this model.
# llama-3.3-70b-versatile is no longer available for
# free/developer-tier usage.
GROQ_MODEL = "openai/gpt-oss-120b"


def _get_groq_api_key() -> str | None:
    """
    Read the Groq API key from Streamlit Secrets first,
    then from the local .env file.
    """

    try:
        return (
            st.secrets.get("GROQ_API_KEY")
            or os.getenv("GROQ_API_KEY")
        )

    except FileNotFoundError:
        return os.getenv("GROQ_API_KEY")


def _get_groq_model() -> str:
    """
    Always use the current supported Groq model.

    We intentionally DO NOT read GROQ_MODEL from Secrets
    or .env because an old value such as
    llama-3.3-70b-versatile could cause a 404 error.
    """

    return GROQ_MODEL


# =========================================================
# TAG DISPLAY
# =========================================================

def _tags(values: list[str]) -> None:

    if values:
        st.write(
            " · ".join(
                f"`{value}`"
                for value in values
            )
        )

    else:
        st.caption("None identified")


# =========================================================
# LIST SECTION
# =========================================================

def _list_section(
    title: str,
    values: list[str]
) -> None:

    st.subheader(title)

    if values:

        for value in values:
            st.markdown(
                f"- {value}"
            )

    else:
        st.caption(
            "None identified"
        )


# =========================================================
# SHOW ANALYSIS RESULTS
# =========================================================

def _show_results(
    result: dict[str, Any]
) -> None:

    score = result["match_score"]

    st.header(
        "Analysis result"
    )

    left, middle, right = st.columns(3)

    left.metric(
        "Match score",
        f"{score['overall']}/100"
    )

    middle.metric(
        "Final result",
        result["final_result"]["label"]
    )

    right.metric(
        "ATS keyword coverage",
        f"{result['ats_keywords']['coverage_percent']}%"
    )

    st.progress(
        score["overall"] / 100
    )

    st.write(
        result["final_result"]["summary"]
    )

    st.caption(
        f"Analysis model: "
        f"{result.get('model_used', GROQ_MODEL)}"
    )

    # =====================================================
    # SCORE BREAKDOWN
    # =====================================================

    st.subheader(
        "Score breakdown"
    )

    breakdown = score["breakdown"]

    st.dataframe(
        [
            {
                "Category": key.replace(
                    "_",
                    " "
                ).title(),
                "Score": value,
            }
            for key, value in breakdown.items()
        ],
        hide_index=True,
        use_container_width=True,
    )

    # =====================================================
    # MATCHING / MISSING SKILLS
    # =====================================================

    first, second = st.columns(2)

    with first:

        _list_section(
            "Matching skills",
            result["matching_skills"]
        )

        _list_section(
            "Missing skills",
            result["missing_skills"]
        )

    with second:

        _list_section(
            "ATS keywords found",
            result["ats_keywords"]["found"]
        )

        _list_section(
            "ATS keywords missing",
            result["ats_keywords"]["missing"]
        )

    # =====================================================
    # PROBLEMS
    # =====================================================

    _list_section(
        "Problems to address",
        result["problems"]
    )

    # =====================================================
    # RECOMMENDATIONS
    # =====================================================

    _list_section(
        "Recommendations",
        result["recommendations"]
    )

    # =====================================================
    # STRUCTURED JSON
    # =====================================================

    with st.expander(
        "View structured JSON"
    ):

        st.json(result)


# =========================================================
# IMPROVED RESUME SECTION
# =========================================================

def _improved_resume_section() -> None:
    """
    Show the source-preserving DOCX download after analysis.
    """

    st.divider()

    if "improved_resume_docx" in st.session_state:

        st.header(
            "Your updated resume is ready"
        )

        st.write(
            "The original design, photo, text, colors, "
            "and page settings have been kept. Only "
            "supported skills were added to the existing "
            "Skills section."
        )

        st.download_button(
            "Download updated Word resume",
            data=st.session_state[
                "improved_resume_docx"
            ],
            file_name="updated_resume.docx",
            mime=(
                "application/vnd.openxmlformats-"
                "officedocument.wordprocessingml.document"
            ),
            use_container_width=True,
        )

    elif "source_preservation_note" in st.session_state:

        st.info(
            st.session_state[
                "source_preservation_note"
            ]
        )


# =========================================================
# MAIN APPLICATION
# =========================================================

def main() -> None:

    # =====================================================
    # PAGE CONFIGURATION
    # =====================================================

    st.set_page_config(
        page_title="AI Resume Analyzer",
        page_icon="📄",
        layout="wide",
    )

    # =====================================================
    # TITLE
    # =====================================================

    st.title(
        "AI Resume Analyzer"
    )

    st.caption(
        "Compare a resume with a job description "
        "and receive structured, evidence-based feedback."
    )

    # =====================================================
    # API KEY
    # =====================================================

    api_key = _get_groq_api_key()

    # =====================================================
    # MODEL
    # =====================================================

    # IMPORTANT:
    # This ALWAYS returns openai/gpt-oss-120b.
    #
    # Even if Streamlit Secrets contains:
    #
    # GROQ_MODEL = "llama-3.3-70b-versatile"
    #
    # it will NOT be used.
    model = _get_groq_model()

    # =====================================================
    # API KEY WARNING
    # =====================================================

    if not api_key:

        st.warning(
            "Add `GROQ_API_KEY` to "
            "`.streamlit/secrets.toml` "
            "before analyzing a resume."
        )

    # =====================================================
    # ANALYSIS FORM
    # =====================================================

    with st.form(
        "analysis_form"
    ):

        resume_file = st.file_uploader(
            "Upload resume",
            type=supported_file_types()
        )

        job_description = st.text_area(
            "Paste the job description",
            height=260,
            placeholder=(
                "Paste the complete job description here..."
            ),
        )

        submitted = st.form_submit_button(
            "Analyze resume",
            type="primary",
        )

    # =====================================================
    # ANALYSIS EXECUTION
    # =====================================================

    if submitted:

        # -------------------------------------------------
        # INPUT VALIDATION
        # -------------------------------------------------

        if (
            not resume_file
            or not job_description.strip()
        ):

            st.error(
                "Upload a resume and paste a job description."
            )

            return

        # -------------------------------------------------
        # API KEY VALIDATION
        # -------------------------------------------------

        if not api_key:

            st.error(
                "A Groq API key is required. "
                "Add it to `.streamlit/secrets.toml`."
            )

            return

        try:

            # =============================================
            # EXTRACT RESUME TEXT
            # =============================================

            with st.spinner(
                "Extracting resume text..."
            ):

                resume_text = extract_resume_text(
                    resume_file.getvalue(),
                    resume_file.name,
                )

            # =============================================
            # ANALYZE RESUME
            # =============================================

            with st.spinner(
                "Analyzing fit with Groq..."
            ):

                # IMPORTANT:
                # model is ALWAYS:
                #
                # openai/gpt-oss-120b
                #
                result = analyze_resume(
                    resume_text,
                    job_description,
                    api_key,
                    model,
                )

            # =============================================
            # UPDATED RESUME
            # =============================================

            improved_resume_docx = None

            source_preservation_note = ""

            # =============================================
            # DOCX RESUME
            # =============================================

            if resume_file.name.lower().endswith(
                ".docx"
            ):

                with st.spinner(
                    "Updating only the existing Skills section..."
                ):

                    additions = create_resume_additions(
                        resume_text,
                        job_description,
                        api_key,
                        model,
                    )

                    improved_resume_docx = (
                        update_docx_resume(
                            resume_file.getvalue(),
                            additions[
                                "skills_to_add"
                            ],
                        )
                    )

            # =============================================
            # NON-DOCX RESUME
            # =============================================

            else:

                source_preservation_note = (
                    "Exact layout preservation is available "
                    "for DOCX resumes. Please upload the original "
                    "DOCX file to keep its photo, fonts, colors, "
                    "and pages unchanged."
                )

            # =============================================
            # SAVE ANALYSIS
            # =============================================

            st.session_state[
                "analysis"
            ] = result

            st.session_state[
                "resume_text"
            ] = resume_text

            st.session_state[
                "job_description"
            ] = job_description

            # =============================================
            # SAVE UPDATED DOCX
            # =============================================

            if improved_resume_docx:

                st.session_state[
                    "improved_resume_docx"
                ] = improved_resume_docx

                st.session_state.pop(
                    "source_preservation_note",
                    None,
                )

            else:

                st.session_state.pop(
                    "improved_resume_docx",
                    None,
                )

                st.session_state[
                    "source_preservation_note"
                ] = source_preservation_note

        # =================================================
        # RESUME PARSING ERROR
        # =================================================

        except ResumeParseError as error:

            st.error(
                f"Could not read the resume: {error}"
            )

        # =================================================
        # DOCX UPDATE ERROR
        # =================================================

        except ResumeUpdateError as error:

            st.error(
                "The original resume was kept unchanged: "
                f"{error}"
            )

        # =================================================
        # GROQ ANALYSIS ERROR
        # =================================================

        except AnalysisError as error:

            error_text = str(error)

            # -------------------------------------------------
            # OLD MODEL ERROR
            # -------------------------------------------------

            if (
                "llama-3.3-70b-versatile"
                in error_text
            ):

                st.error(
                    "The old Groq model is still being "
                    "used inside analyzer.py. Please make "
                    "sure analyzer.py uses the model value "
                    "passed from app.py instead of hardcoding "
                    "`llama-3.3-70b-versatile`."
                )

            else:

                st.error(
                    f"Analysis could not be completed: "
                    f"{error}"
                )

    # =====================================================
    # DISPLAY RESULTS
    # =====================================================

    if "analysis" in st.session_state:

        _show_results(
            st.session_state[
                "analysis"
            ]
        )

        _improved_resume_section()


# =========================================================
# APPLICATION ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()
