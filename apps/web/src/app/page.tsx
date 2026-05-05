"use client";

import type { DragEvent } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import CopyTextButton from "@/components/CopyTextButton";
import MarkdownResponse from "@/components/MarkdownResponse";
import MessageInput from "@/components/MessageInput";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const SUGGESTIONS = [
  "What services does the company offer?",
  "Tell me about the company portfolio",
  "What technologies do you specialize in?",
  "How can I get started with your platform?",
];
const RETRIEVAL_TOP_K = 10;
const MAX_HISTORY_MESSAGES = 12;

type ChatRole = "user" | "assistant";

interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
}

interface LastQuery {
  query: string;
  history: ChatMessage[];
  assistantMessageId: string;
}

function createMessageId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function toRequestHistory(messages: ChatMessage[]) {
  return messages.slice(-MAX_HISTORY_MESSAGES).map(({ role, content }) => ({ role, content }));
}

export default function Home() {
  const [isDragging, setIsDragging] = useState(false);
  const [dragCounter, setDragCounter] = useState(0);
  const [lastQuery, setLastQuery] = useState<LastQuery | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const messagesRef = useRef<ChatMessage[]>([]);
  const activeControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    return () => activeControllerRef.current?.abort();
  }, []);

  const sendQuery = useCallback(async (query: string, mode: "send" | "retry") => {
    activeControllerRef.current?.abort();

    const controller = new AbortController();
    activeControllerRef.current = controller;
    const userHistory = mode === "retry" && lastQuery
      ? lastQuery.history
      : messagesRef.current;
    const userMessage: ChatMessage = {
      id: createMessageId(),
      role: "user",
      content: query,
    };
    const assistantMessage: ChatMessage = {
      id: mode === "retry" && lastQuery ? lastQuery.assistantMessageId : createMessageId(),
      role: "assistant",
      content: "",
    };
    const requestHistory = toRequestHistory(userHistory);

    setIsRetrying(mode === "retry");
    setIsSending(true);
    setStatusMessage(null);
    setLastQuery({
      query,
      history: userHistory,
      assistantMessageId: assistantMessage.id,
    });

    if (mode === "retry") {
      setMessages((current) =>
        current.map((chatMessage) =>
          chatMessage.id === assistantMessage.id
            ? { ...chatMessage, content: "" }
            : chatMessage
        )
      );
    } else {
      setMessages((current) => [...current, userMessage, assistantMessage]);
    }

    try {
      const response = await fetch(`${API_BASE_URL}/query/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          top_k: RETRIEVAL_TOP_K,
          history: requestHistory,
        }),
        signal: controller.signal,
      });

      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("Response body is null");

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        setMessages((current) =>
          current.map((chatMessage) =>
            chatMessage.id === assistantMessage.id
              ? { ...chatMessage, content: chatMessage.content + chunk }
              : chatMessage
          )
        );
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setStatusMessage(error instanceof Error ? error.message : "An error occurred.");
    } finally {
      if (activeControllerRef.current === controller) {
        activeControllerRef.current = null;
        setIsRetrying(false);
        setIsSending(false);
      }
    }
  }, [lastQuery]);

  const startNewChat = useCallback(() => {
    activeControllerRef.current?.abort();
    activeControllerRef.current = null;
    setMessages([]);
    setLastQuery(null);
    setStatusMessage(null);
    setMessage("");
    setIsRetrying(false);
    setIsSending(false);
  }, []);

  // Event Listeners
  const handleMessageSent = useCallback((event: Event) => {
    const detail = (event as CustomEvent<string>).detail;
    if (!detail) return;
    void sendQuery(detail, "send");
  }, [sendQuery]);

  useEffect(() => {
    window.addEventListener("messageSent", handleMessageSent as EventListener);
    return () => window.removeEventListener("messageSent", handleMessageSent as EventListener);
  }, [handleMessageSent]);

  // Drag & Drop Handlers
  const handleDragEnter = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragCounter((prev) => prev + 1);
    if (dragCounter === 0) setIsDragging(true);
  };
  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragCounter((prev) => prev - 1);
    if (dragCounter - 1 === 0) setIsDragging(false);
  };
  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    setDragCounter(0);
    alert("File uploaded!");
  };

  return (
    <main className="min-h-screen bg-[#F9FAFB] flex flex-col items-center px-4 pb-12 pt-28">
      <div className="w-full max-w-4xl flex flex-col gap-8">
        
        {/* 1. Header & Dropzone */}
        <div
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          className={`relative border-2 border-dashed rounded-2xl p-10 transition-all text-center ${
            isDragging ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-white"
          }`}
        >
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Ask anything</h1>
          <p className="text-gray-500">Drop a file here or use the input below</p>
        </div>

        {/* 2. Suggestions */}
        <div className="flex flex-wrap justify-center gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => setMessage(s)}
              className="px-4 py-2 bg-white border border-gray-200 rounded-full text-sm text-gray-600 hover:border-blue-400 hover:text-blue-600 transition-colors shadow-sm"
            >
              {s}
            </button>
          ))}
        </div>

        {/* 3. Conversation Box (The RAG UI) */}
        <div className="bg-white border border-gray-200 rounded-2xl shadow-sm min-h-[250px] flex flex-col relative overflow-hidden">
          {/* Box Header */}
          <div className="px-6 py-3 border-b border-gray-100 bg-gray-50/50 flex justify-between items-center">
            <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">Conversation</span>
            <div className="flex items-center gap-3">
              {messages.some((chatMessage) => chatMessage.role === "assistant" && chatMessage.content) && !isSending && (
                <div className="scale-90 transform-gpu origin-right">
                  <CopyTextButton
                    textToCopy={messages
                      .filter((chatMessage) => chatMessage.role === "assistant" && chatMessage.content)
                      .map((chatMessage) => chatMessage.content)
                      .join("\n\n")}
                  />
                </div>
              )}
              <button
                type="button"
                onClick={startNewChat}
                disabled={messages.length === 0 && !statusMessage && !message}
                className="px-3 py-2 rounded-lg border border-gray-200 bg-white text-xs font-semibold text-gray-600 hover:border-blue-300 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                New chat
              </button>
            </div>
          </div>

          {/* Box Content */}
          <div className="p-6 flex-1">
            {messages.length > 0 ? (
              <div className="flex flex-col gap-5">
                {messages.map((chatMessage) => (
                  <div
                    key={chatMessage.id}
                    className={`flex ${chatMessage.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[85%] rounded-xl px-4 py-3 text-sm leading-6 ${
                        chatMessage.role === "user"
                          ? "bg-blue-600 text-white"
                          : "border border-gray-100 bg-gray-50 text-gray-700"
                      }`}
                    >
                      {chatMessage.content ? (
                        chatMessage.role === "assistant" ? (
                          <MarkdownResponse content={chatMessage.content} />
                        ) : (
                          <p className="whitespace-pre-wrap">{chatMessage.content}</p>
                        )
                      ) : (
                        <div className="flex items-center gap-2 text-gray-400 animate-pulse">
                          <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
                          <span>AI is thinking...</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-gray-300 italic text-sm">
                Waiting for your question...
              </div>
            )}
          </div>
        </div>

        {/* 4. Input Area */}
        <div className="flex flex-col gap-3 w-full max-w-4xl mx-auto">
          <MessageInput
            message={message}
            onMessageChange={setMessage}
            isListening={isListening}
            setIsListening={setIsListening}
            canRetry={Boolean(lastQuery) && !isSending}
            isRetrying={isRetrying}
            onRetry={() => lastQuery && sendQuery(lastQuery.query, "retry")}
          />
          
          {statusMessage && (
            <div className="text-center text-sm font-medium text-red-600">
              {statusMessage}
            </div>
          )}
        </div>

      </div>
    </main>
  );
}
