# LLM Inference & Serving

> Status: scaffolded — follow docs/engineering-playbook.md §Adding a new showcase project.

- Problem: <one line>
- Design: [DESIGN.md](DESIGN.md)
- Story: [story.yaml](story.yaml) (served at `/projects/08-inference-serving/story`)

## Reproduce

```bash
uv run python -m inference_serving.cli prepare
uv run python -m inference_serving.cli evaluate
```
