export const SKILL_ALIASES = {
  fastapi: "fastapi",
  "fast api": "fastapi",
  js: "javascript",
  javascript: "javascript",
  "machine learning": "machine learning",
  machinelearning: "machine learning",
  ml: "machine learning",
  "natural language processing": "nlp",
  naturallanguageprocessing: "nlp",
  nlp: "nlp",
  mysql: "sql",
  postgres: "sql",
  postgresql: "sql",
  sql: "sql",
  sqlite: "sql",
  react: "react",
  reactjs: "react",
  "react.js": "react",
  "rest api": "api",
  "rest apis": "api",
  restapi: "api",
  restapis: "api",
  api: "api",
  apis: "api",
  "large language models": "llm",
  largelanguagemodels: "llm",
  llm: "llm",
  llms: "llm",
  "gemini api": "gemini",
  gemini: "gemini",
  "openai api": "openai",
  openai: "openai",
  "scikit learn": "scikit-learn",
  "scikit-learn": "scikit-learn",
  sklearn: "scikit-learn",
  "problem solving": "problem solving",
  problemsolving: "problem solving",
  communication: "communication",
  communications: "communication",
  teamwork: "teamwork",
};

export function cleanList(items = [], limit = 6) {
  if (!Array.isArray(items)) return [];
  return [...new Set(items.map((item) => String(item || "").trim()).filter(Boolean))].slice(0, limit);
}

export function normalizeSkill(skill) {
  const normalized = String(skill || "")
    .toLowerCase()
    .replace(/[^a-z0-9+#. ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const compact = normalized.replace(/\s+/g, "");
  return SKILL_ALIASES[normalized] || SKILL_ALIASES[compact] || normalized;
}

export function uniqueByNormalizedSkill(items = [], excludeKeys = new Set()) {
  const seen = new Set(excludeKeys);
  const result = [];
  cleanList(items, 80).forEach((skill) => {
    const key = normalizeSkill(skill);
    if (!key || seen.has(key)) return;
    seen.add(key);
    result.push(skill);
  });
  return result;
}
