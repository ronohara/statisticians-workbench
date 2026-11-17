// scripts/extract-translations.ts
// ============================================================
// TRANSLATION EXTRACTION SCRIPT
// Uses ts-morph to parse TypeScript files and extract TranslationKey
// definitions. Outputs to locales/en.yaml by default; `--output <path>`
// diverts the write elsewhere and leaves the locale file untouched.
// ============================================================

import crypto from "crypto";
import fs from "fs";
import os from "os";
import path from "path";
import yaml from "js-yaml";
import { glob } from "glob";
import { Project, SyntaxKind, Node } from "ts-morph";

// ============================================================
// CONSTANTS
// ============================================================

// ANSI color codes for terminal output
const RESET = "\x1b[0m";
const GREEN = "\x1b[32m";
const RED = "\x1b[31m";
const CYAN = "\x1b[36m";
const GRAY = "\x1b[90m";
const YELLOW = "\x1b[33m";

// Valid prefixes are auto-discovered from the keys found in translations.ts files.
// No hardcoded whitelist — any key defined in a module's translations.ts is valid.
// The function below only checks for obviously malformed keys.

// ============================================================
// TYPES
// ============================================================

interface KeyInfo {
    key: string;
    fallback: string;
    file: string;
    line: number;
}

// ============================================================
// EXTRACTION FUNCTIONS
// ============================================================

/**
 * Check if a key has a valid prefix.
 */
function isValidKey(key: string): boolean {
    if (key.length < 3) return false;
    const dotIndex = key.indexOf(".");
    if (dotIndex < 1) return false;           // no dot, or dot at position 0
    if (dotIndex >= key.length - 1) return false; // dot at end, nothing after
    return true;
}

/**
 * Extract TranslationKey definitions from a file using ts-morph.
 */
function extractFromFile(filePath: string): Map<string, KeyInfo> {
    const result = new Map<string, KeyInfo>();
    
    try {
        const project = new Project({
            useInMemoryFileSystem: true,
        });
        
        const content = fs.readFileSync(filePath, "utf8");
        const sourceFile = project.createSourceFile(filePath, content);
        
        // Get all object literal expressions in the file
        const objectLiterals = sourceFile.getDescendantsOfKind(SyntaxKind.ObjectLiteralExpression);
        
        for (const objLiteral of objectLiterals) {
            // Check if this object has both "key" and "fallback" properties
            let key: string | null = null;
            let fallback: string | null = null;
            
            const properties = objLiteral.getProperties();
            for (const prop of properties) {
                if (prop.getKind() === SyntaxKind.PropertyAssignment) {
                    const propAssignment = prop.asKind(SyntaxKind.PropertyAssignment);
                    if (propAssignment) {
                        const propName = propAssignment.getName();
                        const initializerNode = propAssignment.getInitializer();
                        if (initializerNode && initializerNode.getKind() === SyntaxKind.StringLiteral) {
                            const stringNode = initializerNode.asKind(SyntaxKind.StringLiteral);
                            if (stringNode) {
                                const value = stringNode.getLiteralValue();
                                if (propName === "key") {
                                    key = value;
                                } else if (propName === "fallback") {
                                    fallback = value;
                                }
                            }
                        }
                    }
                }
            }
            
            // If we found both key and fallback, add to results
            if (key && fallback && isValidKey(key)) {
                const line = objLiteral.getStartLineNumber();
                if (!result.has(key)) {
                    result.set(key, { key, fallback, file: filePath, line });
                }
            }
        }
        
    } catch (error) {
        console.error(`${RED}Error processing ${filePath}:${RESET}`, error);
    }
    
    return result;
}

/**
 * Find all translations.ts files in the project.
 */
function findTranslationFiles(): string[] {
    return glob.sync("**/translations.ts", {
        ignore: [
            "**/node_modules/**",
            "**/.next/**",
            "**/dist/**",
            "**/build/**",
            "**/coverage/**",
        ],
        absolute: true,
    });
}

// ============================================================
// OUTPUT — write only when the contents actually changed
// ============================================================

/**
 * Load an existing target YAML into a key map, or null when it is absent or
 * unparseable (in which case no key-level summary can be produced — the text
 * comparison still decides).
 */
function loadExistingKeys(yamlPath: string): Record<string, unknown> | null {
    if (!fs.existsSync(yamlPath)) return null;
    try {
        const data = yaml.load(fs.readFileSync(yamlPath, "utf8"));
        if (data && typeof data === "object" && !Array.isArray(data)) {
            return data as Record<string, unknown>;
        }
        return null;
    } catch (error) {
        console.log(`${GRAY}   (could not parse the existing target: ${error})${RESET}`);
        return null;
    }
}

/**
 * Report how the new key map differs from the existing one.
 */
function summariseChange(existing: Record<string, unknown> | null, newKeys: Map<string, string>): void {
    if (existing === null) {
        console.log(`   no readable previous version — ${newKeys.size} keys would be written`);
        return;
    }

    const added = Array.from(newKeys.keys()).filter((k) => !(k in existing)).sort();
    const removed = Object.keys(existing).filter((k) => !newKeys.has(k)).sort();
    const changed = Array.from(newKeys.keys())
        .filter((k) => k in existing && existing[k] !== newKeys.get(k))
        .sort();

    console.log(`   +${added.length} added, -${removed.length} removed, ~${changed.length} changed value(s)`);

    const show = (label: string, keys: string[]): void => {
        if (keys.length === 0) return;
        const shown = keys.slice(0, 10).join(", ");
        const more = keys.length > 10 ? ` … (+${keys.length - 10} more)` : "";
        console.log(`     ${label}: ${shown}${more}`);
    };

    show("added", added);
    show("removed", removed);
    show("changed", changed);
}

