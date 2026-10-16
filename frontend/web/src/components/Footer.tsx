import React from "react";
import { siteConfig } from "@/config/site";
import styles from "./Footer.module.css";

export function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.container}>
        <div className={styles.notice}>{siteConfig.footerText}</div>
      </div>
    </footer>
  );
}
