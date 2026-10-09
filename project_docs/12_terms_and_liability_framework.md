# 12: Terms of Service and Liability Framework

**Goal (owner's instruction): limit the team's financial and legal liability.**

**This is a planning framework, not legal advice.** The team and the author of this document are not lawyers. Every clause below is a checklist item for a qualified Indian lawyer to draft and confirm. Labels: **[K]** general knowledge to confirm, **[P]** our proposal.

## 1. Layers of protection

Liability is limited by several layers working together. No single layer is enough.

| Layer | What it does | Owner |
|---|---|---|
| 1. Product design | Outputs are structurally non-advisory, so there is less to be liable for | Built in code |
| 2. Contract | Terms of Service with disclaimers and a liability cap | Lawyer drafts |
| 3. Legal entity | A company or LLP stands between the team and claims | Team + lawyer |
| 4. Money handling | A licensed gateway holds card data; no live money until the entity exists | Team |
| 5. Data handling | Consent, minimal retention, deletion | Code + lawyer |
| 6. Operations | Audit trail, kill switch, output validators | Code |
| 7. Insurance | Optional professional indemnity and cyber cover, later | Team |

## 2. Layer 1: product design (already in the specification)

- No buy, sell or hold language, no price targets, no personalized suitability. Output validators reject such text (`PROJECT.md` NFR-LEG-001).
- Company-specific outputs use neutral wording: "management's description appears inconsistent with the reported figure". Never "lied", "fraud" or "misleading".
- Every analytical output carries an educational-use disclaimer and the data's "as of" time.
- No claims such as "predicts crashes", "beats the market", "SEBI approved", "recommended".
- The product describes what it did and what it could not know, so users are not misled about reliability.

## 3. Layer 2: Terms of Service checklist [P]

Accepted by click-through at sign-up; acceptance, version and time are stored (FR-AUTH-010).

| Clause | Purpose |
|---|---|
| **Nature of service** | Software providing educational analysis of disclosures, market data and the user's own records. Not investment advice, research recommendation, portfolio management or a solicitation. The team is not represented as SEBI-registered |
| **No reliance** | The user decides independently and should consult a registered adviser. No guarantee of accuracy, completeness, timeliness or fitness |
| **Third-party data "as is"** | Exchange, index, news and model outputs may be delayed, wrong or unavailable; no liability for them |
| **AI-generated content** | Language-model text may contain errors; evidence and sources are shown so the user can check |
| **Limitation of liability** | Cap total liability at the fees paid in a stated recent period (or a fixed small amount for free users); exclude indirect, consequential and trading losses |
| **Exclusions** | No liability for investment losses, lost profits, data loss or decisions made using outputs. Note that some liability cannot be excluded by contract, such as fraud or wilful misconduct, and courts may not enforce clauses seen as unreasonable [K], so the lawyer sets the wording |
| **User indemnity** | The user covers claims arising from their misuse, their uploaded content, or breach of the terms |
| **Uploaded data warranty** | The user has the right to upload the data, has removed identifiers, and consents to processing |
| **Acceptable use** | No scraping, resale, redistribution of outputs or data, account sharing, reverse engineering, abuse or attempts to extract raw vendor data |
| **Institutional addendum** | The signatory has authority to bind the institution; use is internal only; no redistribution to the institution's clients as advice; the institution is responsible for its own regulatory duties |
| **Intellectual property** | The team keeps the software and models; the user keeps their data; a limited licence to the user |
| **Privacy and consent** | Link to a privacy notice covering purpose, retention, deletion and processors |
| **Fees, renewal, lapse, refunds** | Monthly billing; lapse returns the account to the free plan; refund terms after the advisor decides (D-07) |
| **Suspension and termination** | Right to suspend for misuse or non-payment |
| **Service availability** | No uptime guarantee; maintenance and outages allowed |
| **Force majeure and third-party failure** | Not liable for failures of providers such as hosts, data sources or model providers |
| **Changes to terms** | Notice and re-acceptance (FR-AUTH-010) |
| **Governing law and disputes** | Indian law; named courts or arbitration, as the lawyer advises |
| **Notices and grievance contact** | A contact point, as Indian consumer and data rules may require [K] |

## 4. Layer 3: legal entity [K]

- Before taking any **real** payment, operate through a registered entity (a private limited company or an LLP), so that claims are against the entity rather than the individuals. Both give limited liability to owners, with different compliance burdens; the lawyer or a chartered accountant advises which fits.
- Until then the product runs in **test mode only**: no real money moves and the exposure is much lower.
- Sign a short **team agreement** now: who owns the code and the idea, how decisions are made, what happens if someone leaves, and how contributions are credited. Hackathon entries also warrant that the work is original and that the team has the right to submit it. [V]
- Keep project money and accounts separate from personal accounts once the entity exists.
- Register for GST and any other required registrations when thresholds are crossed (D-06).

## 5. Layer 4: money handling

- A licensed payment gateway collects payments. The team never stores card or bank details (FR-PAY-005).
- Plan changes happen only after a verified gateway webhook (FR-PAY-003), which prevents disputes about "I paid but was not upgraded" caused by client-side errors.
- Refund and chargeback handling must exist before live payments (D-07).
- Test mode only during the hackathon (FR-PAY-009).

## 6. Layer 5: data handling [K]

- Trade logs and account data are personal data. Collect the minimum, say why, keep it for the shortest time, delete on request.
- Default: logs are processed in memory and not stored (FR-F3-009). Storage needs explicit consent.
- Processors: Supabase, the model provider and the search provider may process or host data outside India; the lawyer advises on notices and agreements (Q-DP-3).
- Have a **breach response plan**: who is told, how fast, what is logged.
- Never put personal data, raw exchange data or credentials in the public repository.

## 7. Layer 6: operational safeguards

- Consent and terms-acceptance records are stored with version and time.
- A **kill switch** (a configuration flag) disables a feature or all LLM output instantly if an output problem or complaint arises.
- Output validators block forbidden language before anything reaches a user.
- The activity feed and ledger give an audit trail of what ran and when (FR-OBS-004).
- Rate limits and budget guards limit abuse and cost exposure.

## 8. Layer 7: insurance (later) [K]

Professional indemnity and cyber-liability cover can protect against claims and breaches. Consider once there are paying users; the lawyer or an insurance broker advises.

## 9. What to take to a lawyer, in order

1. Can the product, as designed, run without SEBI registration? (Q-REG-1 to Q-REG-4; `06`.)
2. Draft the Terms of Service, privacy notice and disclaimers from §3 and §6.
3. Choose and set up the legal entity; agree the team agreement.
4. Review data licensing for exchange and index data (Q-LIC-1).
5. GST, invoices, refund rules and gateway onboarding (D-06, D-07).
6. Review company-specific wording in Feature 2 (D-29).

## 10. Rule for the hackathon

For the hackathon the product is a **prototype in test mode** with no real money and only consenting, identified test users and judges. Do not market it to the public as a financial service, and do not accept real payments, until steps 1 to 3 above are done.
