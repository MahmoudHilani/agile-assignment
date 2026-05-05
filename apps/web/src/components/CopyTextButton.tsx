"use client";

import { useState } from "react";

interface CopyButtonProps {
  textToCopy: string;
}

export default function CopyTextButton({ textToCopy }: CopyButtonProps) {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(textToCopy);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy text: ", err);
    }
  };

  return (
    <button
      onClick={handleCopy}
      style={{
        width: "100%",
        padding: "8px",
        backgroundColor: isCopied ? "#16a34a" : "#6862e2",
        color: "white",
        border: "none",
        borderRadius: "12px",
        fontWeight: "bold",
        fontSize: "0.9rem",
        cursor: "pointer",
        boxShadow: "0 4px 12px rgba(79, 70, 229, 0.2)",
        transition: "background-color 0.2s ease, transform 0.1s ease",
      }}
    >
      {isCopied ? "Copied" : "CLICK TO COPY LLM OUTPUT"}
    </button>
  );
}
