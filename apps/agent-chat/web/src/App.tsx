import { useMemo } from "react";
import { ChatSurface } from "./components/chat/ChatSurface";
import { HttpChatApi } from "./lib/chat/client";
import { MockChatApi } from "./lib/chat/mock";
import { useChat } from "./lib/chat/useChat";

/**
 * Transport wiring: VITE_MOCK=1 runs the scripted mock transport (no backend
 * needed); otherwise talk to the FastAPI SSE endpoint, base URL overridable
 * via VITE_API_BASE.
 */
export default function App() {
  const api = useMemo(() => {
    if (import.meta.env.VITE_MOCK === "1") return new MockChatApi();
    return new HttpChatApi(import.meta.env.VITE_API_BASE ?? "");
  }, []);
  const chat = useChat(api);
  return <ChatSurface chat={chat} />;
}
