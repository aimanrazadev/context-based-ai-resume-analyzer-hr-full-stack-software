from pydantic import BaseModel, Field


class ParsedResumeRaw(BaseModel):
    headings_found: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_sections: list[str] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)
    is_low_confidence: bool = False
    parser_layers: dict = Field(default_factory=dict)


class ParsedResumeStructured(BaseModel):
    version: int = 3
    sections: dict = Field(default_factory=dict)
    raw: ParsedResumeRaw = Field(default_factory=ParsedResumeRaw)
