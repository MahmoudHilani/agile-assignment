"use client";

interface PdfUploadZoneProps {
  onPdfUpload: (file: File) => void;
}

export default function PdfUploadZone({ onPdfUpload }: PdfUploadZoneProps) {
  return (
    <div
      style={{
        border: "2px dashed #d1d5db",
        borderRadius: "12px",
        padding: "24px",
        textAlign: "center",
        color: "#6b7280",
        fontSize: "14px",
        background: "#fafafa",
      }}
    >
      <p>Drag & drop a PDF here or use the + button to upload</p>
    </div>
  );
}
