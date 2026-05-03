"use client";

import type { DragEvent } from "react";
import { useCallback, useEffect, useState } from "react";
import CopyTextButton from "@/components/CopyTextButton";
import MessageInput from "@/components/MessageInput";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const SUGGESTIONS = [
  "What services does the company offer?",
  "Tell me about the company portfolio",
  "What technologies do you specialize in?",
  "How can I get started with your platform?",
];
const RETRIEVAL_TOP_K = 10;

export default function Home() {
  const [isDragging, setIsDragging] = useState(false);
  const [dragCounter, setDragCounter] = useState(0);
  const [lastQuery, setLastQuery] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [statusVariant, setStatusVariant] = useState<"info" | "success" | "error">("info");
  const [isListening, setIsListening] = useState(false);
  const [message, setMessage] = useState("");
  const [completion, setCompletion] = useState("");
  const statusClassName = statusVariant === "error" ? "text-red-600" : "text-green-600";

  const sendQuery = useCallback(async (query: string, mode: "send" | "retry") => {
    setIsRetrying(mode === "retry");
    setIsSending(true);
    setCompletion(""); 
    setStatusMessage(null);

    try {
      const response = await fetch(`${API_BASE_URL}/query/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, top_k: RETRIEVAL_TOP_K }),
      });

      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("Response body is null");

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        setCompletion((prev) => prev + chunk);
      }
      setStatusVariant("success");
      setStatusMessage("Message processed.");
    } catch (error) {
      setStatusVariant("error");
      setStatusMessage(error instanceof Error ? error.message : "An error occurred.");
    } finally {
      setIsRetrying(false);
      setIsSending(false);
    }
  }, []);

  // Event Listeners
  const handleMessageSent = useCallback((event: Event) => {
    const detail = (event as CustomEvent<string>).detail;
    if (!detail) return;
    setLastQuery(detail);
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

        {/* 3. AI Response Box (The RAG UI) */}
        <div className="bg-white border border-gray-200 rounded-2xl shadow-sm min-h-[250px] flex flex-col relative overflow-hidden">
          {/* Box Header */}
          <div className="px-6 py-3 border-b border-gray-100 bg-gray-50/50 flex justify-between items-center">
            <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">AI Response</span>
            {completion && !isSending && (
              <div className="scale-90 transform-gpu origin-right">
                <CopyTextButton textToCopy={completion} />
              </div>
            )}
          </div>

          {/* Box Content */}
          <div className="p-8 flex-1">
            {isSending && !completion ? (
              <div className="flex items-center gap-2 text-gray-400 animate-pulse">
                <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
                <span>AI is thinking...</span>
              </div>
            ) : completion ? (
              <div className="prose prose-blue max-w-none text-gray-700 leading-relaxed">
                {completion}
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
            onRetry={() => sendQuery(lastQuery!, "retry")}
          />
          
          {statusMessage && (
            <div className={`text-center text-sm font-medium ${statusClassName}`}>
              {statusMessage}
            </div>
          )}
        </div>

      </div>
    </main>
  );
}
