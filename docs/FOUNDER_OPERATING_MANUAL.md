# AuraAI Founder Operating Manual

**Purpose:** Explain how the founder controls AuraAI safely and consistently.

---

## 1. Founder Role

You are the final authority. AuraAI may research, recommend, prepare, execute approved work, and maintain durable state, but it should pause before sensitive or irreversible actions.

---

## 2. Daily Founder Workflow

A normal founder session should eventually be:

1. Open Mission Control.
2. Review system health and recovery status.
3. Review missions requiring attention.
4. Approve, reject, revise, pause, or resume work.
5. Review produced artifacts.
6. Approve publishing packages.
7. Publish manually where required.
8. confirm publication with URL or platform reference.
9. Review imported analytics and lessons.
10. approve or reject the recommended next mission.

---

## 3. Creating a Mission

A mission request should include:

- objective;
- target customer;
- expected deliverable;
- platform or channel;
- constraints;
- budget;
- deadline if applicable;
- success criteria;
- stop conditions;
- approval requirements.

AuraAI should convert the request into a structured mission proposal before execution.

---

## 4. Approval Decisions

For every approval, the dashboard should show:

- what is being approved;
- current version;
- why approval is required;
- expected next action;
- risks;
- affected artifacts;
- whether the action is reversible.

Available decisions should include:

- approve;
- reject;
- request revision;
- pause;
- cancel.

---

## 5. Content Review

Before approving content:

- confirm facts and claims;
- confirm brand tone;
- confirm target audience;
- check prohibited or risky content;
- check spelling and presentation;
- confirm the artifact version;
- request revisions when needed.

Approval should apply only to the reviewed version.

---

## 6. Publishing Review

Publishing approval means the package is allowed to be published. It does not mean publication has occurred.

Review:

- final media;
- title;
- description;
- thumbnail;
- captions;
- tags;
- platform;
- timing recommendation;
- compliance notes.

After manual publishing, provide:

- platform;
- external post URL or platform ID;
- publication time;
- optional notes.

Only then should AuraAI mark publication as confirmed.

---

## 7. Pause and Resume

Pause when:

- output quality is uncertain;
- a provider behaves unexpectedly;
- costs are rising;
- credentials or external services are unavailable;
- a mission requires a business decision;
- an artifact needs human review.

Resume only after the blocking condition is resolved. AuraAI should continue from verified checkpoints instead of starting from zero.

---

## 8. Failure Handling

When a mission fails, inspect:

- current mission state;
- active or interrupted attempt;
- retry count;
- latest valid checkpoint;
- provider error;
- artifact integrity;
- founder approval state.

Use bounded retry. Do not repeatedly retry an unsafe or expensive step without investigation.

---

## 9. Cost Control

Until AuraAI generates revenue:

- approve free or low-cost providers first;
- reject unnecessary subscriptions;
- require clear justification for paid tools;
- track spending per mission;
- compare provider value;
- stop missions that exceed approved limits.

---

## 10. Git and Milestone Control

For every milestone:

- review the plan;
- approve implementation scope;
- require focused and full tests;
- review modified files;
- require a clean walkthrough;
- commit only after approval;
- tag major milestones;
- push main and the tag;
- confirm a clean working tree.

Do not allow the implementation agent to combine multiple milestones into one unreviewed change.

---

## 11. Emergency Controls

The founder should be able to:

- pause all execution;
- disable new commands;
- cancel a mission;
- disable an employee;
- disable a provider;
- revoke external credentials;
- prevent publishing;
- restore from durable state;
- inspect audit history.

---

## 12. Completion Standard

A mission is not complete merely because an employee returned success.

Completion requires:

- required tasks finished;
- artifacts registered;
- approvals resolved;
- publication confirmed where applicable;
- durable state updated;
- no unresolved recovery issue;
- final result visible in Mission Control.

---

## 13. Founder Principle

Use AuraAI to reduce manual operational work, not to surrender control.

The system should make decisions easier to understand, execution easier to resume, and business experiments safer to run.
