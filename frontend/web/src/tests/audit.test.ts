import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

function getAllFiles(dirPath: string, arrayOfFiles: string[] = []): string[] {
  const files = fs.readdirSync(dirPath);

  files.forEach((file) => {
    const fullPath = path.join(dirPath, file);
    if (fs.statSync(fullPath).isDirectory()) {
      if (file !== "node_modules" && file !== ".next" && file !== "tests") {
        getAllFiles(fullPath, arrayOfFiles);
      }
    } else {
      if (/\.(tsx?|css)$/.test(file)) {
        arrayOfFiles.push(fullPath);
      }
    }
  });

  return arrayOfFiles;
}

describe("Static Security and Style Audit", () => {
  const srcDir = path.resolve(__dirname, "../");
  const files = getAllFiles(srcDir);

  it("prohibits CSS gradients across all source files", () => {
    const gradientMatches: { file: string; line: number; match: string }[] = [];

    files.forEach((file) => {
      const content = fs.readFileSync(file, "utf-8");
      const lines = content.split("\n");
      lines.forEach((line, index) => {
        if (/gradient/i.test(line)) {
          gradientMatches.push({ file, line: index + 1, match: line.trim() });
        }
      });
    });

    expect(gradientMatches).toEqual([]);
  });

  it("prohibits browser web storage (localStorage and sessionStorage) in production code", () => {
    const storageMatches: { file: string; line: number; match: string }[] = [];

    files.forEach((file) => {
      const content = fs.readFileSync(file, "utf-8");
      const lines = content.split("\n");
      lines.forEach((line, index) => {
        if (/localStorage|sessionStorage/.test(line)) {
          storageMatches.push({ file, line: index + 1, match: line.trim() });
        }
      });
    });

    expect(storageMatches).toEqual([]);
  });

  it("prohibits dangerouslySetInnerHTML across all components", () => {
    const dangerousMatches: { file: string; line: number }[] = [];

    files.forEach((file) => {
      const content = fs.readFileSync(file, "utf-8");
      const lines = content.split("\n");
      lines.forEach((line, index) => {
        if (/dangerouslySetInnerHTML/.test(line)) {
          dangerousMatches.push({ file, line: index + 1 });
        }
      });
    });

    expect(dangerousMatches).toEqual([]);
  });

  it("prohibits hardcoded external HTTP(S) API URLs in source code", () => {
    const urlMatches: { file: string; line: number; match: string }[] = [];

    files.forEach((file) => {
      // Exclude next.config.ts if it was in src
      const content = fs.readFileSync(file, "utf-8");
      const lines = content.split("\n");
      lines.forEach((line, index) => {
        // Match http:// or https:// that are not comments or type declarations
        if (/https?:\/\//.test(line)) {
          // Allow SVG namespace declarations
          if (line.includes("http://www.w3.org/2000/svg")) return;
          urlMatches.push({ file, line: index + 1, match: line.trim() });
        }
      });
    });

    expect(urlMatches).toEqual([]);
  });

  it("prohibits token in URLs or query strings", () => {
    const tokenUrlMatches: { file: string; line: number; match: string }[] = [];

    files.forEach((file) => {
      const content = fs.readFileSync(file, "utf-8");
      const lines = content.split("\n");
      lines.forEach((line, index) => {
        if (/[?&]token=|[?&]access_token=/i.test(line)) {
          tokenUrlMatches.push({ file, line: index + 1, match: line.trim() });
        }
      });
    });

    expect(tokenUrlMatches).toEqual([]);
  });
});
