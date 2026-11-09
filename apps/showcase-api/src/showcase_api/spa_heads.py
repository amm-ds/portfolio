"""Per-route <head> content for the served SPA shell.

The SPA catch-all serves the same index.html for every client-side route, so
link-preview bots and non-JS crawlers used to see only the home page's
title/description/canonical/og tags plus an empty <div id="root">. This module
renders route-specific head tags and a <noscript> body from the same
portfolio_core registry the API serves, mirroring the titles/descriptions the
React app's usePageMeta sets client-side. The global social card
(og:image/twitter) is left untouched.
"""

import html
import re
from dataclasses import dataclass
from pathlib import Path

from portfolio_core.logging import get_logger
from portfolio_core.manifest import load_index
from portfolio_core.story import load_story

logger = get_logger("showcase_api.main")

REPO_ROOT = Path(__file__).resolve().parents[4]
PROJECTS_ROOT = REPO_ROOT / "projects"

_BRAND = "alejandromerida.dev"

# Fallback when a project has no story.yaml yet (portfolio.yaml has no summary
# field): one honest sentence derived from the manifest.
_NO_STORY_TEMPLATE = "{title} — a reproducible {domain} case study from the {_brand} portfolio."


@dataclass(frozen=True)
class RouteHead:
    """What a route's <head> and <noscript> body must say."""

    title: str
    description: str
    canonical_path: str
    h1: str
    summary: str


