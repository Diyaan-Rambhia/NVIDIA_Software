import React from "react";
import styles from "@/app/contagion/contagion.module.css";

export interface ContagionNewsItem {
  title: string;
  url?: string;
  content?: string;
  source?: string;
  evidence_id?: string;
}

export interface ContagionNewsBlockProps {
  newsState: "ready" | "empty" | "not run: no search key" | "error" | "loading";
  newsQuery?: string | null;
  newsResults?: ContagionNewsItem[] | null;
  errorStatus?: number | null;
  errorMessage?: string | null;
}

export function ContagionNewsBlock({
  newsState,
  newsQuery,
  newsResults,
  errorStatus,
  errorMessage,
}: ContagionNewsBlockProps) {
  return (
    <div className={styles.newsSection}>
      <h3 className={styles.subHeader}>External Context (Market News)</h3>

      {newsState === "loading" && (
        <div className={styles.stateBox} data-mono>
          Loading macro news...
        </div>
      )}

      {newsState === "not run: no search key" && (
        <div className={styles.stateBox} data-mono>
          not run: no search key
        </div>
      )}

      {newsState === "empty" && (
        <div className={styles.stateBox} data-mono>
          {newsQuery ? `no results (${newsQuery})` : "no results"}
        </div>
      )}

      {newsState === "error" && (
        <div className={`${styles.stateBox} ${styles.stateError}`} data-mono>
          {errorStatus
            ? `HTTP ${errorStatus}: ${errorMessage || "Error loading market news"}`
            : errorMessage || "Error loading market news"}
        </div>
      )}

      {newsState === "ready" && newsResults && newsResults.length > 0 && (
        <div className={styles.newsList}>
          {newsResults.map((item, idx) => {
            const hasHttps =
              item.url &&
              (item.url.startsWith("https://") || item.url.startsWith("https:"));
            return (
              <article key={idx} className={styles.articleCard}>
                <div className={styles.articleMeta}>
                  {item.source && (
                    <span className={styles.source} data-mono>
                      {item.source}
                    </span>
                  )}
                  {item.evidence_id && (
                    <span className={styles.evidenceBadge} data-mono>
                      {item.evidence_id}
                    </span>
                  )}
                </div>

                <div className={styles.articleTitle}>
                  {hasHttps && item.url ? (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={styles.articleLink}
                    >
                      {item.title}
                    </a>
                  ) : (
                    <span>{item.title}</span>
                  )}
                </div>

                {item.content && (
                  <p className={styles.articleSnippet}>{item.content}</p>
                )}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
