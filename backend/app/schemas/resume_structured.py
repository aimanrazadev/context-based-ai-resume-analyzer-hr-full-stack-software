from pydantic import BaseModel, Field


class ParsedResumeSkillSections(BaseModel):
    text: str = ""
    items: list[str] = Field(default_factory=list)
    primary: list[str] = Field(default_factory=list)
    secondary: list[str] = Field(default_factory=list)
    technical: list[str] = Field(default_factory=list)
    soft: list[str] = Field(default_factory=list)


class ParsedExperienceItem(BaseModel):
    summary: str = ""
    date_hint: str = ""
    entry_type: str = ""
    job_title: str = ""
    company_name: str = ""


class ParsedProjectItem(BaseModel):
    summary: str = ""
    project_hint: str = ""


class ParsedEducationItem(BaseModel):
    summary: str = ""
    category_hint: str = ""
    institution: str = ""
    date_hint: str = ""


class ParsedCertificationItem(BaseModel):
    summary: str = ""
    issuer: str = ""
    date_hint: str = ""


class ParsedResumeSections(BaseModel):
    skills: ParsedResumeSkillSections = Field(default_factory=ParsedResumeSkillSections)
    experience: dict = Field(default_factory=dict)
    projects: dict = Field(default_factory=dict)
    education: dict = Field(default_factory=dict)
    certifications: dict = Field(default_factory=dict)


class ParsedResumeRaw(BaseModel):
    headings_found: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_sections: list[str] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)
    is_low_confidence: bool = False


class ParsedResumeStructured(BaseModel):
    version: int = 3
    sections: dict = Field(default_factory=dict)
    raw: ParsedResumeRaw = Field(default_factory=ParsedResumeRaw)
