"use client";

import React from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { siteConfig } from "@/config/site";
import styles from "./Navbar.module.css";

export function Navbar() {
  const pathname = usePathname();
  const { user, entitlements, isAuthenticated, isAdmin, logout } = useAuth();

  const navLinks = [
    { href: "/dashboard", label: "Dashboard", protected: true },
    { href: "/contagion", label: "Contagion", protected: true },
    { href: "/filings", label: "Filings", protected: true },
    { href: "/trade-log", label: "Trade Log", protected: true },
    { href: "/agent", label: "Agent", protected: true },
  ];

  if (isAdmin) {
    navLinks.push({ href: "/admin", label: "Admin", protected: true });
  }

  // Quota calculation from entitlements
  const quotaSummary = React.useMemo(() => {
    if (!entitlements?.features) return null;
    const parts: string[] = [];
    for (const [key, detail] of Object.entries(entitlements.features)) {
      if (!detail) continue;
      const shortKey = key.replace("feature1_contagion", "F1").replace("feature2_filings", "F2").replace("feature3_forensic", "F3");
      if (detail.remaining_quota !== null && detail.remaining_quota !== undefined) {
        parts.push(`${shortKey}: ${detail.remaining_quota} left`);
      } else if (detail.decision === "full") {
        parts.push(`${shortKey}: unlimited`);
      } else if (detail.status === 402 || detail.status === 403) {
        parts.push(`${shortKey}: locked`);
      }
    }
    return parts.length > 0 ? parts.join(" | ") : null;
  }, [entitlements]);

  return (
    <header className={styles.header}>
      <div className={styles.container}>
        <div className={styles.brandRow}>
          <Link href="/" className={styles.brandLink}>
            <Image
              src={siteConfig.logo.horizontalLight}
              alt={siteConfig.name}
              width={140}
              height={32}
              priority
              className={styles.brandLogo}
            />
          </Link>
          <span className={styles.headerTagline}>{siteConfig.tagline}</span>
        </div>

        <nav className={styles.navLinks} aria-label="Main Navigation">
          {isAuthenticated ? (
            <>
              {navLinks.map((link) => {
                const isActive = pathname === link.href;
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`${styles.navLink} ${isActive ? styles.navLinkActive : ""}`}
                  >
                    {link.label}
                  </Link>
                );
              })}
            </>
          ) : (
            <Link
              href="/"
              className={`${styles.navLink} ${pathname === "/" ? styles.navLinkActive : ""}`}
            >
              Overview
            </Link>
          )}
        </nav>

        <div className={styles.userSection}>
          {isAuthenticated ? (
            <>
              <div className={styles.metaBadges}>
                <span className={styles.planBadge} data-mono>
                  PLAN: {user?.plan?.toUpperCase() || "UNKNOWN"}
                </span>
                {quotaSummary && (
                  <span className={styles.quotaBadge} data-mono>
                    {quotaSummary}
                  </span>
                )}
              </div>
              <Link
                href="/account"
                className={`${styles.accountLink} ${pathname === "/account" ? styles.navLinkActive : ""}`}
              >
                Account
              </Link>
              <button onClick={logout} className={styles.logoutBtn} type="button">
                Log out
              </button>
            </>
          ) : (
            <div className={styles.authActions}>
              <Link href="/login" className={styles.loginLink}>
                Log in
              </Link>
              <Link href="/signup" className={styles.signupBtn}>
                Sign up
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
