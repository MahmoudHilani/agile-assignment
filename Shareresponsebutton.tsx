"use client";

import { useState, useRef, useEffect } from "react";

interface ShareResponseButtonProps {
  responseText: string;
  responseTitle?: string;
}

type ShareState = "idle" | "open" | "copying" | "copied" | "sharing" | "shared" | "error";

export default function ShareResponseButton({
  responseText,
  responseTitle = "AI Response",
}: ShareResponseButtonProps) {
  const [state, setState] = useState<ShareState>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const canNativeShare =
    typeof navigator !== "undefined" &&
    typeof navigator.share === "function" &&
    typeof navigator.canShare === "function";

  // Close menu when clicking outside
  useEffect(() => {
    if (state !== "open") return;

    const handleClickOutside = (e: MouseEvent) => {
      if (
        menuRef.current &&
        !menuRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setState("idle");
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [state]);

  // Close on Escape key
  useEffect(() => {
    if (state !== "open") return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setState("idle");
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [state]);

  const formattedText = `${responseTitle}\n${"─".repeat(responseTitle.length)}\n\n${responseText}\n\nShared via AI Assistant`;

  const handleToggleMenu = () => {
    setState((prev) => (prev === "open" ? "idle" : "open"));
  };

  const handleCopy = async () => {
    setState("copying");
    try {
      await navigator.clipboard.writeText(formattedText);
      setState("copied");
      setTimeout(() => setState("idle"), 2200);
    } catch {
      setErrorMsg("Could not access clipboard.");
      setState("error");
      setTimeout(() => setState("idle"), 3000);
    }
  };

  const handleNativeShare = async () => {
    setState("sharing");
    try {
      const shareData: ShareData = {
        title: responseTitle,
        text: formattedText,
      };

      if (navigator.canShare(shareData)) {
        await navigator.share(shareData);
        setState("shared");
        setTimeout(() => setState("idle"), 2000);
      } else {
        throw new Error("Share not supported for this content.");
      }
    } catch (err: unknown) {
      // AbortError means user cancelled — not a real error
      if (err instanceof DOMException && err.name === "AbortError") {
        setState("idle");
        return;
      }
      setErrorMsg("Could not open share menu.");
      setState("error");
      setTimeout(() => setState("idle"), 3000);
    }
  };

  const isMenuOpen = state === "open";
  const isBusy = state === "copying" || state === "sharing";

  return (
    <div className="share-response-wrapper" role="group" aria-label="Share response">
      {/* Share trigger button */}
      <button
        ref={buttonRef}
        type="button"
        className={`share-trigger-btn ${isMenuOpen ? "active" : ""} ${state === "copied" || state === "shared" ? "success" : ""}`}
        onClick={handleToggleMenu}
        disabled={isBusy}
        aria-haspopup="true"
        aria-expanded={isMenuOpen}
        aria-label="Share this response"
        title="Share response"
      >
        {state === "copied" ? (
          <>
            <CheckIcon />
            <span>Copied!</span>
          </>
        ) : state === "shared" ? (
          <>
            <CheckIcon />
            <span>Shared!</span>
          </>
        ) : state === "error" ? (
          <>
            <ErrorIcon />
            <span>Failed</span>
          </>
        ) : (
          <>
            <ShareIcon />
            <span>Share</span>
          </>
        )}
      </button>

      {/* Dropdown share menu */}
      {isMenuOpen && (
        <div
          ref={menuRef}
          className="share-dropdown"
          role="menu"
          aria-label="Share options"
        >
          <p className="share-dropdown-label">Share this response</p>

          <button
            type="button"
            className="share-option-btn"
            onClick={handleCopy}
            role="menuitem"
          >
            <CopyIcon />
            <div className="share-option-text">
              <span className="share-option-title">Copy to clipboard</span>
              <span className="share-option-desc">Paste it anywhere you like</span>
            </div>
          </button>

          {canNativeShare && (
            <button
              type="button"
              className="share-option-btn"
              onClick={handleNativeShare}
              role="menuitem"
            >
              <AppsIcon />
              <div className="share-option-text">
                <span className="share-option-title">Share via app</span>
                <span className="share-option-desc">Messages, Mail, WhatsApp &amp; more</span>
              </div>
            </button>
          )}

          {state === "error" && (
            <p className="share-error-msg" role="alert">{errorMsg}</p>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Icon components ── */

function ShareIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="18" cy="5" r="3" />
      <circle cx="6" cy="12" r="3" />
      <circle cx="18" cy="19" r="3" />
      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
      <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
    </svg>
  );
}

function CopyIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function AppsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8" />
      <polyline points="16 6 12 2 8 6" />
      <line x1="12" y1="2" x2="12" y2="15" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function ErrorIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}