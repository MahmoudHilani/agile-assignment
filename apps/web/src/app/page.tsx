'use client';

import { useState } from 'react';
import MediaSelectionButton from "@/components/MediaSelectionButton";

export default function Home() {
  const [isDragging, setIsDragging] = useState(false);
  const [dragCounter, setDragCounter] = useState(0);

  const handleDragEnter = (e) => {
    e.preventDefault();
    setDragCounter(prev => prev + 1);
    if (dragCounter === 0) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setDragCounter(prev => prev - 1);
    if (dragCounter - 1 === 0) {
      setIsDragging(false);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    setDragCounter(0);
    const files = Array.from(e.dataTransfer.files);
    const validTypes = [
      'application/pdf',
      'text/plain',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'image/jpeg',
      'image/png',
      'image/gif',
      'image/webp',
      'image/bmp',
      'image/tiff'
    ];
    const invalidFiles = files.filter(file => !validTypes.includes(file.type));
    if (invalidFiles.length > 0) {
      alert(`Some files are not valid. Valid formats: docx, pdf, txt, img. Invalid files: ${invalidFiles.map(f => f.name).join(', ')}`);
    } else {
      alert('Files dropped successfully');
    }
  };

  return (
    <main
      style={{
        minHeight: '100vh',
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: 'system-ui, sans-serif',
        padding: '24px',
        backgroundColor: '#f8fafc'
      }}
    >
      <div
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        style={{
          width: '360px',
          padding: '28px',
          borderRadius: '18px',
          border: '2px dashed #64748b',
          backgroundColor: '#ffffff',
          boxShadow: '0 18px 40px rgba(15, 23, 42, 0.08)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '16px',
          textAlign: 'center',
          position: 'relative'
        }}
      >
        <h1 style={{ margin: 0, fontSize: '1.25rem', color: '#0f172a' }}>
          Drag files here
        </h1>
        <p style={{ margin: 0, color: '#475569' }}>
          Valid formats: docx, pdf, txt, jpg, png, gif, webp, bmp, tiff.
        </p>
        <p style={{ margin: 0, fontSize: '0.95rem', color: '#64748b' }}>
          Drop files on the box above to upload.
        </p>
        {isDragging && (
          <div style={{
            position: 'absolute',
            inset: 0,
            borderRadius: '18px',
            backgroundColor: 'rgba(99, 102, 241, 0.14)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#0f172a',
            fontSize: '1rem',
            pointerEvents: 'none'
          }}>
            Drop files now
          </div>
        )}
      <div style={{ width: "100%", maxWidth: "700px" }}>
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
          <MediaSelectionButton />
        </div>
      </div>
    </main>
  );
}
