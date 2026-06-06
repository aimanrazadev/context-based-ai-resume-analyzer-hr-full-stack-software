def resume_structuring_system_prompt() -> str:
    """
    Build the system prompt for AI-based resume structuring.

    Returns:
        A strict instruction string telling the model to return only valid JSON
        and avoid extra prose.
    """
    return (
        "You are a resume parser. Return only valid JSON. No markdown, no extra text. "
        "Follow the schema exactly, use only evidence from the resume, and keep strings concise."
    )


def candidate_summary_prompt_rule() -> str:
    """
    Return the rule block for candidate and recruiter summaries.

    Returns:
        A short instruction describing how to write candidate-facing and
        recruiter-facing summaries from resume evidence only.
    """
    return (
        '- "candidate_summary": 2-3 sentences summarizing the profile in plain professional language.\n'
        '- "recruiter_summary": 2 short recruiter-friendly sentences focusing on fit, strengths, and readiness.\n'
    )


def strengths_weaknesses_prompt_rule() -> str:
    """
    Return the rule block for strengths and weaknesses extraction.

    Returns:
        Prompt instructions for concise, evidence-based strengths and
        weaknesses lists.
    """
    return (
        '- "strengths": up to 5 short evidence-based bullets.\n'
        '- "weaknesses": up to 5 short bullets describing unclear, weak, or missing areas from the resume.\n'
    )


def skill_gap_prompt_rule() -> str:
    """
    Return the rule block for missing skill analysis.

    Returns:
        Prompt instructions for identifying likely missing or weak skill areas.
    """
    return '- "missing_skills": up to 8 concise skill gaps or weak skill areas inferred only from the resume.\n'


def hiring_recommendation_prompt_rule() -> str:
    """
    Return the rule block for the hiring recommendation output.

    Returns:
        Prompt instructions for a concise recommendation field.
    """
    return (
        '- "hiring_recommendation": one of "strong_yes", "yes", "maybe", or "no" based only on resume evidence.\n'
    )


def resume_structuring_user_prompt(*, resume_text: str) -> str:
    """
    Build the user prompt for AI-based resume structuring.

    Args:
        resume_text: Clean extracted resume text.

    Returns:
        A schema-constrained prompt that asks the model for deterministic JSON
        covering skills, experience, projects, and education.
    """
    return (
        "Extract structured information from this resume text.\n\n"
        "Return JSON in this exact shape:\n"
        "{\n"
        '  "version": 3,\n'
        '  "sections": {\n'
        '    "skills": {"text": string, "items": string[], "primary": string[], "secondary": string[]},\n'
        '    "experience": {"text": string, "bullets": string[]},\n'
        '    "projects": {"text": string, "items": string[]},\n'
        '    "education": {"text": string, "items": string[]}\n'
        "  },\n"
        '  "analysis": {\n'
        '    "candidate_summary": string,\n'
        '    "recruiter_summary": string,\n'
        '    "strengths": string[],\n'
        '    "weaknesses": string[],\n'
        '    "missing_skills": string[],\n'
        '    "hiring_recommendation": string\n'
        "  },\n"
        '  "raw": {"warnings": string[]}\n'
        "}\n\n"
        "Rules:\n"
        "- Use evidence from the resume text.\n"
        "- Do not invent projects, skills, education, or work experience.\n"
        "- Deduplicate skills; keep common casing (e.g. AWS, SQL).\n"
        "- Keep bullets short; max ~20 bullets.\n"
        "- Keep project items short and recruiter-friendly.\n"
        "- If a section is missing, return an empty string/array for that section.\n"
        "- If data is missing, return empty arrays/strings and add a warning.\n\n"
        "Additional analysis rules:\n"
        f"{candidate_summary_prompt_rule()}"
        f"{strengths_weaknesses_prompt_rule()}"
        f"{skill_gap_prompt_rule()}"
        f"{hiring_recommendation_prompt_rule()}\n"
        "Resume text:\n"
        "-----\n"
        f"{resume_text or ''}\n"
        "-----\n"
    )


def job_match_system_prompt() -> str:
    """
    Build the system prompt for AI-based job matching.

    Returns:
        A strict instruction string for recruiter-style JSON output.
    """
    return (
        "You are a recruiter. Return only valid JSON. No markdown, no extra text. "
        "Use resume evidence; do not hallucinate."
    )


def job_match_user_prompt(*, job_title: str | None, job_description: str | None, resume_text: str) -> str:
    """
    Build the legacy job-match prompt.

    Args:
        job_title: Job title text, if available.
        job_description: Job description text, if available.
        resume_text: Resume text to compare against the job.

    Returns:
        A schema-constrained prompt for a legacy score/explanation response.
    """
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
    """
    Build the sectioned job-match prompt used by the newer match flow.

    Args:
        job_title: Job title text, if available.
        job_description: Job description text, if available.
        resume_text: Resume text to compare against the job.

    Returns:
        A strict JSON prompt that asks the model for sectioned recruiter-style
        match summaries.
    """
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

