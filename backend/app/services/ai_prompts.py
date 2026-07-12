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
    Return the rule block for the single canonical candidate summary.

    Returns:
        A short instruction describing how to write the factual summary from
        resume evidence only.
    """
    return (
        '- "candidate_summary": maximum 2 concise lines and factual only: profile, major project names, primary tech stack, education institution/CGPA if present, and professional experience/company/impact if present. Do not include recommendation, strengths, weaknesses, or suitability. Omit missing facts instead of inventing them.\n'
    )


def strengths_weaknesses_prompt_rule() -> str:
    """
    Return the rule block for strengths and weaknesses extraction.

    Returns:
        Prompt instructions for concise, evidence-based strengths and
        weaknesses lists.
    """
    return (
        '- "strengths": up to 5 short evidence-based bullets focused on demonstrated strengths relevant to the target role.\n'
        '- "weaknesses": up to 5 short bullets; include only genuine missing, weak, or unclear areas. Do not invent weaknesses.\n'
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


