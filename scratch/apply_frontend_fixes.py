import pathlib

p_page = pathlib.Path("frontend/web/src/app/agent/page.tsx")
text = p_page.read_text(encoding="utf-8")

# 1. Update handleFileSelect to support plain text files directly
old_select_code = '''    // Supported document formats: PDF, Excel, Word
    const isPdf = file.name.endsWith(".pdf") || file.type === "application/pdf";
    const isExcel = file.name.endsWith(".xlsx") || file.name.endsWith(".xls") || file.type.includes("spreadsheetml");
    const isWord = file.name.endsWith(".docx") || file.name.endsWith(".doc") || file.type.includes("wordprocessingml");

    if (!isPdf && !isExcel && !isWord) {
      setFileError("Supported files: PDF, Excel (.xlsx), Word (.docx)");
      return;
    }'''

new_select_code = '''    // Support plain text files directly in-memory via file.text()
    const isText = file.name.endsWith(".txt") || file.name.endsWith(".csv") || file.name.endsWith(".md") || file.name.endsWith(".json") || file.type.startsWith("text/");
    if (isText) {
      setExtractingFile(true);
      try {
        const textContent = await file.text();
        setAttachedFile({
          name: file.name,
          text: textContent,
        });
      } catch (err: unknown) {
        setFileError("Document text extraction failed.");
      } finally {
        setExtractingFile(false);
      }
      return;
    }

    // Supported document formats for server extraction: PDF, Excel, Word
    const isPdf = file.name.endsWith(".pdf") || file.type === "application/pdf";
    const isExcel = file.name.endsWith(".xlsx") || file.name.endsWith(".xls") || file.type.includes("spreadsheetml");
    const isWord = file.name.endsWith(".docx") || file.name.endsWith(".doc") || file.type.includes("wordprocessingml");

    if (!isPdf && !isExcel && !isWord) {
      setFileError("Supported files: text (.txt, .csv, .md), PDF, Excel (.xlsx), Word (.docx)");
      return;
    }'''

text = text.replace(old_select_code, new_select_code)

# 2. Update handleSend to allow sending with attached file
old_send_check = '''  const handleSend = async (queryToSend?: string) => {
    const q = (queryToSend ?? inputQuery).trim();
    if (!q || running) return;'''

new_send_check = '''  const handleSend = async (queryToSend?: string) => {
    let q = (queryToSend ?? inputQuery).trim();
    if (!q && attachedFile) {
      q = `Analyze the attached file: ${attachedFile.name}`;
    }
    if (!q || running) return;'''

text = text.replace(old_send_check, new_send_check)

# 3. Update input accept attribute
old_accept = 'accept=".pdf,.xlsx,.docx,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/*"'
new_accept = 'accept=".txt,.csv,.md,.json,text/*,.pdf,.xlsx,.docx,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/*"'
text = text.replace(old_accept, new_accept)

# 4. Update Send button disabled condition
old_btn_disable = 'disabled={running || !inputQuery.trim()}'
new_btn_disable = 'disabled={running || (!inputQuery.trim() && !attachedFile)}'
text = text.replace(old_btn_disable, new_btn_disable)

p_page.write_text(text, encoding="utf-8")
print("frontend/web/src/app/agent/page.tsx updated successfully")

