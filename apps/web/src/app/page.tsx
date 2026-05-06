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

interface RetryTarget {
  query: string;
  history: ChatMessage[];
  assistantMessageId: string;
}

interface TTSResponse {
  mime_type: string;
  audio_b64: string;
}

function createMessageId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function toRequestHistory(messages: ChatMessage[]) {
  return messages.slice(-MAX_HISTORY_MESSAGES).map(({ role, content }) => ({ role, content }));
}

function audioBlobFromBase64(audioBase64: string, mimeType: string) {
  const binary = window.atob(audioBase64);
  const bytes = new Uint8Array(binary.length);

  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }

  return new Blob([bytes], { type: mimeType });
}

export default function Home() {
  const [isDragging, setIsDragging] = useState(false);
  const [dragCounter, setDragCounter] = useState(0);
  const [retryTargets, setRetryTargets] = useState<Record<string, RetryTarget>>({});
  const [retryingMessageId, setRetryingMessageId] = useState<string | null>(null);
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(null);
  const [loadingSpeechMessageId, setLoadingSpeechMessageId] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const messagesRef = useRef<ChatMessage[]>([]);
  const activeControllerRef = useRef<AbortController | null>(null);
  const speechControllerRef = useRef<AbortController | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    return () => {
      activeControllerRef.current?.abort();
      speechControllerRef.current?.abort();
      audioRef.current?.pause();
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
      }
    };
  }, []);

  const stopSpeech = useCallback(() => {
    speechControllerRef.current?.abort();
    speechControllerRef.current = null;
    audioRef.current?.pause();
    audioRef.current = null;
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
    setSpeakingMessageId(null);
    setLoadingSpeechMessageId(null);
  }, []);

  const sendQuery = useCallback(async (
    query: string,
    mode: "send" | "retry",
    retryTarget?: RetryTarget
  ) => {
    activeControllerRef.current?.abort();

    const controller = new AbortController();
    activeControllerRef.current = controller;
    const userHistory = mode === "retry" && retryTarget
      ? retryTarget.history
      : messagesRef.current;
    const userMessage: ChatMessage = {
      id: createMessageId(),
      role: "user",
      content: query,
    };
    const assistantMessage: ChatMessage = {
      id: mode === "retry" && retryTarget ? retryTarget.assistantMessageId : createMessageId(),
      role: "assistant",
      content: "",
    };
    const requestHistory = toRequestHistory(userHistory);
    const nextRetryTarget = {
      query,
      history: userHistory,
      assistantMessageId: assistantMessage.id,
    };

    setRetryingMessageId(mode === "retry" ? assistantMessage.id : null);
    setIsSending(true);
    setStatusMessage(null);
    setRetryTargets((current) => ({
      ...current,
      [assistantMessage.id]: nextRetryTarget,
    }));

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
        setRetryingMessageId(null);
        setIsSending(false);
      }
    }
  }, []);

  const startNewChat = useCallback(() => {
    activeControllerRef.current?.abort();
    activeControllerRef.current = null;
    stopSpeech();
    setMessages([]);
    setRetryTargets({});
    setStatusMessage(null);
    setMessage("");
    setRetryingMessageId(null);
    setIsSending(false);
    setShowSuggestions(true);
  }, [stopSpeech]);

  const handleRetry = useCallback((assistantMessageId: string) => {
    const retryTarget = retryTargets[assistantMessageId];
    if (!retryTarget || isSending) return;
    stopSpeech();
    void sendQuery(retryTarget.query, "retry", retryTarget);
  }, [isSending, retryTargets, sendQuery, stopSpeech]);

  const handleReadAloud = useCallback(async (assistantMessageId: string, content: string) => {
    if (speakingMessageId === assistantMessageId || loadingSpeechMessageId === assistantMessageId) {
      stopSpeech();
      return;
    }

    stopSpeech();
    const speechController = new AbortController();
    speechControllerRef.current = speechController;
    setLoadingSpeechMessageId(assistantMessageId);
    setStatusMessage(null);

    try {
      const response = await fetch(`${API_BASE_URL}/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: content }),
        signal: speechController.signal,
      });
      const payload = await response.json().catch(() => ({})) as Partial<TTSResponse> & { detail?: string };

      if (!response.ok) {
        throw new Error(payload.detail ?? "Could not read the response aloud.");
      }

      if (!payload.audio_b64 || !payload.mime_type) {
        throw new Error("The speech response did not include audio.");
      }

      const audioUrl = URL.createObjectURL(audioBlobFromBase64(payload.audio_b64, payload.mime_type));
      const audio = new Audio(audioUrl);
      audioRef.current = audio;
      audioUrlRef.current = audioUrl;

      audio.onended = stopSpeech;
      audio.onerror = () => {
        stopSpeech();
        setStatusMessage("Could not play the generated speech.");
      };

      setSpeakingMessageId(assistantMessageId);
      setLoadingSpeechMessageId(null);
      await audio.play();
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      stopSpeech();
      setStatusMessage(error instanceof Error ? error.message : "Could not read the response aloud.");
    } finally {
      if (speechControllerRef.current === speechController) {
        speechControllerRef.current = null;
      }
    }
  }, [loadingSpeechMessageId, speakingMessageId, stopSpeech]);

  const handleMessageSent = useCallback((event: Event) => {
    const detail = (event as CustomEvent<string>).detail;
    if (!detail) return;
    void sendQuery(detail, "send");
  }, [sendQuery]);

  useEffect(() => {
    window.addEventListener("messageSent", handleMessageSent as EventListener);
    return () => window.removeEventListener("messageSent", handleMessageSent as EventListener);
  }, [handleMessageSent]);

  const handleDragEnter = (e: DragEvent<HTMLElement>) => {
    e.preventDefault();
    setDragCounter((prev) => prev + 1);
    if (dragCounter === 0) setIsDragging(true);
  };
  const handleDragLeave = (e: DragEvent<HTMLElement>) => {
    e.preventDefault();
    setDragCounter((prev) => prev - 1);
    if (dragCounter - 1 === 0) setIsDragging(false);
  };
  const handleDrop = (e: DragEvent<HTMLElement>) => {
    e.preventDefault();
    setIsDragging(false);
    setDragCounter(0);
    alert("File uploaded!");
  };

  const handleSuggestionClick = (suggestion: string) => {
    setMessage(suggestion);
    setShowSuggestions(false);
  };

  const hasMessages = messages.length > 0;

  return (
    <main
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      className="relative min-h-screen bg-[#F9FAFB] flex flex-col"
    >
      <div className="w-full max-w-3xl mx-auto px-4 pt-24 pb-40 flex-1 flex flex-col gap-10">

        {/* Hero: only shown on empty state. */}
        {!hasMessages && (
          <div className="text-center mt-10">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Ask anything</h1>
            <p className="text-gray-500">Drop a file anywhere on the page or type below</p>
          </div>
        )}

        {/* Suggestions: hidden once clicked or a chat starts. */}
        {showSuggestions && !hasMessages && (
          <div className="flex flex-wrap justify-center gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => handleSuggestionClick(s)}
                className="px-4 py-2 bg-white border border-gray-200 rounded-full text-sm text-gray-600 hover:border-emerald-400 hover:text-emerald-600 transition-colors shadow-sm"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {/* Messages */}
        {hasMessages && (
          <div className="flex flex-col gap-8">
            {messages.map((chatMessage) => (
              <div
                key={chatMessage.id}
                className={`flex ${chatMessage.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {chatMessage.role === "user" ? (
                  <div className="max-w-[80%] rounded-2xl px-5 py-3 text-base leading-7 bg-emerald-600 text-white">
                    <p className="whitespace-pre-wrap">{chatMessage.content}</p>
                  </div>
                ) : (
                  <div className="w-full">
                    {chatMessage.content ? (
                      <>
                        <MarkdownResponse content={chatMessage.content} />
                        <div className="llm-output-actions" aria-label="Response actions">
                          <CopyTextButton textToCopy={chatMessage.content} />
                          <button
                            type="button"
                            className={`llm-action-button read-aloud-button${speakingMessageId === chatMessage.id ? " speaking" : ""}${loadingSpeechMessageId === chatMessage.id ? " busy" : ""}`}
                            onClick={() => handleReadAloud(chatMessage.id, chatMessage.content)}
                            disabled={Boolean(loadingSpeechMessageId && loadingSpeechMessageId !== chatMessage.id)}
                            aria-label={speakingMessageId === chatMessage.id ? "Stop reading response" : "Read response aloud"}
                            title={speakingMessageId === chatMessage.id ? "Stop reading" : "Read aloud"}
                          >
                            {speakingMessageId === chatMessage.id ? (
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                <rect x="6" y="6" width="12" height="12" rx="1" />
                              </svg>
                            ) : (
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                <path d="M11 5 6 9H2v6h4l5 4V5z" />
                                <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
                                <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
                              </svg>
                            )}
                          </button>
                          <button
                            type="button"
                            className={`llm-action-button try-again-button${retryingMessageId === chatMessage.id ? " busy" : ""}`}
                            onClick={() => handleRetry(chatMessage.id)}
                            disabled={isSending || !retryTargets[chatMessage.id]}
                            aria-label="Try again"
                            title="Try again"
                          >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                              <path d="M4.93 4.93a10 10 0 0 1 14.14 0L18 6" />
                              <path d="M19 1v5h-5" />
                              <path d="M19.07 19.07a10 10 0 0 1-14.14 0L6 18" />
                              <path d="M5 23v-5h5" />
                            </svg>
                          </button>
                        </div>
                      </>
                    ) : (
                      <div className="flex items-center gap-2 text-gray-400 animate-pulse py-1">
                        <div className="w-2 h-2 bg-emerald-400 rounded-full"></div>
                        <div className="w-2 h-2 bg-emerald-400 rounded-full animation-delay-150"></div>
                        <div className="w-2 h-2 bg-emerald-400 rounded-full animation-delay-300"></div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {statusMessage && (
          <div className="text-center text-sm font-medium text-red-600">
            {statusMessage}
          </div>
        )}
      </div>

      {/* Sticky input bar */}
      <div className="fixed bottom-0 left-0 right-0 pointer-events-none">
        <div className="bg-gradient-to-t from-[#F9FAFB] via-[#F9FAFB] to-transparent pt-8 pb-6">
          <div className="w-full max-w-3xl mx-auto px-4 pointer-events-auto">
            <div className="mb-2 flex justify-end">
              <button
                type="button"
                onClick={startNewChat}
                disabled={!hasMessages}
                title={hasMessages ? "Start a new conversation" : "Send a prompt to start a conversation"}
                className="flex items-center gap-2 rounded-full border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-600 shadow-sm transition-all duration-150 hover:border-emerald-400 hover:text-emerald-600 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-gray-200 disabled:hover:text-gray-600 disabled:hover:shadow-sm"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M12 5H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7" />
                  <path d="M18.375 2.625a1 1 0 0 1 3 3l-9.75 9.75L8 17l1.625-3.625z" />
                </svg>
                New chat
              </button>
            </div>
            <MessageInput
              message={message}
              onMessageChange={setMessage}
              isListening={isListening}
              setIsListening={setIsListening}
            />
          </div>
        </div>
      </div>

      {/* Full-screen drag overlay */}
      {isDragging && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-emerald-500/10 backdrop-blur-sm pointer-events-none">
          <div className="px-8 py-6 rounded-2xl border-2 border-dashed border-emerald-500 bg-white/90 shadow-lg">
            <p className="text-lg font-semibold text-emerald-600">Drop file to upload</p>
          </div>
        </div>
      )}
    </main>
  );
}
