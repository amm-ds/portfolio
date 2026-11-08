import { useMemo } from "react";
import { ChatSurface } from "./components/chat/ChatSurface";
import { HttpChatApi } from "./lib/chat/client";
import { MockChatApi } from "./lib/chat/mock";
import { getChatSessionId } from "./lib/chat/session";
import { useChat } from "./lib/chat/useChat";

/**
 * Transport wiring: VITE_MOCK=1 runs the scripted mock transport (no backend
 * needed); otherwise talk to the FastAPI SSE endpoint, base URL overridable
 * via VITE_API_BASE and the backend's API key via VITE_API_KEY (sent as
 * X-API-Key when set).
 */
export default function App() {
  const sessionId = useMemo(() => getChatSessionId(), []);
  const api = useMemo(() => {
    if (import.meta.env.VITE_MOCK === "1") return new MockChatApi();
    return new HttpChatApi(import.meta.env.VITE_API_BASE ?? "", {
      apiKey: import.meta.env.VITE_API_KEY,
      sessionId,
    });
  }, [sessionId]);
  const chat = useChat(api);
  return <ChatSurface chat={chat} />;
}
