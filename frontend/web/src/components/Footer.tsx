import React from "react";
import { siteConfig, UI_REVISION } from "@/config/site";
import styles from "./Footer.module.css";

export function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.container}>
        <div className={styles.notice}>{siteConfig.footerText}</div>
        <div className={styles.notice}>UI revision {UI_REVISION}</div>
      </div>
    </footer>
  );
}
