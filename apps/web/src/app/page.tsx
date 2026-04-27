'use client';

import type { DragEvent } from "react";
import { useState } from "react";
import CopyTextButton from "@/components/CopyTextButton";
import MessageInput from "@/components/MessageInput";
import VoiceWave from "@/components/VoiceWave";

const LLM_OUTPUT_TEXT = "LLM OUTPUT DATA";

export default function Home() {
  const [isDragging, setIsDragging] = useState(false);
  const [dragCounter, setDragCounter] = useState(0);
  const [isListening, setIsListening] = useState(false);


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

      <MessageInput />

      <div className="copy-button-wrapper">
        <CopyTextButton textToCopy={LLM_OUTPUT_TEXT} />
      </div>
    </main>
  );
}
