# AuraAI UI Language

Use concise operational nouns and explicit state. Prefer “Founder Approval
Required” over “Pending” when founder action is needed. Never imply that a
person, platform, or provider acted when the system only prepared a plan.

## Standard status labels

- Idle, Working, Waiting, Blocked, Completed, and Failed.
- Review Required, Founder Approval Required, Approved, Rejected, and Revision
  Required.
- Ready to Render, Rendered Locally, Ready to Upload, Uploaded Manually, and
  Metrics Imported.

Internal enum values remain stable. The dashboard presentation mapping converts
them into human-readable labels. Badges pair a visible word with a dot or icon.

Buttons use verbs, empty states explain what is absent without inventing data,
and warnings state both the risk and required action. “Local interface only,”
sample-data labels, approval gates, and manual-publishing language remain
visible wherever relevant.
