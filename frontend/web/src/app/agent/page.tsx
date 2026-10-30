"use client";

import React, { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import { useAuth } from "@/context/AuthContext";
import { apiFetch, ApiError } from "@/lib/api";
import { AgentAskResponse, AgentStep } from "@/types/agent";
import { formatDecimal } from "@/lib/formatters";
import styles from "./agent.module.css";

type ModelTier = "fast" | "balanced" | "deep";

interface ChatMessage {
  id: string;
  sender: "user" | "agent";
  text?: string;
  answer?: string;
  tier?: ModelTier;
  disclaimer?: string;
  steps?: AgentStep[];
  total_cost_usd?: number;
  duration_ms?: number;
  error?: {
    status: number;
    code: string;
    message: string;
  };
}

const STARTER_QUESTIONS = [
  "Check systemic absorption ratio and Forbes-Rigobon correlation shifts for Indian equities.",
  "Audit INFY filings for revenue discrepancies between press releases and XBRL.",
  "Evaluate portfolio trade logs for XIRR performance and disposition effect.",
];

export default function AgentPage() {
  const router = useRouter();
  const { user } = useAuth();

  // In-memory chat thread
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputQuery, setInputQuery] = useState("");
  const [selectedTier, setSelectedTier] = useState<ModelTier>("balanced");
  const [unavailableTiers, setUnavailableTiers] = useState<Record<ModelTier, string>>({} as Record<ModelTier, string>);
  const [running, setRunning] = useState(false);
  const [extractingFile, setExtractingFile] = useState(false);
  const [attachedFile, setAttachedFile] = useState<{ name: string; text: string } | null>(null);
  const [imageNotice, setImageNotice] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    setImageNotice(null);
    setFileError(null);
    const file = e.target.files?.[0];
    if (!file) return;

    // Reset input value so same file can be selected again
    e.target.value = "";

    // Check for images
    if (file.type.startsWith("image/") || /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(file.name)) {
      setImageNotice("Images: coming later");
      return;
    }

    // Support plain text files directly in-memory via file.text()
    const isText = file.name.endsWith(".txt") || file.name.endsWith(".csv") || file.name.endsWith(".md") || file.name.endsWith(".json") || file.type.startsWith("text/");
    if (isText) {
      setExtractingFile(true);
      try {
        const textContent = await file.text();
        setAttachedFile({
          name: file.name,
          text: textContent,
        });
      } catch (err: unknown) {
        setFileError("Document text extraction failed.");
      } finally {
        setExtractingFile(false);
      }
      return;
    }

    // Supported document formats for server extraction: PDF, Excel, Word
    const isPdf = file.name.endsWith(".pdf") || file.type === "application/pdf";
    const isExcel = file.name.endsWith(".xlsx") || file.name.endsWith(".xls") || file.type.includes("spreadsheetml");
    const isWord = file.name.endsWith(".docx") || file.name.endsWith(".doc") || file.type.includes("wordprocessingml");

    if (!isPdf && !isExcel && !isWord) {
      setFileError("Supported files: text (.txt, .csv, .md), PDF, Excel (.xlsx), Word (.docx)");
      return;
    }

    setExtractingFile(true);
    try {
      const buffer = await file.arrayBuffer();
      const extracted = await apiFetch<string>(`/files/extract?filename=${encodeURIComponent(file.name)}`, {
        method: "POST",
        headers: {
          "x-filename": file.name,
          "content-type": file.type || "application/octet-stream",
        },
        body: buffer,
      });

      setAttachedFile({
        name: file.name,
        text: typeof extracted === "string" ? extracted : JSON.stringify(extracted),
      });
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setFileError(`Extraction failed: ${err.parsed.message}`);
      } else {
        setFileError("Document text extraction failed.");
      }
    } finally {
      setExtractingFile(false);
    }
  };

  const removeAttachment = () => {
    setAttachedFile(null);
    setFileError(null);
    setImageNotice(null);
  };

  const handleSend = async (queryToSend?: string) => {
    let q = (queryToSend ?? inputQuery).trim();
    if (!q && attachedFile) {
      q = `Analyze the attached file: ${attachedFile.name}`;
    }
    if (!q || running) return;

    const userMsgId = `user-${Date.now()}`;
    const userMsg: ChatMessage = {
      id: userMsgId,
      sender: "user",
      text: q,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuery("");
    setImageNotice(null);
    setFileError(null);
    setRunning(true);

    const textToAttach = attachedFile?.text || null;
    const tierUsed = selectedTier;
    // Attachment chip remains active across turns until removed by user

    const historyPayload = messages.slice(-10).map((m) => ({
      role: m.sender === "user" ? "user" : "assistant",
      content: m.text || m.answer || "",
    }));

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const res = await apiFetch<AgentAskResponse>("/agent/ask", {
        method: "POST",
        body: JSON.stringify({
          query: q,
          model_tier: tierUsed,
          attachment_text: textToAttach,
          history: historyPayload,
        }),
        signal: controller.signal,
      });

      const agentMsg: ChatMessage = {
        id: `agent-${Date.now()}`,
        sender: "agent",
        answer: res.answer,
        tier: (res as any).model_tier || tierUsed,
        disclaimer: res.disclaimer,
        steps: res.steps || [],
        total_cost_usd: res.total_cost_usd,
        duration_ms: res.duration_ms,
      };

      setMessages((prev) => [...prev, agentMsg]);
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") {
        const cancelMsg: ChatMessage = {
          id: `err-${Date.now()}`,
          sender: "agent",
          error: {
            status: 499,
            code: "CLIENT_CANCELLED",
            message: "Cancel stops waiting; the server may still finish.",
          },
        };
        setMessages((prev) => [...prev, cancelMsg]);
        return;
      }

      if (err instanceof ApiError) {
        if (err.status === 401) {
          router.push("/login");
          return;
        }

        let code = err.parsed.code || `HTTP_${err.status}`;
        let message = err.parsed.message;

        if (err.status === 402) {
          code = code || "UPGRADE_REQUIRED";
          message = "Requires the institutional plan. Plan changes are not available yet.";
        } else if (err.status === 403) {
          code = code || "FORBIDDEN";
          message = message || "Access restricted for your account segment.";
        } else if (err.status === 429) {
          code = code || "QUOTA_EXCEEDED";
          const resetTime = err.parsed.resetTime || (err.parsed as any).reset_time;
          if (resetTime) {
            message = `${message} (Reset time: ${resetTime})`;
          }
        } else if (err.status === 503) {
          code = code || "SERVICE_UNAVAILABLE";
          message = message || "Model service is unconfigured or unreachable.";
          // Mark the tier unavailable with reason
          setUnavailableTiers((prev) => ({
            ...prev,
            [tierUsed]: message,
          }));
        }

        const agentErrMsg: ChatMessage = {
          id: `err-${Date.now()}`,
          sender: "agent",
          error: {
            status: err.status,
            code: code.toUpperCase(),
            message: `HTTP ${err.status} [${code.toUpperCase()}]: ${message}`,
          },
        };
        setMessages((prev) => [...prev, agentErrMsg]);
      } else {
        const genericErrMsg: ChatMessage = {
          id: `err-${Date.now()}`,
          sender: "agent",
          error: {
            status: 500,
            code: "AGENT_ERROR",
            message: "HTTP 500 [AGENT_ERROR]: Execution error communicating with autonomous agent loop.",
          },
        };
        setMessages((prev) => [...prev, genericErrMsg]);
      }
    } finally {
      setRunning(false);
      abortControllerRef.current = null;
    }
  };

  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const userPlan = user?.plan || "free";

  return (
    <div className={styles.pageContainer}>
      {/* Top Header */}
      <div className={styles.header}>
        <div className={styles.titleGroup}>
          <h1 className={styles.title}>FinFriend agent</h1>
          <span className={styles.planBadge} data-mono>
            {userPlan}
          </span>
        </div>
        <span className={styles.statelessNote} data-mono>
          Each question is answered on its own.
        </span>
      </div>

      {/* Thread Container */}
      <div className={styles.threadContainer} data-testid="chat-thread">
        {messages.map((msg) => {
          const isUser = msg.sender === "user";
          const isError = Boolean(msg.error);

          return (
            <div
              key={msg.id}
              className={`${styles.messageBlock} ${
                isUser
                  ? styles.userMessage
                  : isError
                    ? styles.errorMessage
                    : styles.agentMessage
              }`}
            >
              <div className={styles.messageHeader}>
                <span className={styles.senderLabel}>
                  {isUser ? "You" : "FinFriend agent"}
                </span>
                {!isUser && msg.tier && (
                  <span className={styles.tierBadge} data-mono>
                    {msg.tier.charAt(0).toUpperCase() + msg.tier.slice(1)}
                  </span>
                )}
              </div>

              {isUser ? (
                <div className={styles.messageBody}>{msg.text}</div>
              ) : isError ? (
                <div className={styles.messageBody}>{msg.error?.message}</div>
              ) : (
                <>
                  <div className={styles.messageBody}>
                    <ReactMarkdown
                      components={{
                        pre({ children, ...props }) {
                          return (
                            <details className={styles.codeDetails}>
                              <summary className={styles.codeSummary}>Code block</summary>
                              <pre {...props}>{children}</pre>
                            </details>
                          );
                        },
                      }}
                    >
                      {msg.answer || ""}
                    </ReactMarkdown>
                  </div>

                  {msg.disclaimer && (
                    <div className={styles.disclaimerText}>{msg.disclaimer}</div>
                  )}

                  {msg.steps && msg.steps.length > 0 && (
                    <details className={styles.stepsDetails}>
                      <summary className={styles.stepsSummary} data-mono>
                        {msg.steps.length} steps, ${formatDecimal(msg.total_cost_usd, 4)}, {msg.duration_ms}ms
                      </summary>
                      <div className={styles.stepsTableWrapper}>
                        <table className={styles.stepsTable}>
                          <thead>
                            <tr>
                              <th>#</th>
                              <th>Tool</th>
                              <th>Input Summary</th>
                              <th>Output Summary</th>
                              <th>Status</th>
                              <th>Cost</th>
                              <th>Duration</th>
                            </tr>
                          </thead>
                          <tbody>
                            {msg.steps.map((step) => {
                              const statusClass =
                                step.status === "success"
                                  ? styles.statusSuccess
                                  : step.status === "denied"
                                    ? styles.statusDenied
                                    : styles.statusError;

                              return (
                                <tr key={step.step_number}>
                                  <td data-mono>{step.step_number}</td>
                                  <td data-mono>{step.tool_name}</td>
                                  <td>{step.input_summary}</td>
                                  <td>{step.output_summary}</td>
                                  <td>
                                    <span className={statusClass} data-mono>
                                      {step.status.toUpperCase()}
                                    </span>
                                  </td>
                                  <td data-mono>${formatDecimal(step.est_cost_usd, 4)}</td>
                                  <td data-mono>{step.duration_ms}ms</td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </details>
                  )}
                </>
              )}
            </div>
          );
        })}

        {running && (
          <div className={styles.runningLine} data-mono>
            running
          </div>
        )}
      </div>

      {/* Input Section at bottom */}
      <div className={styles.inputSection}>
        {messages.length === 0 && (
          <div className={styles.starterChips} data-testid="starter-chips">
            {STARTER_QUESTIONS.map((chip, idx) => (
              <button
                key={idx}
                type="button"
                className={styles.starterChip}
                onClick={() => handleSend(chip)}
                disabled={running}
              >
                {chip}
              </button>
            ))}
          </div>
        )}

        {attachedFile && (
          <div className={styles.attachedChip} data-testid="attached-chip">
            <span data-mono>{attachedFile.name}</span>
            <button
              type="button"
              onClick={removeAttachment}
              title="Remove attachment"
              aria-label="Remove attachment"
            >
              x
            </button>
          </div>
        )}

        {imageNotice && (
          <div className={styles.imageNotice} data-mono>
            {imageNotice}
          </div>
        )}

        {fileError && (
          <div className={styles.imageNotice} data-mono>
            {fileError}
          </div>
        )}

        <textarea
          className={styles.textarea}
          value={inputQuery}
          onChange={(e) => setInputQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about contagion, filings discrepancies, or trade logs... (Enter to send, Shift+Enter for new line)"
          disabled={running}
          rows={2}
        />

        <div className={styles.inputControls}>
          <div className={styles.leftControls}>
            <select
              aria-label="Model Tier"
              className={styles.tierSelect}
              value={selectedTier}
              onChange={(e) => setSelectedTier(e.target.value as ModelTier)}
              disabled={running}
            >
              <option value="fast" disabled={Boolean(unavailableTiers.fast)}>
                Fast{unavailableTiers.fast ? ` (unavailable: ${unavailableTiers.fast})` : ""}
              </option>
              <option value="balanced" disabled={Boolean(unavailableTiers.balanced)}>
                Balanced{unavailableTiers.balanced ? ` (unavailable: ${unavailableTiers.balanced})` : ""}
              </option>
              <option value="deep" disabled={Boolean(unavailableTiers.deep)}>
                Deep{unavailableTiers.deep ? ` (unavailable: ${unavailableTiers.deep})` : ""}
              </option>
            </select>

            <label className={styles.fileButton}>
              {extractingFile ? "Extracting..." : "Attach file"}
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.csv,.md,.json,text/*,.pdf,.xlsx,.docx,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/*"
                onChange={handleFileSelect}
                disabled={running || extractingFile}
                hidden
              />
            </label>
          </div>

          <div className={styles.rightControls}>
            {running && (
              <button
                type="button"
                className={styles.cancelBtn}
                onClick={handleCancel}
                title="Cancel stops waiting; the server may still finish."
              >
                Cancel stops waiting; the server may still finish.
              </button>
            )}

            <button
              type="button"
              className={styles.sendBtn}
              onClick={() => handleSend()}
              disabled={running || (!inputQuery.trim() && !attachedFile)}
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
