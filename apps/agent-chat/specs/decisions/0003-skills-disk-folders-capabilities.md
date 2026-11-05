# ADR-0003: Skills as disk folders with Capability progressive disclosure

- **Status:** Accepted
- **Date:** 2026-11-05

## Context

An adaptable agent needs a place for domain playbooks ("answer refund
questions only from the handbook", "compress long texts with the tool"). These
must be editable by someone who writes markdown, not framework code, and the
agent's context budget must not pay for every playbook on every turn. The
alternative — skills as Python modules that inject instructions at assembly
time — makes the model read all skills always and couples authorship to code.

## Decision

A skill is a **folder on disk** with one convention
(`agent_chat.capabilities.loader`):

```
skills/<name>/SKILL.md        instructions; the first prose paragraph is the
                              description the model sees
skills/<name>/resources/*.md  optional reference documents
```

- The loader builds one pydantic-ai `Capability` per folder, always with
  `defer_loading=True`: the model sees only id + description until it calls
  `load_capability("<name>")`, at which point the instructions and tools
  enter the run — **progressive disclosure by construction**, not by prompt
  hygiene.
- A folder with `resources/` automatically gets a deterministic keyword-search
  tool named `search_<name>` over those documents — no per-skill code. Ranking
  is keyword overlap with a stopword list: deterministic, embeddable nowhere,
  and good enough for a skill's own reference shelf.
- A skill that needs a bespoke tool (the shipped `summarize` and its
  `summarize_text`) registers one builder in `EXTRA_TOOL_BUILDERS` — adding
  one is one line.
- Folders without a `SKILL.md` are skipped, so `resources/` and friends can
  live anywhere under the skills root. The skills directory is a setting
  (`AGENT_CHAT_SKILLS_DIR`).

## Consequences

- Adding a skill is adding a folder; deleting one is deleting it. No registry
  to maintain, no code review needed for a wording change.
- Context stays small: two short description lines per skill until the model
  loads one, which the eval suite pins (`handbook-*` cases assert the
  load-then-search sequence).
- Skill search is lexical on purpose — embeddings stay the RAG pipeline's
  job (ADR-0002). A skill whose documents need semantic search belongs in the
  vector store instead, via the `retrieve` tool.
- The failure mode is honest: an empty `search_<name>` result means the skill
  does not cover the topic, and the shipped instructions tell the model to
  say exactly that instead of guessing.
