"use client";

interface NewChatButtonProps {
  onNewChat: () => void;
}

export default function NewChatButton({ onNewChat }: NewChatButtonProps) {
  return (
    <button
      type="button"
      className="new-chat-btn"
      onClick={onNewChat}
      aria-label="Start a new chat"
      title="New Chat"
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M12 5v14M5 12h14" />
      </svg>
      New Chat
    </button>
  );
}
