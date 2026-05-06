"use client";

import type { DragEvent } from "react";
import { useCallback, useEffect, useState } from "react";
import CopyTextButton from "@/components/CopyTextButton";
import MessageInput from "@/components/MessageInput";
import LoadingAnimation from "../components/LoadingAnimation";
import NewChatButton from "../components/NewChatButton";
import CompanyLogo from "@/components/CompanyLogo";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const SUGGESTIONS = [
  "What services does the company offer?",
  "Tell me about the company portfolio",
  "What technologies do you specialize in?",
  "How can I get started with your platform?",
];

export default function Home() {
  const [isDragging, setIsDragging] = useState(false);
  const [dragCounter, setDragCounter] = useState(0);
  const [lastQuery, setLastQuery] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [message, setMessage] = useState("");
  const [completion, setCompletion] = useState("");
  const [chatKey, setChatKey] = useState(0);

  const [messages, setMessages] = useState<
    { role: "user" | "ai"; text: string }[]
  >([]);

  const [isChatMode, setIsChatMode] = useState(false);

  const sendQuery = useCallback(
    async (query: string, mode: "send" | "retry") => {
      setIsRetrying(mode === "retry");
      setIsSending(true);
      setCompletion("");
      setStatusMessage(null);

      try {
        const response = await fetch(`${API_BASE_URL}/query/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query, top_k: 5 }),
        });

        if (!response.ok)
          throw new Error(`${response.status} ${response.statusText}`);

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        if (!reader) throw new Error("Response body is null");

        let aiText = "";

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          aiText += chunk;
          setCompletion((prev) => prev + chunk);

          // update AI message live
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];

            if (last && last.role === "ai") {
              last.text = aiText;
            } else {
              updated.push({ role: "ai", text: aiText });
            }

            return [...updated];
          });
        }

        setStatusMessage("Message processed.");
      } catch (error) {
        setStatusMessage(
          error instanceof Error ? error.message : "An error occurred."
        );
      } finally {
        setIsRetrying(false);
        setIsSending(false);
      }
    },
    []
  );

  // ✅ FIX 1 — enable chat mode + store user message
  const handleMessageSent = useCallback(
    (event: Event) => {
      const detail = (event as CustomEvent<string>).detail;
      if (!detail) return;

      setIsChatMode(true);

      setMessages((prev) => [
        ...prev,
        { role: "user", text: detail },
      ]);

      setLastQuery(detail);
      void sendQuery(detail, "send");
    },
    [sendQuery]
  );

  useEffect(() => {
    window.addEventListener(
      "messageSent",
      handleMessageSent as EventListener
    );
    return () =>
      window.removeEventListener(
        "messageSent",
        handleMessageSent as EventListener
      );
  }, [handleMessageSent]);

  // ✅ reset also resets chat mode
  const handleNewChat = () => {
    setCompletion("");
    setStatusMessage(null);
    setLastQuery(null);
    setIsSending(false);
    setIsRetrying(false);
    setMessage("");
    setIsDragging(false);
    setDragCounter(0);
    setChatKey((prev) => prev + 1);
    setMessages([]);
    setIsChatMode(false);

    window.dispatchEvent(new CustomEvent("newChat"));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

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
    <>
      <div className="fixed top-4 left-4 z-50">
        <NewChatButton onNewChat={handleNewChat} />
      </div>

      <main className="min-h-screen bg-[#F9FAFB] flex flex-col items-center py-12 px-4">
        <div className="w-full max-w-4xl flex flex-col gap-8">

          {/* HEADER */}
          <div
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            className={`relative border-2 border-dashed rounded-2xl p-10 text-center ${
              isDragging
                ? "border-blue-500 bg-blue-50"
                : "border-gray-200 bg-white"
            }`}
          >
            <div className="flex flex-col items-center gap-3 mb-2">
              <div className="flex items-center gap-3">
                <CompanyLogo />
              </div>
            </div>

            <h1 className="text-3xl font-bold text-gray-900">
              Ask anything
            </h1>

            <p className="text-gray-500">
              Drop a file here or use the input below
            </p>
          </div>

          {/* SUGGESTIONS */}
          <div className="flex flex-wrap justify-center gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => setMessage(s)}
                className="px-4 py-2 bg-white border border-gray-200 rounded-full text-sm text-gray-600 hover:border-blue-400 hover:text-blue-600 shadow-sm"
              >
                {s}
              </button>
            ))}
          </div>

          {/* AI RESPONSE BOX */}
          <div className="bg-white border border-gray-200 rounded-2xl shadow-sm min-h-[250px] flex flex-col">
            <div className="px-6 py-3 border-b bg-gray-50/50 flex justify-between">
              <span className="text-xs font-bold text-gray-400 uppercase">
                AI Response
              </span>
              {completion && !isSending && (
                <CopyTextButton textToCopy={completion} />
              )}
            </div>

            <div className="p-8 flex-1">
              {completion || "Waiting for your question..."}
            </div>
          </div>

          {/* ✅ FIX 2 — CHAT BUBBLES */}
          {isChatMode && (
            <div className="mt-4 flex flex-col gap-3 max-h-[300px] overflow-y-auto">
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex ${
                    msg.role === "user"
                      ? "justify-end"
                      : "justify-start"
                  }`}
                >
                  <div
                     className={`max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed break-words whitespace-pre-wrap ${
                     msg.role === "user"
                     ? "bg-blue-500 text-white"
                        : "bg-gray-200 text-gray-800"
                      }`}
                  >
                    {msg.text}
                  </div>
                </div>
              ))}
            </div>
          )}

          <LoadingAnimation isLoading={isSending} />

          {/* ✅ FIX 3 — INPUT SWITCH */}
          {!isChatMode && (
            <div className="flex flex-col gap-3 w-full max-w-4xl mx-auto">
              <div className="bg-white rounded-2xl shadow-lg border">
                <MessageInput
                  key={chatKey}
                  message={message}
                  onMessageChange={setMessage}
                  isListening={isListening}
                  setIsListening={setIsListening}
                  canRetry={Boolean(lastQuery) && !isSending}
                  isRetrying={isRetrying}
                  onRetry={() => sendQuery(lastQuery!, "retry")}
                />
              </div>
            </div>
          )}

        {isChatMode && (
  <div className="fixed bottom-4 left-1/2 -translate-x-1/2 w-full max-w-4xl px-4">
    <div className="bg-white rounded-2xl shadow-lg border border-gray-200">
                <MessageInput
                  key={chatKey}
                  message={message}
                  onMessageChange={setMessage}
                  isListening={isListening}
                  setIsListening={setIsListening}
                  canRetry={Boolean(lastQuery) && !isSending}
                  isRetrying={isRetrying}
                  onRetry={() => sendQuery(lastQuery!, "retry")}
                />
              </div>
            </div>
          )}

          {statusMessage && (
            <div className="text-center text-sm text-green-600">
              {statusMessage}
            </div>
          )}
        </div>
      </main>
    </>
  );
}