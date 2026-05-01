"use client";

import type { DragEvent } from "react";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import CopyTextButton from "@/components/CopyTextButton";
import MessageInput from "@/components/MessageInput";

const SUGGESTIONS = [
  "What services does the company offer?",
  "Tell me about the company portfolio",
  "What technologies do you specialize in?",
  "How can I get started with your platform?",
];

const LLM_OUTPUT_TEXT = "LLM OUTPUT DATA";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function Home() {
  const router = useRouter();
  const [isDragging, setIsDragging] = useState(false);
  const [dragCounter, setDragCounter] = useState(0);
  const [lastQuery, setLastQuery] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [statusVariant, setStatusVariant] = useState<"info" | "success" | "error">("info");
  const [isListening, setIsListening] = useState(false);
  const [message, setMessage] = useState("");

  const sendQuery = useCallback(async (query: string, mode: "send" | "retry") => {
    setIsRetrying(mode === "retry");
    setIsSending(true);
    setStatusVariant("info");
    setStatusMessage(mode === "retry" ? "Retrying your previous query..." : "Processing your message...");

    try {
      const response = await fetch(`${API_BASE_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        const message = response.status === 501
          ? "This endpoint is not implemented yet."
          : `${response.status} ${response.statusText}`;
        throw new Error(errorText || message);
      }

      setStatusVariant("success");
      setStatusMessage(mode === "retry" ? "The query was resent successfully." : "The query was sent successfully.");
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown error.";
      setStatusVariant("error");
      setStatusMessage(
        mode === "retry"
          ? `Unable to resend the last query. ${detail}`
          : `Unable to send the query. ${detail}`,
      );
    } finally {
      setIsRetrying(false);
      setIsSending(false);
    }
  }, []);

  const handleMessageSent = useCallback((event: Event) => {
    const detail = (event as CustomEvent<string>).detail;
    if (!detail) return;

    setLastQuery(detail);
    setStatusVariant("info");
    setStatusMessage("Processing your message...");
    void sendQuery(detail, "send");
  }, [sendQuery]);

  useEffect(() => {
    window.addEventListener("messageSent", handleMessageSent as EventListener);
    return () => {
      window.removeEventListener("messageSent", handleMessageSent as EventListener);
    };
  }, [handleMessageSent]);

  const handleRetry = useCallback(() => {
    if (!lastQuery || isRetrying || isSending) return;
    void sendQuery(lastQuery, "retry");
  }, [isRetrying, isSending, lastQuery, sendQuery]);

  useEffect(() => {
    if (!localStorage.getItem("admin_token")) {
      router.push("/login");
    }
  }, [router]);

  const handleDragEnter = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragCounter((prev) => prev + 1);
    if (dragCounter === 0) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragCounter((prev) => prev - 1);
    if (dragCounter - 1 === 0) {
      setIsDragging(false);
    }
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    setDragCounter(0);

    const files = Array.from(e.dataTransfer.files);
    const validTypes = [
      "application/pdf",
      "text/plain",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "image/jpeg",
      "image/png",
      "image/gif",
      "image/webp",
      "image/bmp",
      "image/tiff",
    ];
    const invalidFiles = files.filter((file) => !validTypes.includes(file.type));

    if (invalidFiles.length > 0) {
      alert(`Some files are not valid. Valid formats: docx, pdf, txt, img. Invalid files: ${invalidFiles.map((file) => file.name).join(", ")}`);
    } else {
      alert("Files dropped successfully");
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setMessage(suggestion);
  };

  return (
    <main className="page-root">
      <section
        className="drop-zone"
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        aria-label="Document upload drop zone"
      >
        <h1>Drag files here</h1>
        <p>Valid formats: docx, pdf, txt, jpg, png, gif, webp, bmp, tiff.</p>
        <p className="drop-zone-help">Drop files on the box above to upload.</p>
        {isDragging && (
          <div className="drop-zone-overlay">
            Drop files now
          </div>
        )}
      </section>

      <section className="prompt-suggestions" aria-label="Suggested prompts">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            className="prompt-suggestion"
            onClick={() => handleSuggestionClick(suggestion)}
          >
            {suggestion}
          </button>
        ))}
      </section>

      <MessageInput
        message={message}
        onMessageChange={setMessage}
        isListening={isListening}
        setIsListening={setIsListening}
        canRetry={Boolean(lastQuery) && !isSending}
        isRetrying={isRetrying}
        onRetry={handleRetry}
      />

      {statusMessage ? (
        <p className={`status-text ${statusVariant}`} role="status">
          {statusMessage}
        </p>
      ) : null}

      <div className="copy-button-wrapper">
        <CopyTextButton textToCopy={LLM_OUTPUT_TEXT} />
      </div>
    </main>
  );
}
