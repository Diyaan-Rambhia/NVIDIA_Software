import React from "react";
import Link from "next/link";
import styles from "./page.module.css";

export default function LandingPage() {
  return (
    <div className={styles.page}>
      {/* Hero Section */}
      <section className={styles.heroSection}>
        <div className={styles.heroGrid}>
          <div className={styles.heroMain}>
            <span className={styles.sectionIndex}>01 / PROBLEM STATEMENT</span>
            <h1 className={styles.heroTitle}>
              When diversified assets suddenly move together, standard risk models fail.
            </h1>
            <p className={styles.heroLead}>
              Under stress, correlations break down. Assets that historically move apart begin
              moving in unison, destroying portfolio diversification when protection is needed most.
              FinFriend audits systemic contagion, verifies regulatory filings with verbatim source tracing,
              and calculates true investment process discipline.
            </p>
            <div className={styles.ctaRow}>
              <Link href="/signup" className={styles.primaryCta}>
                Open Account
              </Link>
              <Link href="/login" className={styles.secondaryCta}>
                Sign In
              </Link>
            </div>
          </div>

          <div className={styles.heroVisual}>
            <div className={styles.diagramBox}>
              <div className={styles.diagramLabel}>Illustration, not market data</div>
              {/* Converging lines diagram */}
              <svg className={styles.convergenceSvg} viewBox="0 0 320 180" fill="none">
                <line x1="20" y1="160" x2="300" y2="160" stroke="#2A313C" strokeWidth="1" />
                <line x1="20" y1="20" x2="20" y2="160" stroke="#2A313C" strokeWidth="1" />
                {/* Asset A line */}
                <path
                  d="M 20 40 C 90 45, 160 70, 300 100"
                  stroke="#7C8CA0"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
                {/* Asset B line */}
                <path
                  d="M 20 140 C 90 135, 160 120, 300 100"
                  stroke="#C29A3A"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
                <circle cx="300" cy="100" r="4" fill="#C4524D" />
              </svg>
              <div className={styles.diagramCaption}>
                Asset A and Asset B correlation shifts under systemic absorption
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Three Analytical Tools */}
      <section className={styles.toolsSection}>
        <div className={styles.sectionHeader}>
          <span className={styles.sectionIndex}>02 / THREE ANALYTICAL TOOLS</span>
          <h2>Deterministic forensic finance tools built for Indian capital markets.</h2>
        </div>

        <div className={styles.toolColumns}>
          <div className={styles.toolCol}>
            <div className={styles.toolNum}>FEATURE 01</div>
            <h3>Systemic Contagion & Absorption</h3>
            <p>
              Quantifies correlation shifts across candidate Indian liquid equities and indices.
              Utilizes Forbes-Rigobon conditional correlation adjustment, systemic absorption ratio
              eigenvalue tracking, and moving-block bootstrap hypothesis testing.
            </p>
            <div className={styles.toolMeta} data-mono>SECTOR UNIVERSE / FORBES-RIGOBON / AR DELTA</div>
          </div>

          <div className={styles.toolCol}>
            <div className={styles.toolNum}>FEATURE 02</div>
            <h3>Filings Consistency & XBRL Engine</h3>
            <p>
              Audits corporate financial claims against filed XBRL statutory statements. Evaluates
              rules R0 through R7 deterministically, demanding exact verbatim source quote matching
              before accepting claims.
            </p>
            <div className={styles.toolMeta} data-mono>RULES R0-R7 / VERBATIM QUOTE AUDIT / IND AS</div>
          </div>

          <div className={styles.toolCol}>
            <div className={styles.toolNum}>FEATURE 03</div>
            <h3>Trade Log Forensic Review</h3>
            <p>
              Parses real trading execution CSV logs to compute true time-weighted and money-weighted
              returns via Brent root-solved XIRR. Replays exact cash flows against Nifty 50 benchmarks
              to measure turnover, concentration HHI, and disposition bias.
            </p>
            <div className={styles.toolMeta} data-mono>XIRR BRENT SOLVER / NIFTY 50 REPLAY / ODEAN PGR-PLR</div>
          </div>
        </div>
      </section>

      {/* How it Works */}
      <section className={styles.methodSection}>
        <div className={styles.sectionHeader}>
          <span className={styles.sectionIndex}>03 / METHODOLOGY & VERIFICATION</span>
          <h2>Maths first. Language models write only from computed evidence.</h2>
        </div>

        <div className={styles.methodSteps}>
          <div className={styles.methodStep}>
            <div className={styles.stepMarker}>STEP 1</div>
            <h4>Pure Mathematical Computation</h4>
            <p>
              Estimators, linear algebra, covariance shrinkage, and cash flow solving execute
              deterministically. Zero speculative inferences or hallucinatory statistics.
            </p>
          </div>
          <div className={styles.methodStep}>
            <div className={styles.stepMarker}>STEP 2</div>
            <h4>Grounded Language Synthesis</h4>
            <p>
              Any qualitative summaries or hypothesis formulations are constrained strictly to
              computed evidence IDs and explicit numeric parameters.
            </p>
          </div>
          <div className={styles.methodStep}>
            <div className={styles.stepMarker}>STEP 3</div>
            <h4>Deterministic Source Verification</h4>
            <p>
              A deterministic verifier rejects any narrative assertion or citation not literally
              found in source filing text or computed analytical results.
            </p>
          </div>
        </div>
      </section>

      {/* Honest Limitations */}
      <section className={styles.limitsSection}>
        <div className={styles.sectionHeader}>
          <span className={styles.sectionIndex}>04 / HONEST LIMITS & DISCLOSURES</span>
          <h2>Explicit data and model boundaries. No false confidence.</h2>
        </div>

        <div className={styles.limitsGrid}>
          <div className={styles.limitItem}>
            <strong>Unofficial Market Prices:</strong> Market data sourced from development feeds
            for technical demonstration; not intended for real-time order routing or trade execution.
          </div>
          <div className={styles.limitItem}>
            <strong>No Flow Data:</strong> Analysis does not incorporate intraday institutional order
            book depth, broker tick data, or proprietary participant flows.
          </div>
          <div className={styles.limitItem}>
            <strong>Revenue & Profit Checks Only:</strong> Filings auditor examines operational revenue,
            margins, and reported PAT; balance sheet notes and off-balance sheet liabilities require human review.
          </div>
          <div className={styles.limitItem}>
            <strong>Provisional Risk-Free Rate:</strong> Benchmark discount curves use provisional 91-day
            T-bill yields pending institutional advisor confirmation.
          </div>
          <div className={styles.limitItem}>
            <strong>No Financial Advisor Review:</strong> Algorithmic analytics are educational and
            exploratory. No personalized investment advice or SEBI-registered advisory opinions are provided.
          </div>
          <div className={styles.limitItem}>
            <strong>Zero Payment Collection:</strong> No commercial transactions, merchant card processing,
            or payment gateway integrations are activated.
          </div>
        </div>
      </section>

      {/* Subscription Plans */}
      <section className={styles.plansSection}>
        <div className={styles.sectionHeader}>
          <span className={styles.sectionIndex}>05 / SEGMENTS & ACCESS TIERS</span>
          <h2>Institutional and retail entitlement tiers (no prices listed).</h2>
        </div>

        <div className={styles.plansGrid}>
          <div className={styles.planCard}>
            <div className={styles.planBadge} data-mono>SEGMENT: RETAIL</div>
            <h3>Retail Free & Paid</h3>
            <p>Designed for individual market participants studying portfolio process discipline.</p>
            <ul className={styles.planFeatures}>
              <li>Feature 2 Filings Consistency engine (daily quota governed)</li>
              <li>Feature 3 Trade Log forensic review (FIFO lot accounting & XIRR)</li>
              <li>Agent tool loop access for filings and trade history</li>
              <li className={styles.disabledFeature}>Systemic Contagion scan locked (Institutional only)</li>
            </ul>
          </div>

          <div className={styles.planCard}>
            <div className={styles.planBadge} data-mono>SEGMENT: INSTITUTIONAL</div>
            <h3>Institutional Free & Paid</h3>
            <p>Designed for regulated asset managers, family offices, and institutional desks.</p>
            <ul className={styles.planFeatures}>
              <li>Systemic Contagion & Absorption scanner (full correlation matrix)</li>
              <li>XBRL filings auditor with verbatim quote verification</li>
              <li>Institutional portfolio metrics (Beta, Alpha, Tracking Error, IR)</li>
              <li>SEBI / RBI registration verification workflow</li>
            </ul>
          </div>
        </div>
      </section>

      {/* CTA Footer Section */}
      <section className={styles.bottomCtaSection}>
        <h2>Begin analytical review</h2>
        <p>Access the deterministic computational dashboard.</p>
        <div className={styles.ctaRow}>
          <Link href="/signup" className={styles.primaryCta}>
            Create Account
          </Link>
          <Link href="/login" className={styles.secondaryCta}>
            Log In
          </Link>
        </div>
      </section>
    </div>
  );
}
