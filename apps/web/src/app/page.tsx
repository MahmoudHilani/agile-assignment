"use client";
import { useState, useCallback } from "react";
import MediaSelectionButton from "@/components/MediaSelectionButton";

const SUGGESTIONS = [
  "What services does the company offer?",
  "Tell me about the company portfolio",
  "What technologies do you specialize in?",
  "How can I get started with your platform?",
];

export default function Home() {
  const [input, setInput] = useState("");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleSuggestionClick = (suggestion: string) => {
    setInput(suggestion);
  };

  const handlePdfUpload = (file: File) => {
    if (file.type !== "application/pdf") {
      setPdfError("Only PDF files are supported.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setPdfError("PDF is too large. Max size is 10MB.");
      return;
    }
    setPdfError(null);
    setPdfFile(file);
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handlePdfUpload(file);
  }, []);

  return (
    <main
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "flex-end",
        height: "100vh",
        padding: "2rem",
        background: isDragging ? "#f0fdf4" : "#f9fafb",
        transition: "background 0.2s",
        border: isDragging ? "2px dashed #22c55e" : "2px dashed transparent",
      }}
    >
      <div style={{ width: "100%", maxWidth: "700px", display: "flex", flexDirection: "column", gap: "12px" }}>

        {isDragging && (
          <div style={{ textAlign: "center", color: "#16a34a", fontWeight: 600, fontSize: "16px" }}>
            Drop your PDF here!
          </div>
        )}

        {pdfFile && (
          <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "8px 16px", background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: "999px", width: "fit-content" }}>
            <span style={{ fontSize: "13px", color: "#1d4ed8" }}>📄 {pdfFile.name}</span>
            <button onClick={() => setPdfFile(null)} style={{ background: "none", border: "none", cursor: "pointer", color: "#3b82f6", fontSize: "16px" }}>×</button>
          </div>
        )}

        {pdfError && (
          <div style={{ color: "#dc2626", fontSize: "13px", padding: "8px 16px", background: "#fef2f2", borderRadius: "8px", border: "1px solid #fecaca" }}>
            ⚠️ {pdfError}
          </div>
        )}

        {input === "" && !pdfFile && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", justifyContent: "center" }}>
            {SUGGESTIONS.map((suggestion, i) => (
              <button
                key={i}
                onClick={() => handleSuggestionClick(suggestion)}
                style={{
                  padding: "8px 16px",
                  background: "#ffffff",
                  border: "1.5px solid #e5e7eb",
                  borderRadius: "999px",
                  fontSize: "14px",
                  color: "#374151",
                  cursor: "pointer",
                  boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
                }}
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "12px 16px",
            border: "1.5px solid #e5e7eb",
            borderRadius: "999px",
            width: "100%",
            background: "#fff",
            boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
          }}
        >
          <MediaSelectionButton onPdfSelected={handlePdfUpload} />
          <input
            type="text"
            placeholder="Start asking..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            style={{
              flex: 1,
              border: "none",
              outline: "none",
              fontSize: "15px",
              background: "transparent",
              color: "#374151",
            }}
          />
          {input && (
            <button
              onClick={() => setInput("")}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                color: "#9ca3af",
                fontSize: "18px",
                padding: "0 4px",
              }}
            >
              ×
            </button>
          )}
        </div>
      </div>
    </main>
  );
}
