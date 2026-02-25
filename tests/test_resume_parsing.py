import json


def test_parse_resume_text_detects_sections_and_skills():
    from backend.app.services.resume_parsing import parse_resume_text

    text = """
Skills
- Python, FastAPI, AWS
- SQL

Experience
Built REST APIs using FastAPI and deployed on AWS.

Education
University of Galway — MS Business Analytics
""".strip()

    parsed = parse_resume_text(text=text)
    assert parsed["version"] == 1
    assert "skills" in parsed["sections"]
    assert "experience" in parsed["sections"]
    assert "education" in parsed["sections"]

    skills = parsed["sections"]["skills"]["items"]
    assert any(s.lower() == "python" for s in skills)
    assert any(s.lower() == "fastapi" for s in skills)
    assert any(s.lower() == "aws" for s in skills)


def test_parse_resume_text_empty_has_warning():
    from backend.app.services.resume_parsing import parse_resume_text

    parsed = parse_resume_text(text="")
    assert parsed["sections"]["skills"]["items"] == []
    assert parsed["raw"]["warnings"]


def test_structured_json_is_valid_json_string_after_dump():
    from backend.app.services.resume_parsing import parse_resume_text

    parsed = parse_resume_text(text="Skills\nPython, FastAPI\n")
    raw = json.dumps(parsed, ensure_ascii=False)
    back = json.loads(raw)
    assert back["version"] == 1

