# 06: Regulatory and Compliance (India)

**This is the highest-stakes document in the folder.** The team are not lawyers. Everything below is a design position for a securities-law professional to confirm. Labels: **[V]** seen in a public source, **[K]** team knowledge to confirm, **[?]** unknown, **[PROPOSED]** our choice.

## 1. The core rule the product obeys

> **The product provides educational analysis only. It never recommends buying, selling or holding any security, never gives price targets, and never personalizes advice to a user's goals, risk profile or situation.**

Why this matters (public facts):
- Under SEBI's Investment Advisers Regulations (2013) and Research Analysts Regulations (2014), no person may act as an investment adviser or research analyst without registration with SEBI. [V]
- Research analyst registration covers preparing or publishing research reports and recommendations on securities, and regulations prescribe qualifications and a minimum net worth. [V] Public guidance says paid stock recommendations, buy/sell calls, price targets or subscription research may require registration, and that the *channel* does not determine whether it is required; a security-specific opinion intended to influence investment decisions can bring the regulations into play. [V]
- SEBI has acted against unregistered advisory presented as education: in one recent order it impounded over ₹546 crore from a trainer and his firm for what it treated as unregistered advisory and research activity delivered under training programmes, including stock-specific entry and exit points. [V] Earlier SEBI orders also treated "educational" claims skeptically when advice was given for a fee. [V]
- SEBI has issued rules aimed at social-media "finfluencers" who give stock views while describing it as education. [?] Details not verified by us.

Implication: simply labelling a product "educational" is not a defence if outputs function as stock-specific advice. The design must make outputs **structurally** non-advisory.

## 2. Design measures [PROPOSED]

| Measure | Where it applies |
|---|---|
| No buy/sell/hold language, no price targets, no "you should" | F3 reviews, F2 flags, agent answers; enforced by output validators that reject such text |
| Outputs describe **analysis of disclosures and of the user's own history**, not forward-looking views on securities | F2, F3 |
| F1 describes the **structure of market co-movement across asset classes**, not recommendations about securities | F1 |
| Agent refuses requests like "should I buy X?" and explains why | Agent |
| Disclaimer on every analytical output and the terms of use | All |
| No security-specific forward-looking statements | All |
| F2 wording about companies: "management's description appears inconsistent with the reported figure"; never "fraud", "lied", "misleading" | F2 |
| No user profiling for suitability (no risk questionnaire, no goals interview) | All |
| No performance claims about the product ("beats the market", "predicts crashes") | Marketing, README, video |

## 3. Questions that need a securities-law professional

| ID | Question | Why it matters |
|---|---|---|
| Q-REG-1 | Does F2 (flagging inconsistencies for named listed companies) amount to a research report requiring RA registration? | It names specific securities and could influence decisions |
| Q-REG-2 | Does F3's review of a user's own trades with benchmark comparison amount to investment advice? | It evaluates personal decisions |
| Q-REG-3 | Is F1 outside both regimes because it covers asset-class co-movement, not securities? Does selling it to institutions change anything? | Institutional customers, paid access |
| Q-REG-4 | Does charging a subscription change the analysis in Q-REG-1 to Q-REG-3? | Payments are in scope |
| Q-REG-5 | What disclaimers and disclosures are required or advisable? | Every output |
| Q-REG-6 | Are there rules on how a product may describe itself ("educational", "intelligence") and on advertising? | Marketing |
| Q-REG-7 | Is there any exemption or sandbox suitable for a research or hackathon prototype? | Scope of the hackathon deliverable |
| Q-REG-8 | If registration were needed for a real launch, which category and what is the realistic path and timeline? | Post-hackathon planning |

## 4. Personal data (DPDP Act and related) [K]

Trade logs reveal a person's financial behaviour and holdings. India's Digital Personal Data Protection Act, 2023 sets duties on those who process personal data: notice, consent, purpose limitation, security safeguards, retention limits, and rights such as correction and erasure. [K] Which rules and timelines currently apply to a small service is for the advisor to confirm. [?]

