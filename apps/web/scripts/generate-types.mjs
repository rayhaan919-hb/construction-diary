import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import yaml from "js-yaml";
import openapiTS, { astToString } from "openapi-typescript";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(__dirname, "..");
const contractPath = path.resolve(webRoot, "../../contracts/api-contract.yaml");
const outPath = path.resolve(webRoot, "src/lib/api-types.ts");

function loadContractYaml(raw) {
  try {
    return yaml.load(raw);
  } catch {
    // Upstream frozen contract line 329 contains unquoted `: ` in `summary:`.
    // Quote unquoted summary/description lines in memory without touching the contract file.
    const sanitized = raw
      .split(/\r?\n/)
      .map((line) => {
        const match = /^(\s+(?:summary|description): )([^'"|>].*:\s.*)$/.exec(line);
        if (!match) return line;
        return `${match[1]}${JSON.stringify(match[2])}`;
      })
      .join("\n");
    return yaml.load(sanitized);
  }
}

async function main() {
  const raw = fs.readFileSync(contractPath, "utf8");
  const schema = loadContractYaml(raw);
  const ast = await openapiTS(schema);
  const banner =
    "/**\n * This file was auto-generated from ../../contracts/api-contract.yaml via openapi-typescript.\n * Do not edit manually; run `npm run generate:types` to regenerate.\n */\n\n";
  const output = banner + astToString(ast);
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, output, "utf8");
  console.log(`Generated ${path.relative(webRoot, outPath)} (${output.length} bytes)`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
