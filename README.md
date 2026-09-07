# AI Resume Analyzer

A modular Streamlit app that compares a PDF or DOCX resume with a pasted job description using the Groq API. It returns a structured JSON analysis and an easy-to-read dashboard with a match score, skills comparison, ATS keywords, issues, and recommendations.

## Features

- PDF and DOCX resume text extraction
- Groq-powered job-fit analysis using JSON-only model output
- Overall match score with a skills, experience, ATS, and requirements breakdown
- Matching skills, missing skills, found/missing ATS keywords, problems, and honest recommendations
- Modular code with separate UI, extraction, AI integration, and prompts

## Project files

| File | Responsibility |
| --- | --- |
| `app.py` | Streamlit UI and user interaction |
| `resume_parser.py` | PDF/DOCX validation and text extraction |
| `analyzer.py` | Groq request, JSON parsing, and result validation |
| `prompts.py` | AI behavior and output contract |
| `requirements.txt` | Python dependencies |

## Setup

1. Install Python 3.10 or newer.
2. Open a terminal in this project directory.
3. Create and activate a virtual environment:

   **Windows PowerShell**

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   **macOS/Linux**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Add a valid Groq API key to `.streamlit/secrets.toml`:

   ```toml
   GROQ_API_KEY = "your_actual_key"
   GROQ_MODEL = "openai/gpt-oss-120b"
   ```

   `GROQ_MODEL` is optional and defaults to `openai/gpt-oss-120b`. The app reads Streamlit secrets first. `.env` remains supported as an optional local fallback. At runtime, the app checks the models enabled for your API key. If the configured model is unavailable, it selects a compatible fallback automatically.

## Run

```bash
streamlit run app.py
```

Streamlit will print a local URL, usually `http://localhost:8501`.

## How it works

1. The user uploads a `.pdf` or `.docx` resume and pastes a job description.
2. `resume_parser.py` extracts readable resume text locally.
3. `analyzer.py` sends the extracted text and job description to Groq with the JSON contract in `prompts.py`.
4. The UI validates and displays the resulting score and feedback.

## Privacy note

The resume text and job description are sent to Groq for analysis. Do not upload documents you are not authorized to share. This tool provides career guidance, not a hiring decision.