/**
 * Write `content` to `target`, but only when it differs from what is there.
 *
 * The content is first rendered to a temporary *.yaml file, so a run that
 * changes nothing never touches the target — no mtime churn, and no spurious
 * "modified" entry in git. The temporary file is removed on both paths.
 *
 * Returns true when the target differs from `content` (i.e. a write is
 * needed). With `checkOnly` the target is left untouched even then, so a
 * caller can ask "is this file current?" without any side effect.
 */
function writeIfChanged(content: string, target: string, newKeys: Map<string, string>, checkOnly: boolean): boolean {
    const tmpPath = path.join(os.tmpdir(), `extract-translations-${crypto.randomBytes(8).toString("hex")}.yaml`);
    try {
        fs.writeFileSync(tmpPath, content, "utf8");

        const existingText = fs.existsSync(target) ? fs.readFileSync(target, "utf8") : null;
        if (existingText === content) {
            console.log(`${GREEN}✅${RESET} No changes — ${CYAN}${target}${RESET} is already up to date (${newKeys.size} keys, ${Buffer.byteLength(content)} bytes).`);
            return false;
        }

        console.log(`${YELLOW}📝${RESET} ${CYAN}${target}${RESET} is out of date (${newKeys.size} keys, ${Buffer.byteLength(content)} bytes).`);
        summariseChange(loadExistingKeys(target), newKeys);

        if (checkOnly) {
            console.log(`   --check: leaving ${target} untouched.`);
            return true;
        }

        fs.mkdirSync(path.dirname(target), { recursive: true });
        // writeFileSync, NOT copyFileSync: copyFileSync adopts the source's
        // mode, which would strip the target's 664 down to a temp file's 600.
        // Writing into the existing file leaves its mode alone, and it works
        // when /tmp is a different filesystem.
        fs.writeFileSync(target, content, "utf8");
        console.log(`${GREEN}✅${RESET} Written ${newKeys.size} keys to ${target}`);
        return true;
    } finally {
        fs.rmSync(tmpPath, { force: true });
    }
}

// ============================================================
// MAIN
// ============================================================

function main() {
    const argv = process.argv.slice(2);
    const checkOnly = argv.includes("--check");

    // --output <path> diverts the write. The shared-key linter uses it so it can
    // compare live declarations without touching a locale file: en.yaml belongs
    // to the translation pipeline, and its mtime is that pipeline's own state.
    let outputPath: string | null = null;
    const outIdx = argv.indexOf("--output");
    if (outIdx !== -1) {
        const value = argv[outIdx + 1];
        if (!value || value.startsWith("--")) {
            console.error("extract-translations: --output requires a path");
            process.exit(2);
        }
        outputPath = path.resolve(value);
    }

    console.log("🔍 Extracting translation keys using ts-morph...");
    
    const files = findTranslationFiles();
    console.log(`📁 Found ${files.length} translation files:`);
    for (const file of files) {
        console.log(`   - ${path.relative(process.cwd(), file)}`);
    }

    const allKeys = new Map<string, KeyInfo>();
    let duplicateCount = 0;
    let sameFallbackCount = 0;
    let differentFallbackCount = 0;

    for (const file of files) {
        const keys = extractFromFile(file);
        for (const [key, info] of keys) {
            if (allKeys.has(key)) {
                duplicateCount++;
                const existing = allKeys.get(key)!;
                if (existing.fallback === info.fallback) {
                    sameFallbackCount++;
                    console.log(`${GREEN}✓${RESET} Duplicate key: ${CYAN}${key}${RESET} - same fallback`);
                } else {
                    differentFallbackCount++;
                    console.log(`${RED}✗${RESET} ${RED}Duplicate key: ${CYAN}${key}${RESET} ${RED}- DIFFERENT fallback values:${RESET}`);
                    console.log(`   ${GREEN}${existing.fallback}${RESET} ${GRAY}(${path.relative(process.cwd(), existing.file)}:${existing.line})${RESET}`);
                    console.log(`   ${RED}${info.fallback}${RESET} ${GRAY}(${path.relative(process.cwd(), file)}:${info.line})${RESET}`);
                }
            } else {
                allKeys.set(key, info);
            }
        }
    }

    console.log(`📊 Found ${allKeys.size} unique keys`);
    if (duplicateCount > 0) {
        console.log(`   ${duplicateCount} duplicate(s): ${GREEN}${sameFallbackCount} same fallback${RESET}, ${RED}${differentFallbackCount} different fallback${RESET}`);
    }

    // Build final key map
    const finalKeys = new Map<string, string>();
    for (const [key, info] of allKeys) {
        finalKeys.set(key, info.fallback);
    }

    // Write to en.yaml (or --output) — only when its contents actually changed
    const yamlPath = outputPath ?? path.join(process.cwd(), "locales", "en.yaml");
    
    const yamlObj: Record<string, string> = {};
    for (const [key, value] of finalKeys) {
        yamlObj[key] = value;
    }

    const sortedObj: Record<string, string> = {};
    for (const key of Object.keys(yamlObj).sort()) {
        sortedObj[key] = yamlObj[key];
    }

    const yamlStr = yaml.dump(sortedObj, { 
        indent: 2, 
        lineWidth: 120,
        quotingType: '"',
        forceQuotes: true,
    });
    
    const changed = writeIfChanged(yamlStr, yamlPath, finalKeys, checkOnly);

    // Default: always exit 0. --check: exit 1 when the target is out of date,
    // so a build or a pipeline can gate on it without parsing output.
    if (checkOnly) {
        process.exit(changed ? 1 : 0);
    }
}

main();