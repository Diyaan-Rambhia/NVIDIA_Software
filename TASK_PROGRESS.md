# TASK_PROGRESS

- [x] Item 1: Trace agent tools, orchestrator, and prompt context for data reading and Rajesh Exports "no data provided" (file:line)
- [x] Item 2: Rewire agent tools to live code with plan check (filings_check, market_scan, market_news, trade_review conditional)
- [x] Item 3: System instruction updates: call tool when fact needed, never invent numbers, plain error reports, no advice, no code/tool names
- [x] Item 4: Tool call failure handling: 502 MODEL_TOOL_CALL_FAILED on exhaustion + tests (filings_check invocation, retail 403, financial unsupported)
- [x] Item 5: Check verified tiers for tool calling from verify_models
- [x] Item 6: Trace contagion news and hypotheses blocks (frontend & backend) for "not generated" and skipped news search (file:line)
- [x] Item 7: Contagion news block 4 real states, TTL caching, config search count
- [x] Item 8: Contagion hypotheses: display "No hypotheses: no regime flag in this scan." with tier, number, threshold from config
- [x] Item 9: Contagion tests: news block states render tests & backend search skip test
- [x] Item 10: Trade log CSV upload contract, help text, row-numbered error test
- [x] Item 11: Trade log 2-row XIRR unit test (10 at 100, 10 at 110 after 365 days = 0.10)
- [x] Docs & validation: openapi.json, drift, coverage, docs_check, tsc, eslint, build, test suites

