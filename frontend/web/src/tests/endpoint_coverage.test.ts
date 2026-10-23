import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

describe("OpenAPI Endpoint Coverage Audit", () => {
  const openApiPath = path.resolve(__dirname, "../../../../docs/openapi.json");
  const openApiContent = JSON.parse(fs.readFileSync(openApiPath, "utf-8"));
  const openApiPaths: string[] = Object.keys(openApiContent.paths || {});

  // Endpoints explicitly declared as intentionally unused in DECISIONS.md
  const intentionallyUnused = new Set<string>([
    "/",
    "/console",
    "/console/",
    "/console/config.html",
    "/console/index.html",
    "/llm/runtime_call",
    "/llm/tavily_search",
  ]);

  // Read all production source code to check for endpoint references
  const srcDir = path.resolve(__dirname, "../");
  function getCodeText(dir: string): string {
    let text = "";
    const items = fs.readdirSync(dir);
    for (const item of items) {
      if (item === "node_modules" || item === ".next" || item === "tests") continue;
      const full = path.join(dir, item);
      if (fs.statSync(full).isDirectory()) {
        text += getCodeText(full);
      } else if (/\.(tsx?|js)$/.test(item)) {
        text += fs.readFileSync(full, "utf-8") + "\n";
      }
    }
    return text;
  }

  const allSourceText = getCodeText(srcDir);

  it("verifies every active OpenAPI backend route is covered by the frontend", () => {
    const uncoveredEndpoints: string[] = [];

    for (const ep of openApiPaths) {
      if (intentionallyUnused.has(ep)) {
        continue;
      }

      // Handle parameterized endpoints like /api/admin/verifications/{verification_id}/review
      const epPattern = ep.includes("{")
        ? ep.split("{")[0] // matches prefix up to param
        : ep;

      if (!allSourceText.includes(epPattern)) {
        uncoveredEndpoints.push(ep);
      }
    }

    expect(uncoveredEndpoints).toEqual([]);
  });
});
