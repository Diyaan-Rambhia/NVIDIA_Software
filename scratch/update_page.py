from pathlib import Path

path = Path("frontend/web/src/app/agent/page.tsx")
text = path.read_text(encoding="utf-8")

old_block = """    const textToAttach = attachedFile?.text || null;
    const tierUsed = selectedTier;
    setAttachedFile(null);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const res = await apiFetch<AgentAskResponse>("/agent/ask", {
        method: "POST",
        body: JSON.stringify({
          query: q,
          model_tier: tierUsed,
          attachment_text: textToAttach,
        }),
        signal: controller.signal,
      });"""

new_block = """    const textToAttach = attachedFile?.text || null;
    const tierUsed = selectedTier;
    // Attachment chip remains active across turns until removed by user

    const historyPayload = messages.slice(-10).map((m) => ({
      role: m.sender === "user" ? "user" : "assistant",
      content: m.text || m.answer || "",
    }));

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const res = await apiFetch<AgentAskResponse>("/agent/ask", {
        method: "POST",
        body: JSON.stringify({
          query: q,
          model_tier: tierUsed,
          attachment_text: textToAttach,
          history: historyPayload,
        }),
        signal: controller.signal,
      });"""

norm_text = text.replace("\r\n", "\n")
if old_block in norm_text:
    updated = norm_text.replace(old_block, new_block, 1)
    path.write_text(updated, encoding="utf-8", newline="\n")
    print("SUCCESS")
else:
    print("FAILURE")

