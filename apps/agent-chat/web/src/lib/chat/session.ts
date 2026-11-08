const SESSION_STORAGE_KEY = "agent-chat:session-id";
const CANONICAL_UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Reuse the current tab's session id, replacing missing or malformed values. */
export function getChatSessionId(storage: Storage = window.sessionStorage): string {
  const stored = storage.getItem(SESSION_STORAGE_KEY);
  if (stored !== null && CANONICAL_UUID.test(stored)) return stored;

  const sessionId = crypto.randomUUID();
  storage.setItem(SESSION_STORAGE_KEY, sessionId);
  return sessionId;
}
