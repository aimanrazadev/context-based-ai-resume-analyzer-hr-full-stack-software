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


class AIResumeSections(BaseModel):
    skills: AIResumeSkills = Field(default_factory=AIResumeSkills)
    experience: AIResumeExperience = Field(default_factory=AIResumeExperience)
    education: AIResumeEducation = Field(default_factory=AIResumeEducation)


class AIResumeRaw(BaseModel):
    warnings: list[str] = Field(default_factory=list)


class AIResumeStructured(BaseModel):
    version: int = 1
    sections: AIResumeSections = Field(default_factory=AIResumeSections)
    raw: AIResumeRaw = Field(default_factory=AIResumeRaw)

