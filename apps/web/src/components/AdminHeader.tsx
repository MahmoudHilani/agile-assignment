"use client";

import type { DragEvent, FormEvent } from "react";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAdminAuth } from "@/context/AdminAuthContext";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const MAX_FILE_BYTES = 10 * 1024 * 1024;
const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt"];

type ReplaceStatus = "idle" | "uploading" | "success" | "error";

function UploadIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  );
}

function FileIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  );
}

export default function AdminHeader() {
  const router = useRouter();
  const { isAdmin, token, logout } = useAdminAuth();

  const [showUpload, setShowUpload] = useState(false);
  const [replaceFile, setReplaceFile] = useState<File | null>(null);
  const [replaceStatus, setReplaceStatus] = useState<ReplaceStatus>("idle");
  const [replaceError, setReplaceError] = useState("");
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const applyFile = (file: File | null) => {
    setReplaceFile(file);
    setReplaceStatus("idle");
    setReplaceError("");
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    applyFile(e.target.files?.[0] ?? null);
  };

  const handlePickerDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDraggingOver(false);
    const file = e.dataTransfer.files[0] ?? null;
    applyFile(file);
  };

  const handlePickerDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDraggingOver(true);
  };

  const handlePickerDragLeave = () => setIsDraggingOver(false);

  const clearFile = () => {
    applyFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleReplaceSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!replaceFile || !token) return;

    const ext = replaceFile.name.slice(replaceFile.name.lastIndexOf(".")).toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setReplaceStatus("error");
      setReplaceError(`Invalid file type. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`);
      return;
    }

    if (replaceFile.size > MAX_FILE_BYTES) {
      setReplaceStatus("error");
      setReplaceError("File exceeds the 10 MB limit.");
      return;
    }

    setReplaceStatus("uploading");
    setReplaceError("");

    try {
      const formData = new FormData();
      formData.append("file", replaceFile);

      const res = await fetch(`${API_BASE_URL}/documents`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({})) as { detail?: string };
        throw new Error(data.detail ?? "Upload failed");
      }

      setReplaceStatus("success");
      setReplaceFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      setReplaceStatus("error");
      setReplaceError(err instanceof Error ? err.message : "Upload failed");
    }
  };

  if (isAdmin) {
    return (
      <div className="ml-auto flex items-center gap-3">
        <span className="rounded-full border border-slate-300 bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">Admin</span>

        <div className="relative">
          <button
            type="button"
            className="rounded-lg border-2 border-blue-600 bg-transparent px-3.5 py-2 text-sm text-blue-600 transition-colors hover:bg-blue-50"
            onClick={() => setShowUpload((v) => !v)}
            aria-expanded={showUpload}
          >
            Replace Doc
          </button>

          {showUpload && (
            <div className="absolute right-0 top-[calc(100%+10px)] z-50 flex min-w-80 flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-xl">
              <p className="text-sm font-bold text-slate-900">Replace Company Document</p>

              <form onSubmit={handleReplaceSubmit} className="flex flex-col gap-2.5">
                {/* Hidden native input */}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.txt"
                  className="file-picker-hidden"
                  onChange={handleFileChange}
                  aria-label="Select document to upload"
                />

                {/* Custom picker zone */}
                <div
                  className={`file-picker-zone${isDraggingOver ? " dragging" : ""}${replaceFile ? " has-file" : ""}`}
                  onClick={() => !replaceFile && fileInputRef.current?.click()}
                  onDragOver={handlePickerDragOver}
                  onDragLeave={handlePickerDragLeave}
                  onDrop={handlePickerDrop}
                  role="button"
                  tabIndex={replaceFile ? -1 : 0}
                  onKeyDown={(e) => e.key === "Enter" && !replaceFile && fileInputRef.current?.click()}
                  aria-label="File drop zone"
                >
                  {replaceFile ? (
                    <div className="file-picker-selected">
                      <span className="file-picker-file-icon"><FileIcon /></span>
                      <span className="file-picker-name" title={replaceFile.name}>
                        {replaceFile.name}
                      </span>
                      <button
                        type="button"
                        className="file-picker-clear"
                        onClick={(e) => { e.stopPropagation(); clearFile(); }}
                        aria-label="Remove selected file"
                      >
                        ✕
                      </button>
                    </div>
                  ) : (
                    <>
                      <span className="file-picker-upload-icon"><UploadIcon /></span>
                      <span className="file-picker-prompt">
                        {isDraggingOver ? "Drop to select" : "Click to browse or drag & drop"}
                      </span>
                      <span className="file-picker-hint">PDF, DOCX or TXT · max 10 MB</span>
                    </>
                  )}
                </div>

                <button
                  type="submit"
                  className="w-full rounded-lg border-0 bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={!replaceFile || replaceStatus === "uploading"}
                >
                  {replaceStatus === "uploading" ? "Uploading…" : "Upload Document"}
                </button>
              </form>

              {replaceStatus === "success" && (
                <p className="text-sm text-green-700" role="status">
                  Document replaced successfully.
                </p>
              )}
              {replaceStatus === "error" && (
                <p className="text-sm text-red-700" role="alert">
                  {replaceError}
                </p>
              )}
            </div>
          )}
        </div>

        <button type="button" className="rounded-lg border-2 border-slate-300 bg-transparent px-3.5 py-2 text-sm text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900" onClick={logout}>
          Logout
        </button>
      </div>
    );
  }

  return (
    <div className="ml-auto flex items-center gap-3">
      <button type="button" className="rounded-lg border-2 border-blue-600 bg-transparent px-3.5 py-2 text-sm text-blue-600 transition-colors hover:bg-blue-50" onClick={() => router.push("/login")}>
        Admin Login
      </button>
    </div>
  );
}