# Hand-authored heads for the non-project routes. Copy mirrors the pages'
# usePageMeta calls so server output and client output agree.
_STATIC_HEADS: dict[str, RouteHead] = {
    "/projects": RouteHead(
        title=f"Demos & Experiments · {_BRAND}",
        description=(
            "Interactive ML demos and reproducible experiment case studies — "
            "forecasting, churn, RAG, optimization and serving."
        ),
        canonical_path="/projects",
        h1="Demos & Experiments",
        summary=(
            "Interactive ML demos and reproducible experiment case studies — "
            "forecasting, churn, RAG, optimization and serving."
        ),
    ),
    # Legacy projects-index path; Caddy 301s it to /projects — the head says
    # so too in case the redirect is ever bypassed.
    "/experiments": RouteHead(
        title=f"Demos & Experiments · {_BRAND}",
        description=(
            "Interactive ML demos and reproducible experiment case studies — "
            "forecasting, churn, RAG, optimization and serving."
        ),
        canonical_path="/projects",
        h1="Demos & Experiments",
        summary=(
            "Interactive ML demos and reproducible experiment case studies — "
            "forecasting, churn, RAG, optimization and serving."
        ),
    ),
    "/services": RouteHead(
        title=f"Services · {_BRAND}",
        description=(
            "Freelance ML/AI engineering offerings — agentic AI & LLM systems, "
            "machine learning, optimization, data engineering, MLOps, interactive "
            "dashboards, full-stack engineering, and APIs & model serving — each "
            "backed by a public, reproducible case study with measured baselines."
        ),
        canonical_path="/services",
        h1="Services",
        summary=(
            "Freelance ML/AI engineering offerings — agentic AI & LLM systems, "
            "machine learning, optimization, data engineering, MLOps, interactive "
            "dashboards, full-stack engineering, and APIs & model serving — each "
            "backed by a public, reproducible case study with measured baselines."
        ),
    ),
    "/about": RouteHead(
        title=f"About · {_BRAND}",
        description=(
            "Alejandro Mérida Maroto — independent ML/AI consultant in Barcelona. "
            "Experience across pharmaceutical AI, network telemetry, manufacturing "
            "analytics, e-commerce retail and venture studios; the working "
            "practices behind every case study."
        ),
        canonical_path="/about",
        h1="About",
        summary=(
            "Alejandro Mérida Maroto — independent ML/AI consultant in Barcelona. "
            "Experience across pharmaceutical AI, network telemetry, manufacturing "
            "analytics, e-commerce retail and venture studios; the working "
            "practices behind every case study."
        ),
    ),
    "/contact": RouteHead(
        title=f"Contact · {_BRAND}",
        description=(
            "Start a conversation about freelance or consulting engagements — "
            "problem, data and timeline."
        ),
        canonical_path="/contact",
        h1="Contact",
        summary=(
            "Start a conversation about freelance or consulting engagements — "
            "problem, data and timeline."
        ),
    ),
    "/glossary": RouteHead(
        title=f"Glossary · {_BRAND}",
        description=(
            "Plain-language definitions — with examples — for the evaluation "
            "terms used across the case studies: baselines, holdouts, WAPE, MASE, "
            "uplift, and more."
        ),
        canonical_path="/glossary",
        h1="Glossary",
        summary=(
            "Plain-language definitions — with examples — for the evaluation "
            "terms used across the case studies: baselines, holdouts, WAPE, MASE, "
            "uplift, and more."
        ),
    ),
    "/apps/agent-chat": RouteHead(
        title=f"Chatbot agent — production template · {_BRAND}",
        description=(
            "A lift-out agent chassis with typed tools, disk-loaded skills, "
            "pgvector retrieval, durable memory, human approvals, deterministic "
            "evaluation, and a streaming React UI."
        ),
        canonical_path="/apps/agent-chat",
        h1="Chatbot agent — production template",
        summary=(
            "A lift-out agent chassis with typed tools, disk-loaded skills, "
            "pgvector retrieval, durable memory, human approvals, deterministic "
            "evaluation, and a streaming React UI."
        ),
    ),
    "/apps/document-intelligence": RouteHead(
        title=f"AI Document Intelligence Workbench · {_BRAND}",
        description=(
            "Page-level PDF analysis: one AI call per page produces cited "
            "summaries, typed entities, and topics, plus page-scoped cited chat "
            "with exact parser-resolved evidence."
        ),
        canonical_path="/apps/document-intelligence",
        h1="AI Document Intelligence Workbench",
        summary=(
            "Page-level PDF analysis: one AI call per page produces cited "
            "summaries, typed entities, and topics, plus page-scoped cited chat "
            "with exact parser-resolved evidence."
        ),
    ),
    # Client-side redirect to /apps/document-intelligence; the head points
    # crawlers straight at the canonical target.
    "/apps/document-review": RouteHead(
        title=f"AI Document Intelligence Workbench · {_BRAND}",
        description=(
            "Page-level PDF analysis: one AI call per page produces cited "
            "summaries, typed entities, and topics, plus page-scoped cited chat "
            "with exact parser-resolved evidence."
        ),
        canonical_path="/apps/document-intelligence",
        h1="AI Document Intelligence Workbench",
        summary=(
            "Page-level PDF analysis: one AI call per page produces cited "
            "summaries, typed entities, and topics, plus page-scoped cited chat "
            "with exact parser-resolved evidence."
        ),
    ),
    "/demos/churn-sandbox": RouteHead(
        title=f"Churn threshold sandbox · {_BRAND}",
        description=(
            "Interactive churn demo: move the alarm threshold and the "
            "missed-churner cost, watch the optimal cutoff and the saved budget "
            "respond."
        ),
        canonical_path="/demos/churn-sandbox",
        h1="Churn threshold sandbox",
        summary=(
            "Interactive churn demo: move the alarm threshold and the "
            "missed-churner cost, watch the optimal cutoff and the saved budget "
            "respond."
        ),
    ),
    "/demos/forecast-workbench": RouteHead(
        title=f"Demand forecast workbench · {_BRAND}",
        description=(
            "Interactive full-panel M5 demand-forecasting demo: compare the "
            "seasonal naive, AutoETS, global and pooled LightGBM arms and the "
            "screened ensemble on the scored-once competition window."
        ),
        canonical_path="/demos/forecast-workbench",
        h1="Demand forecast workbench",
        summary=(
            "Interactive full-panel M5 demand-forecasting demo: compare the "
            "seasonal naive, AutoETS, global and pooled LightGBM arms and the "
            "screened ensemble on the scored-once competition window."
        ),
    ),
}

_PROJECT_ROUTE_RE = re.compile(r"/projects/([^/]+)(?:/report)?\Z")


def _project_head(project_dir: Path, title: str, domain: str) -> RouteHead:
    """Head for one project: story short_version when authored, else a derived
    one-liner. Content problems fall back, never break the shell."""
    description: str | None = None
    try:
        story = load_story(project_dir)
    except Exception as e:  # a bad story.yaml must not 500 the SPA shell
        logger.warning(
            "spa head: %s story unusable (%s); using manifest fallback", project_dir.name, e
        )
        story = None
    if story is not None:
        description = story.short_version
    if not description:
        description = _NO_STORY_TEMPLATE.format(title=title, domain=domain, _brand=_BRAND)
    return RouteHead(
        title=f"{title} · {_BRAND}",
        description=description,
        canonical_path=f"/projects/{project_dir.name}",
        h1=title,
        summary=description,
    )


