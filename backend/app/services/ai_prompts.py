def resume_structuring_system_prompt() -> str:
    return (
        "You are a resume parser. Return only valid JSON. No markdown, no extra text. "
        "Follow the schema exactly and keep strings concise."
    )


def resume_structuring_user_prompt(*, resume_text: str) -> str:
    # Keep it deterministic and easy to validate on our side.
    return (
        "Extract structured information from this resume text.\n\n"
        "Return JSON in this exact shape:\n"
        "{\n"
        '  "version": 1,\n'
        '  "sections": {\n'
        '    "skills": {"text": string, "items": string[], "primary": string[], "secondary": string[]},\n'
        '    "experience": {"text": string, "bullets": string[]},\n'
        '    "education": {"text": string, "items": string[]}\n'
        "  },\n"
        '  "raw": {"warnings": string[]}\n'
        "}\n\n"
        "Rules:\n"
        "- Use evidence from the resume text.\n"
        "- Deduplicate skills; keep common casing (e.g. AWS, SQL).\n"
        "- Keep bullets short; max ~20 bullets.\n"
        "- If data is missing, return empty arrays/strings and add a warning.\n\n"
        "Resume text:\n"
        "-----\n"
        f"{resume_text or ''}\n"
        "-----\n"
    )


def job_match_system_prompt() -> str:
    return (
        "You are a recruiter. Return only valid JSON. No markdown, no extra text. "
        "Use resume evidence; do not hallucinate."
    )


def job_match_user_prompt(*, job_title: str | None, job_description: str | None, resume_text: str) -> str:
    return (
        "Score how well this resume matches the job.\n\n"
        "Return JSON in this exact shape:\n"
        "{\n"
        '  "score": 0-100,\n'
        '  "explanation": string,\n'
        '  "highlights": string[],\n'
        '  "gaps": string[]\n'
        "}\n\n"
        "Rules:\n"
        "- score is an integer 0-100.\n"
        "- explanation is 1-3 sentences.\n"
        "- highlights: up to 6 short bullets referencing evidence.\n"
        "- gaps: up to 6 short bullets for missing/weak areas.\n\n"
        "Job title:\n"
        f"{job_title or ''}\n\n"
        "Job description:\n"
        f"{job_description or ''}\n\n"
        "Resume text:\n"
        "-----\n"
        f"{resume_text or ''}\n"
        "-----\n"
    )


def job_match_sectioned_user_prompt(*, job_title: str | None, job_description: str | None, resume_text: str) -> str:
    return (
        "You are an AI resume evaluator.\n\n"
        "Analyze the resume against the job description.\n\n"
        "Return the response STRICTLY in the following JSON format:\n\n"
        "{\n"
        '  "education_summary": {\n'
        '    "score": 0-100,\n'
        '    "summary": "2 short sentences, recruiter-friendly"\n'
        "  },\n"
        '  "projects_summary": {\n'
        '    "score": 0-100,\n'
        '    "summary": "2 short sentences, practical focus"\n'
        "  },\n"
        '  "work_experience_summary": {\n'
        '    "score": 0-100,\n'
        '    "summary": "2 short sentences, role relevance"\n'
        "  },\n"
        '  "overall_match_score": 0-100\n'
        "}\n\n"
        "Rules:\n"
        "- Be concise.\n"
        "- Avoid long explanations.\n"
        "- Write like a hiring manager, not a professor.\n"
        "- No markdown. JSON only.\n"
        "- Use resume evidence; do not hallucinate.\n\n"
        "Job title:\n"
        f"{job_title or ''}\n\n"
        "Job description:\n"
        f"{job_description or ''}\n\n"
        "Resume text:\n"
        "-----\n"
        f"{resume_text or ''}\n"
        "-----\n"
    )



