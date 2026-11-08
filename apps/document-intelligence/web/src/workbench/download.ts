export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  // Defer revocation: revoking synchronously can cancel the download in Firefox.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

/** Stable, filesystem-friendly download stem: filename base + short document id. */
export function downloadStem(filename: string, documentId: string): string {
  const base = filename.replace(/\.pdf$/i, "").replaceAll(/[^a-z0-9-_]+/gi, "-").replaceAll(/^-+|-+$/g, "");
  return `${base || "document"}-${documentId.slice(0, 8)}`;
}
