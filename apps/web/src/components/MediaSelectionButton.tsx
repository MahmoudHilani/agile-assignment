"use client";

import { useRef, useState } from "react";

type MediaType = "image" | "document" | "audio" | "video" | "pdf";

interface MediaOption {
  type: MediaType;
  label: string;
  accept: string;
  icon: React.ReactNode;
}

const MEDIA_OPTIONS: MediaOption[] = [
  {
    type: "pdf",
    label: "PDF",
    accept: "application/pdf",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
      </svg>
    ),
  },
  {
    type: "image",
    label: "Image",
    accept: "image/*",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
        <circle cx="8.5" cy="8.5" r="1.5" />
        <polyline points="21 15 16 10 5 21" />
      </svg>
    ),
  },
  {
    type: "document",
    label: "Document",
    accept: ".doc,.docx,.txt,.md",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
      </svg>
    ),
  },
  {
    type: "audio",
    label: "Audio",
    accept: "audio/*",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 18V5l12-2v13" />
        <circle cx="6" cy="18" r="3" />
        <circle cx="18" cy="16" r="3" />
      </svg>
    ),
  },
  {
    type: "video",
    label: "Video",
    accept: "video/*",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="23 7 16 12 23 17 23 7" />
        <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
      </svg>
    ),
  },
];

interface SelectedFile {
  type: MediaType;
  file: File;
}

interface MediaSelectionButtonProps {
  onFileSelected?: (selected: SelectedFile) => void;
  onPdfSelected?: (file: File) => void;
}

export default function MediaSelectionButton({ onFileSelected, onPdfSelected }: MediaSelectionButtonProps) {
  const [open, setOpen] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<SelectedFile[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const currentTypeRef = useRef<MediaOption | null>(null);

  const handleOptionClick = (option: MediaOption) => {
    currentTypeRef.current = option;
    setOpen(false);
    if (fileInputRef.current) {
      fileInputRef.current.accept = option.accept;
      fileInputRef.current.click();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !currentTypeRef.current) return;
    if (currentTypeRef.current.type === "pdf" && onPdfSelected) {
      onPdfSelected(file);
    } else {
      const selected: SelectedFile = { type: currentTypeRef.current.type, file };
      setSelectedFiles((prev) => [...prev, selected]);
      onFileSelected?.(selected);
    }
    e.target.value = "";
  };

  const removeFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      {selectedFiles.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
          {selectedFiles.map((sf, i) => (
            <div key={i} className="media-chip">
              <span className="media-chip-icon">
                {MEDIA_OPTIONS.find((o) => o.type === sf.type)?.icon}
              </span>
              <span className="media-chip-name">{sf.file.name}</span>
              <button className="media-chip-remove" onClick={() => removeFile(i)}>×</button>
            </div>
          ))}
        </div>
      )}

      <div className="media-dropdown-container">
        <button
          className="media-selection-btn-plus"
          onClick={() => setOpen((v) => !v)}
          aria-label="Attach media"
        >
          +
        </button>

        {open && (
          <>
            <div className="media-backdrop" onClick={() => setOpen(false)} />
            <ul className="media-dropdown" role="listbox">
              {MEDIA_OPTIONS.map((option) => (
                <li key={option.type} role="option" className="media-dropdown-item" onClick={() => handleOptionClick(option)}>
                  <span className="media-item-icon">{option.icon}</span>
                  <span>{option.label}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      <input ref={fileInputRef} type="file" style={{ display: "none" }} onChange={handleFileChange} />
    </div>
  );
}
