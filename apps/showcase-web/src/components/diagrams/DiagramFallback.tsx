export function DiagramFallback({ specId, reason = "Diagram preview unavailable." }: { specId: string; reason?: string }) {
  return (
    <pre className="code-block flow-diagram-fallback">
      <code>{`diagram ${specId}\n\n${reason}`}</code>
    </pre>
  );
}
