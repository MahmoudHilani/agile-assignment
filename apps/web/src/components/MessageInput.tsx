"use client";

import type { KeyboardEvent } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import MediaSelectionButton from "@/components/MediaSelectionButton";
import VoiceWave from "@/components/VoiceWave";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const MAX_RECORDING_SECONDS = 20;

interface MessageInputProps {
  message: string;
  onMessageChange: (message: string) => void;
  isListening?: boolean;
  setIsListening?: (val: boolean) => void;
  canRetry?: boolean;
  isRetrying?: boolean;
  onRetry?: () => void;
}

interface WindowWithWebkitAudioContext extends Window {
  webkitAudioContext?: typeof AudioContext;
}

function mergeAudioBuffers(buffers: Float32Array[]) {
  const totalLength = buffers.reduce((length, buffer) => length + buffer.length, 0);
  const samples = new Float32Array(totalLength);
  let offset = 0;

  for (const buffer of buffers) {
    samples.set(buffer, offset);
    offset += buffer.length;
  }

  return samples;
}

function writeAscii(view: DataView, offset: number, value: string) {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}

function encodeWav(buffers: Float32Array[], sampleRate: number) {
  const samples = mergeAudioBuffers(buffers);
  const bytesPerSample = 2;
  const headerSize = 44;
  const buffer = new ArrayBuffer(headerSize + samples.length * bytesPerSample);
  const view = new DataView(buffer);

  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * bytesPerSample, true);
  writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * bytesPerSample, true);
  view.setUint16(32, bytesPerSample, true);
  view.setUint16(34, 8 * bytesPerSample, true);
  writeAscii(view, 36, "data");
  view.setUint32(40, samples.length * bytesPerSample, true);

  let offset = headerSize;
  for (const sample of samples) {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
    offset += bytesPerSample;
  }

  return new Blob([view], { type: "audio/wav" });
}

export default function MessageInput({
  message,
  onMessageChange,
  setIsListening,
  canRetry = false,
  isRetrying = false,
  onRetry,
}: MessageInputProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingPulse, setRecordingPulse] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [transcriptionError, setTranscriptionError] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioBuffersRef = useRef<Float32Array[]>([]);
  const sampleRateRef = useRef(0);
  const recordingTimeoutRef = useRef<number | null>(null);

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

  const releaseRecordingResources = useCallback(() => {
    if (recordingTimeoutRef.current !== null) {
      window.clearTimeout(recordingTimeoutRef.current);
      recordingTimeoutRef.current = null;
    }
    processorRef.current?.disconnect();
    if (processorRef.current) {
      processorRef.current.onaudioprocess = null;
    }
    sourceRef.current?.disconnect();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    void audioContextRef.current?.close();

    processorRef.current = null;
    sourceRef.current = null;
    streamRef.current = null;
    audioContextRef.current = null;
  }, []);

  useEffect(() => {
    return () => {
      releaseRecordingResources();
    };
  }, [releaseRecordingResources]);

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

  const transcribeRecording = useCallback(async (audio: Blob) => {
    setIsTranscribing(true);
    setTranscriptionError("");

    try {
      const formData = new FormData();
      formData.append("audio", audio, "recording.wav");
      formData.append("locale", "en-US");

      const response = await fetch(`${API_BASE_URL}/voice`, {
        method: "POST",
        body: formData,
      });
      const payload = await response.json().catch(() => ({})) as { text?: string; detail?: string };

      if (!response.ok) {
        throw new Error(payload.detail ?? "Could not transcribe the recording.");
      }

      if (!payload.text) {
        throw new Error("The recording did not contain any transcribed text.");
      }

      onMessageChange(payload.text);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not transcribe the recording.";
      setTranscriptionError(message);
    } finally {
      setIsTranscribing(false);
    }
  }, [onMessageChange]);

  const stopRecording = useCallback(async () => {
    const buffers = audioBuffersRef.current;
    const sampleRate = sampleRateRef.current;

    releaseRecordingResources();
    setIsRecording(false);
    if (setIsListening) setIsListening(false);

    if (buffers.length === 0 || sampleRate === 0) {
      setTranscriptionError("No audio was captured.");
      return;
    }

    audioBuffersRef.current = [];
    sampleRateRef.current = 0;
    await transcribeRecording(encodeWav(buffers, sampleRate));
  }, [releaseRecordingResources, setIsListening, transcribeRecording]);

  const toggleRecording = async () => {
    if (isRecording) {
      await stopRecording();
      return;
    }

    const AudioContextClass = window.AudioContext ?? (window as WindowWithWebkitAudioContext).webkitAudioContext;

    if (!navigator.mediaDevices?.getUserMedia || !AudioContextClass) {
      alert("Voice recording is not supported in this browser.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const audioContext = new AudioContextClass();
      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);

      streamRef.current = stream;
      audioContextRef.current = audioContext;
      sourceRef.current = source;
      processorRef.current = processor;
      audioBuffersRef.current = [];
      sampleRateRef.current = audioContext.sampleRate;
      setTranscriptionError("");

      processor.onaudioprocess = (event) => {
        const input = event.inputBuffer.getChannelData(0);
        audioBuffersRef.current.push(new Float32Array(input));
        event.outputBuffer.getChannelData(0).fill(0);
      };

      source.connect(processor);
      processor.connect(audioContext.destination);
      await audioContext.resume();
      setIsRecording(true);
      if (setIsListening) setIsListening(true);
      recordingTimeoutRef.current = window.setTimeout(() => {
        void stopRecording();
      }, MAX_RECORDING_SECONDS * 1000);
    } catch {
      releaseRecordingResources();
      alert("Microphone access denied. Please allow microphone permissions.");
    }
  };

  const hintText = isRecording
    ? `Recording. ${MAX_RECORDING_SECONDS} second limit.`
    : isTranscribing
      ? "Transcribing audio..."
      : "Enter to send. Shift+Enter for a new line.";

  return (
    <section className="message-composer" aria-label="Message composer">
      <MediaSelectionButton />

      {isRecording ? (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
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
          {hintText}
        </span>
        <div className="button-group">
          <button
            type="button"
            className={`icon-button mic-btn ${isRecording ? "recording" : ""}`}
            onClick={toggleRecording}
            disabled={isTranscribing}
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
            className={`icon-button retry-btn ${isRetrying ? "busy" : ""}`}
            onClick={onRetry}
            disabled={!canRetry || isRetrying}
            aria-label="Try again"
            title="Retry last query"
            data-tooltip="Try again"
          >
            {isRetrying ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="10" opacity="0.25" />
                <path d="M12 2a10 10 0 0 1 10 10" />
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M4.93 4.93a10 10 0 0 1 14.14 0L18 6" />
                <path d="M19 1v5h-5" />
                <path d="M19.07 19.07a10 10 0 0 1-14.14 0L6 18" />
                <path d="M5 23v-5h5" />
              </svg>
            )}
          </button>
          <button
            type="button"
            className={`icon-button send-btn ${message.trim() ? "active" : ""}`}
            onClick={handleSend}
            disabled={!message.trim() || isTranscribing}
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
      {transcriptionError && (
        <p className="voice-error" role="alert">
          {transcriptionError}
        </p>
      )}
    </section>
  );
}