_PROJECT_HEADS: dict[str, RouteHead] | None = None


def _project_heads() -> dict[str, RouteHead]:
    """Project heads keyed by id, built lazily once per process from the same
    registry the API serves (invalidate by restarting, like the API's startup
    indexes)."""
    global _PROJECT_HEADS
    if _PROJECT_HEADS is None:
        table: dict[str, RouteHead] = {}
        try:
            manifests = load_index(PROJECTS_ROOT)
        except OSError as e:
            logger.warning("spa head: project registry unreadable (%s); static heads only", e)
            manifests = []
        for info in manifests:
            table[info.id] = _project_head(PROJECTS_ROOT / info.id, info.title, info.domain)
        _PROJECT_HEADS = table
    return _PROJECT_HEADS


def route_head(path: str) -> RouteHead | None:
    """The head for one SPA route path, or None to serve the shell as-is."""
    if path in _STATIC_HEADS:
        return _STATIC_HEADS[path]
    match = _PROJECT_ROUTE_RE.fullmatch(path)
    if match:
        return _project_heads().get(match.group(1))
    return None


# --- Shell rendering -----------------------------------------------------------

# The vite build's index.html; the exact instances are substituted per route.
# Base URL comes from the shell's own canonical tag so dev/staging builds that
# gen_sitemap.py baked a different VITE_SITE_URL into stay internally
# consistent.
_BASE_RE = re.compile(r'<link rel="canonical" href="([^"]*)"')
_TAG_SUBSTITUTIONS: list[tuple[str, str]] = [
    ("title", r"<title>.*?</title>"),
    ("description", r'(<meta\s+name="description"\s+content=")[^"]*(")'),
    ("canonical", r'(<link\s+rel="canonical"\s+href=")[^"]*(")'),
    ("og:title", r'(<meta\s+property="og:title"\s+content=")[^"]*(")'),
    ("og:description", r'(<meta\s+property="og:description"\s+content=")[^"]*(")'),
    ("og:url", r'(<meta\s+property="og:url"\s+content=")[^"]*(")'),
]
_ROOT_DIV = '<div id="root"></div>'

_warned_missing_tags: set[str] = set()


def _replace_tag(shell: str, label: str, pattern: str, replacement: str) -> str:
    rendered, count = re.subn(pattern, replacement, shell, count=1, flags=re.DOTALL)
    if count != 1 and label not in _warned_missing_tags:
        _warned_missing_tags.add(label)
        logger.warning("spa head: index.html has no %s tag; serving route heads without it", label)
    return rendered


def inject_head(shell: str, path: str) -> str:
    """index.html with the route's head tags and <noscript> body substituted.

    Unknown routes and shells missing the expected tags are served unchanged
    (a warning is logged once per missing tag — forward-compat guard for a
    future vite build that renames them).
    """
    head = route_head(path)
    if head is None:
        return shell

    base_match = _BASE_RE.search(shell)
    base = base_match.group(1).rstrip("/") if base_match else f"https://{_BRAND}"
    canonical_url = f"{base}{head.canonical_path}"

    rendered = shell
    replacements = {
        "title": f"<title>{html.escape(head.title)}</title>",
        "description": f"\\g<1>{html.escape(head.description)}\\g<2>",
        "canonical": f"\\g<1>{html.escape(canonical_url)}\\g<2>",
        "og:title": f"\\g<1>{html.escape(head.title)}\\g<2>",
        "og:description": f"\\g<1>{html.escape(head.description)}\\g<2>",
        "og:url": f"\\g<1>{html.escape(canonical_url)}\\g<2>",
    }
    for label, pattern in _TAG_SUBSTITUTIONS:
        rendered = _replace_tag(rendered, label, pattern, replacements[label])

    if _ROOT_DIV in rendered:
        noscript = (
            f"{_ROOT_DIV}\n"
            "    <noscript>\n"
            f"      <h1>{html.escape(head.h1)}</h1>\n"
            f"      <p>{html.escape(head.summary)}</p>\n"
            "    </noscript>"
        )
        rendered = rendered.replace(_ROOT_DIV, noscript, 1)
    elif "noscript" not in _warned_missing_tags:
        _warned_missing_tags.add("noscript")
        logger.warning("spa head: index.html has no #root div; skipping <noscript> body")
    return rendered
