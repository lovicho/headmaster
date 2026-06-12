import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, extname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const srcDir = join(root, "src");
const distDir = join(root, "dist");
const mojibakeMarkers = ["�", "쨌", "醫", "紐", "怨", "??/"];
const requiredSourceText = [
  "Headmaster",
  "Control Dashboard",
  "새 작업",
  "승인 대기",
  "작업 목록",
];

function walk(dir) {
  return readdirSync(dir)
    .flatMap((entry) => {
      const path = join(dir, entry);
      return statSync(path).isDirectory() ? walk(path) : [path];
    });
}

function fail(message) {
  console.error(message);
  process.exitCode = 1;
}

if (!existsSync(distDir)) {
  fail("dist directory is missing; run npm run build before smoke");
} else if (!existsSync(join(distDir, "index.html"))) {
  fail("dist/index.html is missing");
}

const sourceFiles = walk(srcDir).filter((path) =>
  [".ts", ".tsx", ".css"].includes(extname(path)),
);
const distFiles = existsSync(distDir) ? walk(distDir) : [];
const checkedFiles = [...sourceFiles, ...distFiles].filter((path) =>
  [".html", ".js", ".css", ".ts", ".tsx"].includes(extname(path)),
);

if (sourceFiles.length === 0) {
  fail("no dashboard source files found");
}

const sourceText = sourceFiles
  .map((path) => readFileSync(path, "utf8"))
  .join("\n");
for (const expected of requiredSourceText) {
  if (!sourceText.includes(expected)) {
    fail(`dashboard source is missing expected text: ${expected}`);
  }
}

const assetFiles = distFiles.filter((path) => [".js", ".css"].includes(extname(path)));
if (assetFiles.length === 0) {
  fail("built dashboard has no JS/CSS assets");
}

for (const path of checkedFiles) {
  const text = readFileSync(path, "utf8");
  const marker = mojibakeMarkers.find((candidate) => text.includes(candidate));
  if (marker !== undefined) {
    fail(`${relative(root, path)} contains mojibake marker: ${marker}`);
  }
}

if (process.exitCode === undefined) {
  console.log("dashboard smoke passed");
}
