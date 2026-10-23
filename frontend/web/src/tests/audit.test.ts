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

  it("prohibits CSS box-shadows across all source files", () => {
    const shadowMatches: { file: string; line: number; match: string }[] = [];

    files.forEach((file) => {
      const content = fs.readFileSync(file, "utf-8");
      const lines = content.split("\n");
      lines.forEach((line, index) => {
        if (/box-shadow|drop-shadow/i.test(line)) {
          shadowMatches.push({ file, line: index + 1, match: line.trim() });
        }
      });
    });

    expect(shadowMatches).toEqual([]);
  });

  it("prohibits emoji characters across all production source files", () => {
    const emojiRegex = /[\u{1F300}-\u{1F6FF}\u{1F900}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/u;
    const emojiMatches: { file: string; line: number; match: string }[] = [];

    files.forEach((file) => {
      const content = fs.readFileSync(file, "utf-8");
      const lines = content.split("\n");
      lines.forEach((line, index) => {
        if (emojiRegex.test(line)) {
          emojiMatches.push({ file, line: index + 1, match: line.trim() });
        }
      });
    });

    expect(emojiMatches).toEqual([]);
  });

  it("prohibits external chart libraries in imports", () => {
    const chartLibRegex = /from\s+['"](recharts|chart\.js|react-chartjs-2|d3|victory|echarts|apexcharts)['"]/i;
    const chartMatches: { file: string; line: number; match: string }[] = [];

    files.forEach((file) => {
      const content = fs.readFileSync(file, "utf-8");
      const lines = content.split("\n");
      lines.forEach((line, index) => {
        if (chartLibRegex.test(line)) {
          chartMatches.push({ file, line: index + 1, match: line.trim() });
        }
      });
    });

    expect(chartMatches).toEqual([]);
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
      const content = fs.readFileSync(file, "utf-8");
      const lines = content.split("\n");
      lines.forEach((line, index) => {
        if (/https?:\/\//.test(line)) {
          if (
            line.includes("http://www.w3.org/2000/svg") ||
            line.includes("startsWith(\"https://\")") ||
            line.includes("startsWith('https://')") ||
            line.includes("startsWith(\"https:\")")
          ) {
            return;
          }
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

  it("prohibits vendor names across src/ (except tests, admin and config)", () => {
    const vendorRegex = /\b(Tavily|Nebius|Nemotron|Llama|Supabase|Token Factory|yfinance|Next\.js)\b/i;
    const vendorMatches: { file: string; line: number; match: string }[] = [];

    files.forEach((file) => {
      const normalized = file.replace(/\\/g, "/");
      if (
        normalized.includes("/tests/") ||
        normalized.includes("/app/admin/") ||
        normalized.includes("/config/")
      ) {
        return;
      }

      const content = fs.readFileSync(file, "utf-8");
      const lines = content.split("\n");
      lines.forEach((line, index) => {
        if (vendorRegex.test(line)) {
          vendorMatches.push({ file, line: index + 1, match: line.trim() });
        }
      });
    });

    expect(vendorMatches).toEqual([]);
  });
});
