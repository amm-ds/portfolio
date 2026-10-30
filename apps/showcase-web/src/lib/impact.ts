import { STORY_SHORT } from "./storyShort";

/** Short "what it achieves" copy for a project — the story's generated
 * `short_version` (scripts/gen_story_short.py bakes every story.yaml into
 * lib/storyShort.ts through the same loader the showcase API uses). This is
 * the single plain-text source for project-card copy, ProjectDetail SEO
 * descriptions, README rows, docs openings, and social text — there is no
 * hand-maintained fallback map. */
export function summaryLine(projectId: string): string | undefined {
  return STORY_SHORT[projectId] ?? undefined;
}
