from pydantic import BaseModel, Field


class AIResumeSkills(BaseModel):
    text: str = ""
    items: list[str] = Field(default_factory=list)
    primary: list[str] = Field(default_factory=list)
    secondary: list[str] = Field(default_factory=list)


class AIResumeExperience(BaseModel):
    text: str = ""
    bullets: list[str] = Field(default_factory=list)


class AIResumeEducation(BaseModel):
    text: str = ""
    items: list[str] = Field(default_factory=list)


class AIResumeProjects(BaseModel):
    text: str = ""
    items: list[str] = Field(default_factory=list)


class AIResumeSections(BaseModel):
    skills: AIResumeSkills = Field(default_factory=AIResumeSkills)
    experience: AIResumeExperience = Field(default_factory=AIResumeExperience)
    projects: AIResumeProjects = Field(default_factory=AIResumeProjects)
    education: AIResumeEducation = Field(default_factory=AIResumeEducation)


class AIResumeAnalysis(BaseModel):
    candidate_summary: str = ""
    recruiter_summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    hiring_recommendation: str = ""


class AIResumeRaw(BaseModel):
    warnings: list[str] = Field(default_factory=list)


class AIResumeStructured(BaseModel):
    version: int = 3
    sections: AIResumeSections = Field(default_factory=AIResumeSections)
    analysis: AIResumeAnalysis = Field(default_factory=AIResumeAnalysis)
    raw: AIResumeRaw = Field(default_factory=AIResumeRaw)
