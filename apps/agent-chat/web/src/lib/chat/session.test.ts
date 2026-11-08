import { describe, expect, it } from "vitest";
import { getChatSessionId } from "./session";

const STORAGE_KEY = "agent-chat:session-id";
const STORED_ID = "123e4567-e89b-42d3-a456-426614174000";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function memoryStorage(initial: Record<string, string> = {}): Storage {
  const values = new Map(Object.entries(initial));
  return {
    get length() {
      return values.size;
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => Array.from(values.keys())[index] ?? null,
    removeItem: (key) => {
      values.delete(key);
    },
    setItem: (key, value) => {
      values.set(key, value);
    },
  };
}

describe("getChatSessionId", () => {
  it("reuses a valid id already stored for the tab", () => {
    const storage = memoryStorage({ [STORAGE_KEY]: STORED_ID });

    expect(getChatSessionId(storage)).toBe(STORED_ID);
    expect(getChatSessionId(storage)).toBe(STORED_ID);
    expect(storage.getItem(STORAGE_KEY)).toBe(STORED_ID);
  });

  it("creates and stores an id when session storage is empty", () => {
    const storage = memoryStorage();

    const sessionId = getChatSessionId(storage);

    expect(sessionId).toMatch(UUID);
    expect(storage.getItem(STORAGE_KEY)).toBe(sessionId);
    expect(getChatSessionId(storage)).toBe(sessionId);
  });

  it("generates different ids for separate session storage areas", () => {
    expect(getChatSessionId(memoryStorage())).not.toBe(getChatSessionId(memoryStorage()));
  });

  it.each(["not-a-uuid", "123e4567-e89b-42d3-a456-426614174000\r\nX-Injected: yes", ""])(
    "replaces invalid stored value %j",
    (invalid) => {
      const storage = memoryStorage({ [STORAGE_KEY]: invalid });

      const sessionId = getChatSessionId(storage);

      expect(sessionId).toMatch(UUID);
      expect(sessionId).not.toBe(invalid);
      expect(storage.getItem(STORAGE_KEY)).toBe(sessionId);
    },
  );
});
