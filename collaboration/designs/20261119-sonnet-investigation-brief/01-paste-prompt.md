# Paste prompt for the top-level Sonnet investigation

Read `collaboration/agents/00-init-senior-reviewer.md` and `collaboration/designs/20261119-sonnet-investigation-brief/00-brief.md` in full before you start.

Investigate where each experiment (01–13) and each app (agent-chat, document-intelligence) can be improved or refined. For each one: the current state from the committed metrics, the gap to the state of the art checked online, the approaches that would close the gap, and the references for each approach.

Rules:
- Check online with WebSearch (standard first; extended only if standard results are thin, off-target or out of date). Record queries and dates.
- Label every external claim source-backed, secondary or gap. Mark conflicts unresolved; do not pick one.
- No hosted model calls, no implementation edits, no git mutations, no deploys, no changes to committed records.
- Do not propose changing existing numbers; propose the experiment that would produce a new one.

Write the output to `collaboration/reviews/20261119-sonnet-investigation/`:
- `00-summary.md` with one ranked table across all projects;
- `01-…` to `13-…` one per project, and `14-agent-chat.md`, `15-document-intelligence.md`;
- `99-sources.md` with every URL, its label and the claim it supports.

Stop and report if a finding would change a headline number or a committed record. End with the list of unresolved conflicts.
