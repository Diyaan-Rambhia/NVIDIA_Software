# 08: Pricing and Tiers

**No prices have been set.** This file defines the tier logic, the cost drivers, and the questions the advisor should help answer. Labels: **[V]** seen in a public source, **[K]** team knowledge to confirm, **[?]** unknown, **[PROPOSED]** our choice.

## 1. Structure [DECIDED by owner, see `11_decisions_log.md`]

Access is defined by **segment** (retail or institutional) and **plan** within the segment. **Billing is monthly** (annual plans later).

| Plan | Segment | F1 Contagion | F2 Filings | F3 Log Advisor | Price (monthly, provisional) |
|---|---|---|---|---|---|
| `retail_free` | Retail | not available | limited quota | limited (small logs) | free |
| `retail_paid` | Retail | not available | full | full retail scope | ₹499 (test-mode placeholder) |
| `institutional_free` | Institutional | locked, upgrade offered | limited, same as `retail_free` | limited, retail scope, same as `retail_free` | free |
| `institutional_paid` | Institutional | full | limited, retail-free level (full F2 not purchasable) | full institutional scope, heavy quotas | ₹24,999 (test-mode placeholder) |
| `judge_all` | Internal only | full | full | full, both scopes | not sold; hackathon judges |

Rules:
- A retail user **cannot** buy F1 at any price; a retail user hitting F1 is told it is an institutional feature and no upgrade is offered.
- **Institutions pay only for what is institutional.** There is no institutional free trial. Institutions can, however, use the retail-level free tier (F2 and F3 at retail-free limits) at no charge.
- Institutional pricing is **higher** than retail pricing, reflecting F1, heavier usage and expected support.
- **Institutional status is verified**: the institution supplies its SEBI registration number (or another regulator's registration ID for entities regulated elsewhere, such as insurers or banks) and an administrator approves it manually before `institutional_paid` can be purchased.
- **The amounts above are placeholders** so that payments can be built and tested in the gateway's test mode. They are not researched market prices. Real prices are set before any live payment, using the unit-economics formula in §3 and advisor input.

## 2. What drives cost (so prices cover them)

### 2.1 Model usage (LLM) [V for prices; estimates are ours]
Nebius lists per-million-token prices (in US dollars): Nemotron Ultra about $1.00 input and $3.00 output; Super about $0.30 and $0.90; Nano about $0.06 and $0.24. [V]

Illustrative arithmetic for one heavy Ultra call of 8,000 input and 2,000 output tokens: 8,000 × $1.00 / 1,000,000 = $0.008, plus 2,000 × $3.00 / 1,000,000 = $0.006, so about $0.014 (about ₹1.2 at an assumed ₹85/$; the exchange rate must be refreshed). [PROPOSED estimate]

| Feature | Main model calls per use | Rough cost driver |
|---|---|---|
| F1 explanation | 1-2 Ultra calls plus Tavily searches | Ultra tokens; Tavily credits |
| F2 analysis (one company-period) | Several Nano extraction calls plus a few Ultra adjudications | Document length |
| F3 review | One Nano mapping plus one Ultra review | Log size |
| Agent question | Several Super calls plus tool-triggered calls | Steps per question |

The statistics (F1) and arithmetic (F3) cost almost nothing in model fees; the cost is language steps and data fetching.

### 2.2 Other costs
- **Database and auth:** Supabase free tier is limited (about 500 MB database, 50,000 monthly active users, pauses after a week of inactivity); the paid tier starts at about $25 per month. [V]
- **Search:** Tavily free tier is 1,000 credits per month. [V]
- **Payment gateway fees:** a percentage of each transaction plus GST on the fee. [K; rate unverified]
- **GST on our own subscription revenue:** generally 18% on software services if registered. [K]
- **Hosting:** TBD.
- **Market-data licences:** may become a major cost if free sources are not acceptable (`06`, `07`).
- **Advisor and legal review.**

## 3. Unit economics formula [PROPOSED]

For a plan with monthly price `P` (excluding GST), average monthly uses `u_f` of each feature `f`, average model cost per use `c_f`, fixed monthly cost `F` spread over `N` paying users, and payment fee rate `r`:

```
margin per user = P × (1 − r) − Σ_f ( u_f × c_f ) − F / N
```

Quotas in `plans.yaml` are chosen so that the heaviest allowed use stays above zero margin: `Σ_f ( quota_f × c_f_max )` must be less than `P × (1 − r)`. The advisor can supply plausible usage frequencies so we can size the quotas.

## 4. Tier-differentiation principles [PROPOSED]

1. Free tier exists to let retail users try F2 and F3 on small inputs; limits are per day.
2. Retail paid unlocks full quotas and larger logs.
3. Institutional pricing reflects: F1 access, much higher quotas, larger logs, configurable parameters, and more support expectation.
4. Pricing is shown in INR, with GST handled according to advisor guidance.
5. No plan is called "advice" or "recommendation".

## 5. Payment mechanics [PROPOSED]

Plan changes occur only when the payment gateway's server-to-server notification (webhook) is verified, never from a browser message alone. Payments are idempotent; plan lapse downgrades the account by a documented rule. During the hackathon the gateway runs in test mode. Judges and demo accounts never pay.

## 6. Decisions on the pricing questions (owner)

| ID | Question | Decision | Status |
|---|---|---|---|
| Q-PRC-1 | Price anchors; monthly vs annual | **Monthly** billing. Amounts provisional (see §1) | Decided; amounts provisional |
| Q-PRC-2 | Institutional free trial? | **No.** Institutions are paid-only for institutional features but may use the retail-level free tier | Decided |
| Q-PRC-3 | How to establish institutional status | **SEBI registration number**, manually verified by an administrator; other regulated institutions give their own regulator's ID; case-by-case for unregistered entities such as family offices | Decided (extension for non-SEBI entities adopted) |
| Q-PRC-4 | Contract terms institutions expect | **Click-through Terms of Service** with limited liability and disclaimers, designed to cap the team's financial and legal exposure; no custom contracts or purchase orders at launch. (Owner wrote "AOT"; read here as Terms of Service.) See `12_terms_and_liability_framework.md` | Adopted |
| Q-PRC-5 | Annual plans | **Later** | Decided |
| Q-PRC-6 | GST and invoice requirements | TBD. Engineering default: store amount, tax and total as separate fields so GST can be added without redesign | TBD |
| Q-PRC-7 | Consumer refund rules | TBD. Default while in test mode: no real money moves, so no refunds | TBD |
| Q-PRC-8 | Lapse and downgrade rule | TBD by owner; **provisional engineering default:** at the end of a period without a successful renewal, the account returns to its segment's free plan, with no grace period and no data deleted | Provisional |
