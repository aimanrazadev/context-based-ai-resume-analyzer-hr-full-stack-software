import assert from "node:assert/strict";

import {
  formatApplicationStatus,
  normalizeApplicationStatus,
} from "../src/shared/utils/applicationStatus.js";
import { getScoreTone } from "../src/shared/utils/scores.js";
import { toJobApiPayload } from "../src/features/jobs/api/jobPayloadMapper.js";

function testApplicationStatus() {
  assert.equal(normalizeApplicationStatus("pending"), "not-reviewed");
  assert.equal(normalizeApplicationStatus("On Hold"), "on-hold");
  assert.equal(normalizeApplicationStatus("on_hold"), "on-hold");
  assert.equal(normalizeApplicationStatus("shortlisted"), "shortlisted");
  assert.equal(normalizeApplicationStatus("something else"), "not-reviewed");
  assert.equal(formatApplicationStatus("not-reviewed"), "Not Reviewed");
  assert.equal(formatApplicationStatus("on_hold"), "On Hold");
}

function testScoreTones() {
  assert.equal(getScoreTone(75).name, "positive");
  assert.equal(getScoreTone(50).name, "warning");
  assert.equal(getScoreTone(49).name, "negative");
  assert.equal(getScoreTone("not a number").name, "negative");
  assert.equal(getScoreTone(200).name, "positive");
}

function testJobPayloadMapping() {
  assert.deepEqual(
    toJobApiPayload({
      title: "Backend Engineer",
      shortDescription: "API role",
      salaryCurrency: "Rs",
      minExperienceYears: 2,
      jobType: "internship",
      requiredSkills: ["Python"],
    }),
    {
      title: "Backend Engineer",
      short_description: "API role",
      salary_currency: "Rs",
      min_experience_years: 2,
      job_type: "internship",
      required_skills: ["Python"],
    },
  );

  assert.deepEqual(toJobApiPayload({ title: "Updated title" }), {
    title: "Updated title",
  });

  const payload = toJobApiPayload({ title: "Draft" }, { includeDefaults: true });
  assert.equal(payload.status, "active");
  assert.equal(payload.draft_step, 1);
  assert.equal(payload.short_description, null);
}

testApplicationStatus();
testScoreTones();
testJobPayloadMapping();

console.log("Frontend unit contracts passed");
