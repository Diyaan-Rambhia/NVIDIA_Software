"""Safe in-memory text extraction for PDF, .xlsx, and .docx files."""

import io
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any

import docx
import openpyxl
import pypdf


PROHIBITED_MACRO_EXTENSIONS = {".xlsm", ".xltm", ".xlam", ".docm", ".dotm"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".svg"}
ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".docx"}


def extract_file_content(
    filename: str,
    content: bytes,
    content_type: str | None = None,
    limits: dict[str, Any] | None = None,
) -> str:
    """Extract plain text from PDF, .xlsx, or .docx entirely in memory.

    Safety protections:
    - Rejects .xlsm and any macro file.
    - Reads Excel values only (data_only=True), never evaluates formulas, ignores external links.
    - Caps uncompressed size and entry count of docx and xlsx to prevent zip decompression bombs.
    - Caps PDF page count and rejects encrypted PDFs.
    - Runs extraction within configured time limit.
    - Memory only: never stores file or text to disk, never logs content.
    """
    limits = limits or {}
    max_bytes = int(limits.get("file_extract_max_bytes", 10485760))
    max_pages = int(limits.get("file_extract_max_pages", 50))
    max_rows = int(limits.get("file_extract_max_rows", 5000))
    max_chars = int(limits.get("file_extract_max_chars", 200000))
    max_uncompressed_bytes = int(limits.get("file_extract_max_uncompressed_bytes", 52428800))
    max_zip_entries = int(limits.get("file_extract_max_zip_entries", 200))
    timeout_seconds = float(limits.get("file_extract_timeout_seconds", 20.0))

    lower_name = filename.lower()
    ext = lower_name[lower_name.rfind("."):] if "." in lower_name else ""

    # 1. Macro prohibition check
    if ext in PROHIBITED_MACRO_EXTENSIONS:
        raise ValueError("Macro-enabled office files (.xlsm, .docm) are strictly prohibited for safety.")

    # 2. Image rejection check (v2)
    if ext in IMAGE_EXTENSIONS or (content_type and content_type.lower().startswith("image/")):
        raise ValueError("Images are not available yet (v2).")

    # 3. Allowed type check
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{ext or filename}'. Only PDF, .xlsx, and .docx files are supported.")

    # 4. Content size checks
    if len(content) == 0:
        raise ValueError("Uploaded file is empty.")

    if len(content) > max_bytes:
        raise ValueError(f"File size ({len(content)} bytes) exceeds configured limit of {max_bytes} bytes.")

    def _do_extract() -> str:
        # Zip bomb defense for docx and xlsx
        if ext in (".docx", ".xlsx"):
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    infolist = zf.infolist()
                    if len(infolist) > max_zip_entries:
                        raise ValueError(
                            f"Archive entry count ({len(infolist)}) exceeds maximum safe limit ({max_zip_entries})."
                        )
                    uncompressed_size = sum(info.file_size for info in infolist)
                    if uncompressed_size > max_uncompressed_bytes:
                        raise ValueError(
                            f"Uncompressed archive size ({uncompressed_size} bytes) exceeds safety limit "
                            f"({max_uncompressed_bytes} bytes)."
                        )
            except zipfile.BadZipFile as exc:
                raise ValueError(f"Corrupt or invalid archive structure: {exc}") from exc

        if ext == ".xlsx":
            try:
                wb = openpyxl.load_workbook(
                    io.BytesIO(content),
                    data_only=True,
                    keep_links=False,
                    read_only=True,
                )
                rows_count = 0
                lines: list[str] = []
                for sheet in wb.worksheets:
                    for row in sheet.iter_rows(values_only=True):
                        rows_count += 1
                        if rows_count > max_rows:
                            wb.close()
                            raise ValueError(f"Excel row count exceeded maximum allowed limit of {max_rows} rows.")
                        vals = [str(v).strip() for v in row if v is not None and str(v).strip()]
                        if vals:
                            lines.append(" | ".join(vals))
                wb.close()
                extracted = "\n".join(lines).strip()
            except Exception as exc:
                if isinstance(exc, ValueError):
                    raise
                raise ValueError(f"Failed to extract Excel content: {exc}") from exc

        elif ext == ".docx":
            try:
                doc = docx.Document(io.BytesIO(content))
                lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
                for table in doc.tables:
                    for row in table.rows:
                        row_vals = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                        if row_vals:
                            lines.append(" | ".join(row_vals))
                extracted = "\n".join(lines).strip()
            except Exception as exc:
                if isinstance(exc, ValueError):
                    raise
                raise ValueError(f"Failed to extract Word document: {exc}") from exc

        elif ext == ".pdf":
            try:
                reader = pypdf.PdfReader(io.BytesIO(content))
                if reader.is_encrypted:
                    raise ValueError("Encrypted PDF files are not supported.")
                if len(reader.pages) > max_pages:
                    raise ValueError(
                        f"PDF page count ({len(reader.pages)}) exceeds maximum allowed limit of {max_pages} pages."
                    )
                page_texts = []
                for page in reader.pages:
                    txt = page.extract_text()
                    if txt and txt.strip():
                        page_texts.append(txt.strip())
                extracted = "\n\n".join(page_texts).strip()
            except Exception as exc:
                if isinstance(exc, ValueError):
                    raise
                raise ValueError(f"Failed to extract PDF document: {exc}") from exc
        else:
            raise ValueError(f"Unhandled extension: {ext}")

        if not extracted:
            raise ValueError("Extracted document content is empty.")

        if len(extracted) > max_chars:
            extracted = extracted[:max_chars]

        return extracted

    # Execute with strict timeout
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_do_extract)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError:
            raise TimeoutError(f"File extraction exceeded timeout of {timeout_seconds}s.")
