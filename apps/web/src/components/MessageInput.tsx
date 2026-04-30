"use client";

import type { KeyboardEvent } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import MediaSelectionButton from "@/components/MediaSelectionButton";
import VoiceWave from "@/components/VoiceWave";

interface MessageInputProps {
  message: string;
  onMessageChange: (message: string) => void;
  isListening?: boolean;
  setIsListening?: (val: boolean) => void;
}

export default function MessageInput({ 
  message, 
  onMessageChange, 
  isListening, 
  setIsListening 
}: MessageInputProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingPulse, setRecordingPulse] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }, [message]);

  useEffect(() => {
    if (!isRecording) return;

    const interval = window.setInterval(() => {
      setRecordingPulse((current) => !current);
    }, 600);

    return () => window.clearInterval(interval);
  }, [isRecording]);

  useEffect(() => {
    return () => {
      mediaRecorderRef.current?.stop();
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  const handleSend = useCallback(() => {
    const trimmed = message.trim();
    if (!trimmed) return;

    window.dispatchEvent(new CustomEvent("messageSent", { detail: trimmed }));
    onMessageChange("");
  }, [message, onMessageChange]);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
    if (setIsListening) setIsListening(false);
  };

  const toggleRecording = async () => {
    if (isRecording) {
      stopRecording();
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      alert("Voice recording is not supported in this browser.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);

      streamRef.current = stream;
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;

        if (chunksRef.current.length > 0) {
          const blob = new Blob(chunksRef.current, { type: "audio/webm" });
          window.dispatchEvent(new CustomEvent("audioRecorded", { detail: blob }));
          onMessageChange("Voice message recorded");
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);
      if (setIsListening) setIsListening(true);
    } catch {
      alert("Microphone access denied. Please allow microphone permissions.");
    }
  };

  return (
    <section className="message-composer" aria-label="Message composer">
      <MediaSelectionButton />
      
      {isRecording ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <VoiceWave isListening={isRecording} />
        </div>
      ) : (
        <textarea
          ref={textareaRef}
          className="message-textarea"
          placeholder="Type your message..."
          value={message}
          onChange={(event) => onMessageChange(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          aria-label="Message input"
        />
      )}

      <div className="composer-actions">
        <span className="hint-text">
          {isRecording ? "Recording. Press stop when done." : "Enter to send. Shift+Enter for a new line."}
        </span>
        <div className="button-group">
          <button
            type="button"
            className={`icon-button mic-btn ${isRecording ? "recording" : ""}`}
            onClick={toggleRecording}
            aria-label={isRecording ? "Stop recording" : "Record voice message"}
            title={isRecording ? "Stop recording" : "Record voice message"}
          >
            {isRecording ? (
              <span className={`stop-icon ${recordingPulse ? "pulse" : ""}`} aria-hidden="true" />
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
            )}
          </button>
          <button
            type="button"
            className={`icon-button send-btn ${message.trim() ? "active" : ""}`}
            onClick={handleSend}
            disabled={!message.trim()}
            aria-label="Send message"
            title="Send message"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>
    </section>
  );
}