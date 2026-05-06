"use client";

import { useEffect, useState } from "react";

interface LoadingAnimationProps {
  isLoading: boolean;
}

export default function LoadingAnimation({ isLoading }: LoadingAnimationProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (isLoading) {
      setVisible(true);
    } else {
      // Small delay before hiding so fade-out can play
      const t = setTimeout(() => setVisible(false), 400);
      return () => clearTimeout(t);
    }
  }, [isLoading]);

  if (!visible) return null;

  return (
    <div
      className={`loading-wrapper ${isLoading ? "loading-enter" : "loading-exit"}`}
      role="status"
      aria-live="polite"
      aria-label="Processing your request"
    >
      <div className="loading-card">
        <div className="loading-dots">
          <span className="loading-dot" />
          <span className="loading-dot" />
          <span className="loading-dot" />
        </div>
        <span className="loading-label">Thinking…</span>
      </div>
    </div>
  );
}