**Design measures [PROPOSED]**
- Logs are processed in memory and not stored unless the user explicitly consents.
- If stored: a plain-language notice, a stated purpose, a retention period, deletion on request.
- No full account numbers or identifiers; users are told to remove them before upload; the parser discards any it finds.
- The ledger of model calls stores token counts, not content.
- Real logs from team members or volunteers: written consent covering analysis and any public display; identifiers removed; stored outside the repository.
- Authentication data is handled by the identity provider (Supabase) with row-level access control.

| ID | Question |
|---|---|
| Q-DP-1 | What consent and notice text is required for processing uploaded logs? |
| Q-DP-2 | Is the product a "data fiduciary" with specific duties at our scale? |
| Q-DP-3 | Data localization or cross-border processing: our model provider and database may be hosted outside India. Is that acceptable for this kind of data? |
| Q-DP-4 | Children's data and verification, if any users are under 18? |

## 5. Data licensing and use of third-party content

| Source | Concern | Design response [PROPOSED] |
|---|---|---|
| **NSE / BSE price and index data** | Exchange data is usually licensed; redistribution may be restricted | Raw data is never committed to the public repository and never exposed through the API; only derived analytics are shown, with attribution |
| **Index provider data (NSE Indices)** | Terms of use of downloads | Read terms; use for analysis only |
| **Unofficial price sources (for example yfinance)** | Not an official licensed feed; terms are restrictive | Used only if the advisor and a legal check allow; otherwise use a licensed source |
| **Company filings, press releases, presentations, transcripts** | Public disclosures but the text may be copyrighted by the company or a transcription vendor | Use for analysis; keep short quotes with attribution; store extracts, not whole documents in public places |
| **News via Tavily** | Publisher copyright | Show short snippets and links, not copied articles |
| **Scraping exchange websites** | Exchange sites may restrict automated access | Throttle, identify, honor terms; prefer official downloads; surface blocks as errors |

| ID | Question |
|---|---|
| Q-LIC-1 | May we use exchange and index data for a commercial analytics product, and under which licence? |
| Q-LIC-2 | May we store and display brief quotes from company transcripts? |
| Q-LIC-3 | Which licensed vendor is the lowest-cost compliant option if free sources are not acceptable? |

## 6. Payments, tax and invoicing [K]

- **Payment gateway.** Indian gateways require business KYC for live payments; test mode is available without it (to be confirmed). [?] During the hackathon the product runs in test mode; no real money moves.
- **GST.** Digital subscriptions are generally subject to GST, and GST registration may be needed above a turnover threshold. [K]
- **Invoices.** Paid plans may require GST-compliant invoices. [K]
- **RBI rules.** Payment aggregation is regulated; using a licensed gateway keeps the product outside that regime. [K]

| ID | Question |
|---|---|
| Q-PAY-1 | When must GST registration happen for a subscription product? |
| Q-PAY-2 | What invoice format is required? |
| Q-PAY-3 | Refund, cancellation and subscription-lapse rules for consumers vs business customers? |
| Q-PAY-4 | Different treatment for institutional customers (contracts, TDS)? |

## 7. Open-source licensing (hackathon) and intellectual property

The hackathon requires a public repository with an open-source licence visible at the top. [V] Choice: MIT (short, permissive) or Apache-2.0 (permissive with a patent grant). Either takes minutes to adopt; see the answer given in chat, and decide before the first commit. Use only dependencies with compatible licences. The code must be the team's own work; third-party data must be used within its terms. [V]

## 8. Marketing and communication rules [PROPOSED]

Never claim: returns, accuracy of crash prediction, "SEBI approved", "recommended", "advisory". Describe the product as **analysis tools** and **disclosure and history review**. All demo and README text goes through the advisor before publishing.

## 9. Summary table of what we ask the advisor to confirm

| # | Item | Priority |
|---|---|---|
| 1 | The core rule (§1) is sufficient; the design measures in §2 are adequate | P1 |
| 2 | Q-REG-1 to Q-REG-4 | P1 |
| 3 | Disclaimer and wording standards | P1 |
| 4 | DPDP duties and consent text | P2 |
| 5 | Data licensing for NSE/BSE/index data | P1 |
| 6 | Payments, GST, invoicing | P3 (before any live payment) |
| 7 | Real-launch pathway if registration is needed | P3 |
