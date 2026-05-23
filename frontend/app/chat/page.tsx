import { AppShell } from "@/components/product/app-shell";
import { ChatInterface } from "@/components/product/chat-interface";

export default function ChatPage() {
  return (
    <AppShell active="chat">
      <ChatInterface />
    </AppShell>
  );
}
