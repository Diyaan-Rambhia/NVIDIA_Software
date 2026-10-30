import pathlib

p_tools = pathlib.Path("backend/app/agent/tools.py")
text = p_tools.read_text(encoding="utf-8")

# 1. Add normalize_fiscal_period function
normalize_func = '''def normalize_fiscal_period(period_str: str | None) -> str:
    """Normalize fiscal period variations like Q3FY25 or q3 fy25 to standard Q3 FY25."""
    if not period_str:
        return "Q3 FY25"
    s = str(period_str).strip()
    m = re.match(r"^(Q[1-4])\s*[-_]?\s*(FY\s*\d{2,4})$", s, re.IGNORECASE)
    if m:
        q_part = m.group(1).upper()
        fy_raw = m.group(2).upper()
        fy_clean = re.sub(r"\\s+", "", fy_raw)
        return f"{q_part} {fy_clean}"
    return s

'''

if "def normalize_fiscal_period" not in text:
    text = text.replace("def resolve_iso_date", normalize_func + "def resolve_iso_date")

# 2. In tool_market_scan, use as_of_resolved in summary["as_of"]
old_scan_as_of = '"as_of": str(scan.as_of),'
new_scan_as_of = '"as_of": as_of_resolved or str(scan.as_of),'
text = text.replace(old_scan_as_of, new_scan_as_of)

# 3. In tool_filings_check, normalize period and catch 404/source unavailable as not_found
old_filing_setup = 'period_query = (period or "Q3 FY25").strip()'
new_filing_setup = 'period_query = normalize_fiscal_period(period or "Q3 FY25")'
text = text.replace(old_filing_setup, new_filing_setup)

old_filing_except = '''    except ValueError as exc:
        return {
            "status": "not_found",
            "reason": str(exc),
            "company": company_query,
            "period": period_query,
            "as_of": period_query,
            "fetched_at": fetched_at,
        }
    except Exception as exc:
        logger.error("Failed to execute filings_check for %s: %s", company_query, exc)
        return {
            "status": "error",
            "reason": f"Filings check error: {exc}",
            "company": company_query,
            "period": period_query,
            "as_of": period_query,
            "fetched_at": fetched_at,
        }'''

new_filing_except = '''    except (ValueError, RuntimeError) as exc:
        err_msg = str(exc)
        if "404" in err_msg or "source unavailable" in err_msg or "no data for" in err_msg:
            return {
                "status": "not_found",
                "reason": f"No XBRL filing document is available for {company_query} for period {period_query} in the NSE exchange archives.",
                "company": company_query,
                "period": period_query,
                "as_of": period_query,
                "fetched_at": fetched_at,
            }
        return {
            "status": "not_found" if isinstance(exc, ValueError) else "error",
            "reason": str(exc) if isinstance(exc, ValueError) else f"Filings check error: {exc}",
            "company": company_query,
            "period": period_query,
            "as_of": period_query,
            "fetched_at": fetched_at,
        }
    except Exception as exc:
        logger.error("Failed to execute filings_check for %s: %s", company_query, exc)
        return {
            "status": "error",
            "reason": f"Filings check error: {exc}",
            "company": company_query,
            "period": period_query,
            "as_of": period_query,
            "fetched_at": fetched_at,
        }'''

text = text.replace(old_filing_except, new_filing_except)

p_tools.write_text(text, encoding="utf-8")
print("backend/app/agent/tools.py updated successfully")

