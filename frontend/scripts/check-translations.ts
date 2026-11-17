// scripts/check-translations.ts
// ============================================================
// FRONTEND TRANSLATION-COMPLIANCE LINTER
// Detects hardcoded English in the frontend (app/, components/, lib/) that
// bypasses the translation system: JSX text nodes and user-visible attributes
// (placeholder / title / aria-label / alt) whose value passes the content
// classifier (prose, or a Title-Case single-word label). Machine values —
// identifiers, URLs, paths, status words, all-caps acronyms — are left alone.
// Mirrors the content-half rules of backend check-translations.py.
// ============================================================

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { glob } from "glob";
import yaml from "js-yaml";
import { Node, ObjectLiteralExpression, Project, SourceFile, SyntaxKind } from "ts-morph";

/** The run's local time as ISO 8601 with its UTC offset — the same shape the
 * Python linters print on their run-identity line. */
function runTimestamp(d = new Date()): string {
    const pad = (n: number) => String(Math.abs(n)).padStart(2, "0");
    const offsetMinutes = -d.getTimezoneOffset();
    const sign = offsetMinutes < 0 ? "-" : "+";
    return (
        `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
        `T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}` +
        `${sign}${pad(Math.floor(Math.abs(offsetMinutes) / 60))}:${pad(Math.abs(offsetMinutes) % 60)}`
    );
}

// User-visible attributes (the "safe four"). className/id/key/value/type/role
// and data-* are deliberately excluded (machine values, not display text).
const SAFE_ATTRS = new Set(["placeholder", "title", "aria-label", "alt"]);

interface Finding {
    file: string;
    line: number;
    kind: string;
    text: string;
    /** The string the registry matches on, when the finding is about one.
     * Key-shaped findings — unreferenced, envelope, duplicate, redundant,
     * duplicate-fallback — carry none: the registry accepts strings, not key
     * names. */
    matchKey?: string;
}

/**
 * Content classifier: natural language (translate it) vs machine value (skip).
 * Prose is "letters + whitespace"; a single word is a label only when Title
 * Case. Identifiers (digits/underscores), punctuation (URLs, paths, codes),
 * all-caps acronyms, and all-lowercase status words are machine values.
 */
function isTranslatable(value: string): boolean {
    if (!value) return false;
    // Brand/product names are not special-cased here: they are permanent
    // whitelist entries, so the acceptance is reported rather than silent.
    if (/[a-zA-Z]/.test(value) && /\s/.test(value)) return true; // prose
    if (/[0-9_]/.test(value)) return false; // identifier / code
    if (!/^[A-Za-z]+$/.test(value)) return false; // punctuation (URL, path, "sk-...")
    if (value === value.toUpperCase()) return false; // all-caps (NULL, ISIN)
    if (value === value.toLowerCase()) return false; // all-lowercase (localhost)
    // Title Case single word (Save, Column, Welcome)
    return value[0] === value[0].toUpperCase() && value.slice(1) === value.slice(1).toLowerCase();
}

// ── Whitelist registry ──────────────────────────────────
// config/translation-whitelist.yaml at the repository root — one source of
// truth for all three linters. Resolved from this script's own location, never
// from the shell's cwd: the linter is run from frontend/, but where its policy
// file lives must not depend on that.
const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const REGISTRY_PATH = path.resolve(SCRIPT_DIR, "..", "..", "config", "translation-whitelist.yaml");

// ── Envelope sources ────────────────────────────────────
// A declared key can reach a user without being named in frontend source: the
// coded-envelope path translates a key that arrives in a backend response field
// (`translate({ key: data.error, fallback: … })`), so no static reference to it
// exists anywhere — not a property path, not a string. A key that a backend also
// declares is reachable that way, which is something the reference check cannot
// see by itself, and the reason such a key is reported as ENVELOPE-KEY rather
// than as unreferenced.
// Both are read as sources, never as generated locale files: the declaration is
// the truth, and a stale extract would misclassify a key declared since the last
// pipeline run.
const BACKEND_PY_ROOT = path.resolve(SCRIPT_DIR, "..", "..", "backend", "src");
const GO_REGISTRY_PATH = path.resolve(
    SCRIPT_DIR, "..", "..", "..", "workbench-go", "internal", "translate", "registry.go",
);

interface WhitelistEntry {
    text: string;
    kind: string;
    scope: string;
    sites: string[];
    /** Which linter owns this entry — the tool that should report it if the
     * string stops occurring. One registry serves three linters scanning three
     * different trees, so an entry owned by another side is unmatched here by
     * construction; without this field every run reported about two thirds of
     * the registry as STALE, which is noise that teaches readers to ignore the
     * line. It does NOT restrict acceptance — every entry still matches a
     * finding in every tool, so a mislabelled side cannot let an unaccepted
     * string through. */
    side: string;
    visible: boolean;
    reason: string;
}

/**
 * Load and validate the registry, naming every problem found.
 *
 * Returns the entries that passed validation and how many problems were
 * reported. A non-zero count means the registry could not be applied in full,
 * which main() turns into exit code 2 — the same code this script already uses
 * for "the tool could not do its job".
 *
 * Problems go to the report's own output: a registry the linter cannot apply
 * means the linter has failed, and the reason has to be readable where the
 * findings are. Validation runs to completion, so every bad entry is named in
 * one pass, and an entry that fails validation is skipped rather than guessed
 * at — which reports MORE findings, never fewer.
 */
function loadWhitelist(
    registryPath: string = REGISTRY_PATH,
): { entries: WhitelistEntry[]; problems: number } {
    let problems = 0;
    const report = (message: string): void => {
        problems += 1;
        console.log(message);
    };

    let raw: string;
    try {
        raw = fs.readFileSync(registryPath, "utf8");
    } catch (e) {
        const code = (e as NodeJS.ErrnoException).code;
        report(
            code === "ENOENT"
                ? `WHITELIST-MISSING: ${registryPath} — every finding is reported`
                : `WHITELIST-UNREADABLE: ${registryPath} — ${e}; every finding is reported`,
        );
        return { entries: [], problems };
    }

    let data: unknown;
    try {
        data = yaml.load(raw);
    } catch (e) {
        report(`WHITELIST-UNREADABLE: ${registryPath} — ${e}; every finding is reported`);
        return { entries: [], problems };
    }

    const listed = (data as { entries?: unknown[] } | null)?.entries ?? [];
    const entries: WhitelistEntry[] = [];
    const seen = new Set<string>();
    listed.forEach((item, index) => {
        const e = item as Record<string, unknown> | null;
        // A null entry carries no fields to validate; name it and move on. Every
        // read below indexes e directly, so it must be a mapping from here.
        if (!e) {
            report(`WHITELIST-INVALID: entry ${index + 1} — no text; skipped`);
            return;
        }
        const text = typeof e?.text === "string" ? (e.text as string) : "";
        if (!text) {
            report(`WHITELIST-INVALID: entry ${index + 1} — no text; skipped`);
            return;
        }
        if (seen.has(text)) {
            report(`WHITELIST-DUPLICATE: ${JSON.stringify(text)} — later entry skipped`);
            return;
        }
        const kind = e["kind"];
        // A missing scope defaults to "value"; the check below rejects anything
        // that is not exactly value|sites, so a string is all that survives here.
        const scope = (e["scope"] ?? "value") as string;
        if (kind !== "permanent" && kind !== "debt") {
            report(
                `WHITELIST-INVALID: ${JSON.stringify(text)} — kind ${JSON.stringify(kind)} is not permanent|debt; skipped`,
            );
            return;
        }
        if (scope !== "value" && scope !== "sites") {
            report(
                `WHITELIST-INVALID: ${JSON.stringify(text)} — scope ${JSON.stringify(scope)} is not value|sites; skipped`,
            );
            return;
        }
        const sites = Array.isArray(e["sites"]) ? (e["sites"] as string[]) : [];
        if (scope === "sites" && sites.length === 0) {
            report(`WHITELIST-INVALID: ${JSON.stringify(text)} — scope sites with no sites recorded; skipped`);
            return;
        }
        const side = (e["side"] ?? "any") as string;
        if (side !== "frontend" && side !== "python" && side !== "go" && side !== "any") {
            report(
                `WHITELIST-INVALID: ${JSON.stringify(text)} — side ${JSON.stringify(side)} is not frontend|python|go|any; skipped`,
            );
            return;
        }
        const reason = e["reason"];
        if (typeof reason !== "string" || !reason) {
            report(`WHITELIST-INVALID: ${JSON.stringify(text)} — no reason; skipped`);
            return;
        }
        seen.add(text);
        entries.push({
            text,
            kind,
            scope,
            sites,
            side,
            // Documented default: permanent entries are quiet, debt is visible.
            visible: typeof e["visible"] === "boolean" ? (e["visible"] as boolean) : kind === "debt",
            reason,
        });
    });
    return { entries, problems };
}

function printHelp(): void {
    console.log(
        `check-translations.ts — frontend translation-compliance linter

Checks:
  1. HARDCODED-JSX-TEXT    hardcoded English in JSX text
  2. HARDCODED-ATTRIBUTE   hardcoded English in placeholder/title/aria-label/alt
  3. UNREFERENCED-KEY      a declared key that nothing reaches
  4. DUPLICATE-KEY         the same key declared twice, fallbacks differing
  5. REDUNDANT-KEY         the same key declared twice, fallbacks identical
  6. TABLE-SHAPE           a declaration table breaching translation-system.md §2 (R1–R4)
  7. TABLE-SHAPE-USE       a call site reaching a table reported under 6
  8. ENVELOPE-KEY          a declared key nothing in the frontend names, that a
                           backend also declares — reachable through the coded
                           envelope, so not a defect on its own (raised by 3)
  9. DUPLICATE-FALLBACK    one fallback text declared under two or more keys of
                           the frontend's own tables (raised by 6)
 10. CALL-SITE-LITERAL     a {key, fallback} object literal passed straight to
                           translate()/translateKey() — a declaration minted at
                           the call site, which no table owns
 11. STRAY-DECLARATION     a {key, fallback} with a STRING-LITERAL fallback
                           written outside a translations.ts — a second
                           declaration of text some table already declares

10 and 11 exist because the other linters are blind to the shape. A key that
arrives as DATA — from a payload, a tool result, a stored draft — carries no
declaration with it, so wrapping it in a fresh key/fallback object at the call
site silently replaces the declared fallback with whatever the wrapper supplies.
That is how a translate call given {key, fallback: ""} rendered nothing for nine
declared keys and passed every gate. A fallback built from a VALUE is not caught
by 11 — that is the coded envelope relaying the server's rendered text, and it is
the pattern these rules point callers towards.

Findings whose subject is a string (1 and 2) are tested against the whitelist
registry before they are reported; a matched finding becomes an EXCEPTION.

Usage: node_modules/.bin/ts-node scripts/check-translations.ts [options]
       (run from frontend/)

Options:
  --whitelist=<path>  read the registry from <path> instead of
                      ${REGISTRY_PATH}
  --exceptions=default|all|none
                      which exception detail lines to print: each entry's own
                      visible flag (default), every one (all), or none (none).
                      The count always prints and the exit code never changes.
  --help              print this and exit 0

Exit codes:
  0  no findings
  1  findings
  2  the registry could not be applied in full, the declaration parser is
     broken, or the options are unusable`,
    );
}

function parseArgs(
    argv: string[],
): { whitelistPath: string | undefined; exceptionsMode: string } {
    let whitelistPath: string | undefined;
    let exceptionsMode = "default";
    for (const arg of argv) {
        if (arg === "--help") {
            printHelp();
            process.exit(0);
        }
        if (arg.startsWith("--whitelist=")) {
            const value = arg.slice("--whitelist=".length);
            if (!value) {
                console.log("USAGE-ERROR: --whitelist needs a path; see --help");
                process.exit(2);
            }
            whitelistPath = path.resolve(value);
            continue;
        }
        if (arg === "--exceptions") {
            console.log("USAGE-ERROR: --exceptions needs a value (default|all|none); see --help");
            process.exit(2);
        }
        if (arg.startsWith("--exceptions=")) {
            const value = arg.slice("--exceptions=".length);
            if (value !== "default" && value !== "all" && value !== "none") {
                console.log(
                    `USAGE-ERROR: --exceptions must be default|all|none, not ${JSON.stringify(value)}; see --help`,
                );
                process.exit(2);
            }
            exceptionsMode = value;
            continue;
        }
        console.log(`USAGE-ERROR: unknown option ${JSON.stringify(arg)}; see --help`);
        process.exit(2);
    }
    return { whitelistPath, exceptionsMode };
}

function findSourceFiles(): string[] {
    // `.tsx` carries the JSX the content checks read; `.ts` is included because
    // the declaration checks belong to the whole source tree, not to JSX. Until
    // 2026-11-04 this pattern was `.tsx` only, so a `.ts` file that is not named
    // `translations.ts` was scanned by neither this loop nor the declaration
    // scan — `lib/recipe-model.ts` held fourteen hardcoded key/fallback pairs and
    // reported nothing.
    const patterns = [
        "app/**/*.tsx", "components/**/*.tsx", "lib/**/*.tsx",
        "app/**/*.ts", "components/**/*.ts", "lib/**/*.ts",
    ];
    const ignore = ["**/node_modules/**", "**/.next/**", "**/dist/**", "**/build/**"];
    const files: string[] = [];
    for (const p of patterns) {
        files.push(...glob.sync(p, { ignore, absolute: true }));
    }
    return files;
}

// ── Checks 3 and 4: declaration-level ────────────────────────────────────
//
// The content checks above scan JSX. These scan `**/translations.ts` and ask the
// two questions the content checks cannot: is each declared key referenced
// anywhere, and is it declared once? Neither class was visible to any linter in
// the project before these checks existed.

interface Declaration {
    key: string;
    fallback: string;
    expr: string;   // full access expression, e.g. RECIPES.load_error
    file: string;   // cwd-relative
    line: number;
}

function findTranslationFiles(): string[] {
    return glob.sync("**/translations.ts", {
        ignore: ["**/node_modules/**", "**/.next/**", "**/dist/**", "**/build/**"],
        absolute: true,
    });
}

/** Files a declaration can be *used* from. `.ts` as well as `.tsx` — the JSX
 * checks never see a plain module — and the declaration files themselves
excluded. */
function findUsageFiles(): string[] {
    const patterns = [
        "app/**/*.{ts,tsx}",
        "components/**/*.{ts,tsx}",
        "lib/**/*.{ts,tsx}",
        "hooks/**/*.{ts,tsx}",
        "*.ts",
        "*.tsx",
    ];
    const ignore = [
        "**/node_modules/**",
        "**/.next/**",
        "**/dist/**",
        "**/build/**",
        "**/translations.ts",
    ];
    const files: string[] = [];
    for (const p of patterns) {
        files.push(...glob.sync(p, { ignore, absolute: true }));
    }
    return files;
}

/** The object literal behind an expression, unwrapping `as const` / `satisfies`
 * / parentheses. The declaration files all end `} as const;`, so without this the
 * walk finds nothing — and a walk that finds nothing looks like a clean run. */
function asObjectLiteral(node: Node): ObjectLiteralExpression | undefined {
    const direct = node.asKind(SyntaxKind.ObjectLiteralExpression);
    if (direct) return direct;
    const asExpr = node.asKind(SyntaxKind.AsExpression);
    if (asExpr) return asObjectLiteral(asExpr.getExpression());
    const satisfies = node.asKind(SyntaxKind.SatisfiesExpression);
    if (satisfies) return asObjectLiteral(satisfies.getExpression());
    const paren = node.asKind(SyntaxKind.ParenthesizedExpression);
    if (paren) return asObjectLiteral(paren.getExpression());
    return undefined;
}

/** Read `{ key: "...", fallback: "..." }` from an object, else null. */
function asLeaf(node: Node): { key: string; fallback: string } | null {
    const lit = asObjectLiteral(node);
    if (!lit) return null;
    let key: string | null = null;
    let fallback: string | null = null;
    for (const prop of lit.getProperties()) {
        const pa = prop.asKind(SyntaxKind.PropertyAssignment);
        if (!pa) continue;
        const name = pa.getName();
        if (name !== "key" && name !== "fallback") continue;
        const init = pa.getInitializer();
        if (!init || !init.isKind(SyntaxKind.StringLiteral)) return null;
        const value = init.asKind(SyntaxKind.StringLiteral)!.getLiteralValue();
        if (name === "key") key = value;
        else fallback = value;
    }
    return key !== null && fallback !== null ? { key, fallback } : null;
}

/** Walk an object literal, recording every translation leaf and its access path.
 * Identifier-valued properties are recorded as wrapper references rather than
 * recursed into: `models: ADMIN_MODELS` means `ADMIN.models.x` and
 * `ADMIN_MODELS.x` are the same declaration. */
function collectDeclarations(
    node: Node,
    prefix: string,
    rel: string,
    out: Declaration[],
    wrappers: Map<string, Map<string, string>>,
): void {
    const lit = asObjectLiteral(node);
    if (!lit) return;
    for (const prop of lit.getProperties()) {
        const pa = prop.asKind(SyntaxKind.PropertyAssignment);
        if (!pa) continue;
        const init = pa.getInitializer();
        if (!init) continue;
        const expr = `${prefix}.${pa.getName()}`;
        const ref = init.asKind(SyntaxKind.Identifier);
        if (ref) {
            const forObject = wrappers.get(prefix) ?? new Map<string, string>();
            forObject.set(pa.getName(), ref.getText());
            wrappers.set(prefix, forObject);
            continue;
        }
        const leaf = asLeaf(init);
        if (leaf) {
            out.push({
                key: leaf.key,
                fallback: leaf.fallback,
                expr,
                file: rel,
                line: pa.getStartLineNumber(),
            });
        } else {
            collectDeclarations(init, expr, rel, out, wrappers);
        }
    }
}

/** Every dotted form an expression can take once wrapper references are followed.
 * `ADMIN.models.description` and `ADMIN_MODELS.description` reach one declaration. */
function expandThroughWrappers(
    expr: string,
    wrappers: Map<string, Map<string, string>>,
): string[] {
    const forms = [expr];
    let current = expr;
    for (let depth = 0; depth < 4; depth++) {
        const dot = current.indexOf(".");
        if (dot <= 0) break;
        const head = current.slice(0, dot);
        const rest = current.slice(dot + 1);
        const second = rest.split(".")[0];
        const target = wrappers.get(head)?.get(second);
        if (!target) break;
        current = target + rest.slice(second.length);
        forms.push(current);
    }
    return forms;
}

/** local name -> imported name, so an aliased import still resolves. */
function aliasesOf(sf: SourceFile): Map<string, string> {
    const map = new Map<string, string>();
    for (const imp of sf.getImportDeclarations()) {
        for (const ni of imp.getNamedImports()) {
            const alias = ni.getAliasNode();
            if (alias) map.set(alias.getText(), ni.getName());
        }
    }
    return map;
}

/** One call site that names an access expression. */
interface Site {
    file: string;
    line: number;
}

/** Remember where an expression was seen, once per location. */
function recordSite(sites: Map<string, Site[]>, expr: string, file: string, line: number): void {
    const list = sites.get(expr);
    if (!list) {
        sites.set(expr, [{ file, line }]);
        return;
    }
    if (!list.some((s) => s.file === file && s.line === line)) list.push({ file, line });
}

/** Every dotted access expression in a file, the head rewritten through the
 * alias map so `A.instance_exists` matches `API_ADMIN.instance_exists`.
 * Element access with a string literal is counted too — it is a use. */
function collectUses(
    sf: SourceFile,
    aliases: Map<string, string>,
    wrappers: Map<string, Map<string, string>>,
    uses: Set<string>,
    sites: Map<string, Site[]>,
    rel: string,
): void {
    for (const pa of sf.getDescendantsOfKind(SyntaxKind.PropertyAccessExpression)) {
        const text = pa.getText().replace(/\s+/g, "");
        const dot = text.indexOf(".");
        if (dot <= 0) continue;
        const head = text.slice(0, dot);
        for (const form of expandThroughWrappers((aliases.get(head) ?? head) + text.slice(dot), wrappers)) {
            uses.add(form);
            recordSite(sites, form, rel, pa.getStartLineNumber());
        }
    }
    for (const ea of sf.getDescendantsOfKind(SyntaxKind.ElementAccessExpression)) {
        const arg = ea.getArgumentExpression();
        if (!arg || !arg.isKind(SyntaxKind.StringLiteral)) continue;
        const text = ea.getExpression().getText().replace(/\s+/g, "");
        const dot = text.indexOf(".");
        const head = dot === -1 ? text : text.slice(0, dot);
        const expr = `${aliases.get(head) ?? head}.${arg.asKind(SyntaxKind.StringLiteral)!.getLiteralValue()}`;
        for (const form of expandThroughWrappers(expr, wrappers)) {
            uses.add(form);
            recordSite(sites, form, rel, ea.getStartLineNumber());
        }
    }
}

/** Every string literal in a file — a key named as a bare string is a use, even
 * without an access path (t("key"), a key held in a data table). */
function collectStringLiterals(sf: SourceFile, out: Set<string>): void {
    for (const sl of sf.getDescendantsOfKind(SyntaxKind.StringLiteral)) {
        out.add(sl.getLiteralValue());
    }
}

/** Every key a backend declares — the Python `TranslationKey("key", …)`
 * literals under backend/src, plus the Go registry's `"key": "fallback"`
 * entries. Membership only: backend-only keys are no concern here.
 *
 * Full-line comments are blanked before the scan in both sources. One of the
 * declaration files carries `TranslationKey("key", "fallback")` in a comment as
 * an illustration, and scanning it would put the literal words into the set —
 * the same shape of trap that would make a commented-out Go map entry read as a
 * live declaration. Blanking keeps the newlines, so a declaration split across
 * lines still matches.
 *
 * Both sources are supporting inputs, read the way locales/en.yaml is: one that
 * cannot be read is named in the report's notes, never turned into a failure. */
function collectBackendKeys(): { keys: Set<string>; parts: string[] } {
    const keys = new Set<string>();
    const parts: string[] = [];

    const pyFiles = fs.existsSync(BACKEND_PY_ROOT)
        ? glob.sync("**/translations.py", { cwd: BACKEND_PY_ROOT, absolute: true })
        : [];
    if (pyFiles.length === 0) {
        parts.push(`no declarations read from ${BACKEND_PY_ROOT}`);
    } else {
        for (const file of pyFiles) {
            const source = fs
                .readFileSync(file, "utf8")
                .split("\n")
                .map((line) => (line.trimStart().startsWith("#") ? "" : line))
                .join("\n");
            for (const m of source.matchAll(/TranslationKey\(\s*"([^"]+)"/g)) keys.add(m[1]);
        }
        parts.push(`${keys.size} from backend/src/**/translations.py (${pyFiles.length} files)`);
    }

    const pythonKeys = keys.size;
    try {
        const source = fs
            .readFileSync(GO_REGISTRY_PATH, "utf8")
            .split("\n")
            .map((line) => (line.trimStart().startsWith("//") ? "" : line))
            .join("\n");
        for (const m of source.matchAll(/^\s*"([^"]+)":\s*"/gm)) keys.add(m[1]);
        parts.push(`${keys.size - pythonKeys} from workbench-go/internal/translate/registry.go`);
    } catch {
        parts.push(`no keys read from ${GO_REGISTRY_PATH}`);
    }

    return { keys, parts };
}

function main() {
    // Read and validate the registry BEFORE scanning the codebase: a scan run
    // against a registry the linter cannot apply is not worth the wait, and
    // every problem it finds belongs at the top of the report.
    const parsed = parseArgs(process.argv.slice(2));
    const whitelistPath = parsed.whitelistPath ?? REGISTRY_PATH;
    const exceptionsMode = parsed.exceptionsMode;

    // The run's identity — which tool, and when — before anything else.
    console.log(`linter:      frontend ${runTimestamp()}`);

    // Where the policy comes from and what is being examined, before anything
    // else — including before the registry is read, so a registry that cannot be
    // read is reported against the path it was looked for in.
    console.log(`whitelist:   ${whitelistPath}`);
    console.log(`source root: ${process.cwd()}`);

    const { entries: whitelist, problems: registryProblems } = loadWhitelist(whitelistPath);
    const byText = new Map<string, WhitelistEntry>();
    for (const e of whitelist) {
        if (!byText.has(e.text)) byText.set(e.text, e);
    }

    // The second input check 3 needs: which keys a backend declares. Read with
    // the registry rather than after the scan, and reported in the notes below.
    const { keys: backendKeys, parts: envelopeParts } = collectBackendKeys();

    const files = findSourceFiles();
    const findings: Finding[] = [];
    const project = new Project({ useInMemoryFileSystem: true });

    for (const filePath of files) {
        let content: string;
        try {
            content = fs.readFileSync(filePath, "utf8");
        } catch {
            continue;
        }

        const sf = project.createSourceFile(filePath, content, { overwrite: true });
        const rel = path.relative(process.cwd(), filePath);

        // Checks 10 and 11: an object literal that is NOT a declaration.
        //
        // 10 — a key/fallback pair passed straight to a translate call. The rule
        // is that a call site names a declaration; a literal is a declaration the
        // call site just made, so nothing owns it and its fallback can be
        // anything, including "".
        for (const call of sf.getDescendantsOfKind(SyntaxKind.CallExpression)) {
            const callee = call.getExpression().getText().replace(/\s+/g, "");
            if (callee !== "translate" && callee !== "translateKey") continue;
            const first = call.getArguments()[0];
            if (!first) continue;
            const leaf = asLeaf(first);
            if (!leaf) continue;
            findings.push({
                file: rel,
                line: first.getStartLineNumber(),
                kind: "CALL-SITE-LITERAL",
                text: `${leaf.key} with fallback ${JSON.stringify(leaf.fallback)}`,
            });
        }

        // 11 — a key/fallback pair with a LITERAL fallback anywhere but a
        // translations file. The predicate is "string literal", which is what
        // separates a second declaration from the envelope: `{key: data.error,
        // fallback: data.message}` relays text the server already rendered, and
        // is deliberately not reported.
        if (!/(^|\/)translations\.ts$/.test(rel)) {
            for (const obj of sf.getDescendantsOfKind(SyntaxKind.ObjectLiteralExpression)) {
                const leaf = asLeaf(obj);
                if (!leaf) continue;
                findings.push({
                    file: rel,
                    line: obj.getStartLineNumber(),
                    kind: "STRAY-DECLARATION",
                    text: `${leaf.key} = ${JSON.stringify(leaf.fallback)}`,
                });
            }
        }

        // Check 1: hardcoded English in JSX text nodes.
        for (const node of sf.getDescendantsOfKind(SyntaxKind.JsxText)) {
            const text = node.getText().trim();
            if (!text) continue; // whitespace-only formatting
            if (isTranslatable(text)) {
                findings.push({ file: rel, line: node.getStartLineNumber(), kind: "HARDCODED-JSX-TEXT", text, matchKey: text });
            }
        }

        // Check 2: hardcoded English in user-visible attributes.
        for (const attr of sf.getDescendantsOfKind(SyntaxKind.JsxAttribute)) {
            if (!SAFE_ATTRS.has(attr.getNameNode().getText())) continue;
            const init = attr.getInitializer();
            if (!init || !init.isKind(SyntaxKind.StringLiteral)) continue;
            const value = init.asKind(SyntaxKind.StringLiteral)!.getLiteralValue();
            if (isTranslatable(value)) {
                findings.push({ file: rel, line: attr.getStartLineNumber(), kind: "HARDCODED-ATTRIBUTE", text: value, matchKey: value });
            }
        }
    }

    // --- Checks 3 & 4: declaration-level ---
    const declarations: Declaration[] = [];
    const wrappers = new Map<string, Map<string, string>>();
    const declFilePaths = findTranslationFiles();
    for (const filePath of declFilePaths) {
        let content: string;
        try {
            content = fs.readFileSync(filePath, "utf8");
        } catch {
            continue;
        }
        const sf = project.createSourceFile(filePath, content, { overwrite: true });
        const rel = path.relative(process.cwd(), filePath);
        for (const stmt of sf.getVariableStatements()) {
            for (const decl of stmt.getDeclarations()) {
                const init = decl.getInitializer();
                if (init) collectDeclarations(init, decl.getName(), rel, declarations, wrappers);
            }
        }
    }

    // A parser that silently returns nothing would report both new checks as
    // clean — which is exactly how an unreferenced key stayed hidden. Fail loudly.
    if (declarations.length === 0 && declFilePaths.length > 0) {
        console.error(
            `check-translations: parsed 0 declarations from ${declFilePaths.length} translations.ts file(s) — the declaration parser is broken`,
        );
        process.exit(2);
    }

    const uses = new Set<string>();
    const literals = new Set<string>();
    const useSites = new Map<string, Site[]>();
    for (const filePath of findUsageFiles()) {
        let content: string;
        try {
            content = fs.readFileSync(filePath, "utf8");
        } catch {
            continue;
        }
        const sf = project.createSourceFile(filePath, content, { overwrite: true });
        collectUses(sf, aliasesOf(sf), wrappers, uses, useSites, path.relative(process.cwd(), filePath));
        collectStringLiterals(sf, literals);
    }

    // Check 3: a declaration nothing reaches. Reported as "no reference in
    // frontend source" in intent, never as "dead": a key can still reach a user
    // without being named here, because getErrorMessageFromData translates keys
    // that arrive in a backend error payload. Referenced > bare string literal
    // > unreferenced.
    // That last class splits, and the report has to say which half a key is in.
    // A key a backend also declares is reachable through the coded envelope:
    // ENVELOPE-KEY, and not a defect on its own. What remains is
    // UNREFERENCED-KEY — nothing in the frontend names it and no backend
    // declares it — and that is the class worth reading.
    // Unreferenced-ness is a property of the KEY, not of one declaration. A key
    // declared twice may be reached through the other object (DATASETS.x versus
    // DATASET_DETAIL.x); judging per declaration reported those as unreferenced
    // while the key was demonstrably in use — and the duplicate check already
    // reports the redundancy separately.
    const liveKeys = new Set<string>();
    for (const d of declarations) {
        if (uses.has(d.expr) || literals.has(d.key)) liveKeys.add(d.key);
    }
    const reported = new Set<string>();
    const ordered = [...declarations].sort(
        (a, b) => a.file.localeCompare(b.file) || a.line - b.line,
    );
    for (const d of ordered) {
        if (liveKeys.has(d.key) || reported.has(d.key)) continue;
        reported.add(d.key);
        findings.push({
            file: d.file,
            line: d.line,
            kind: backendKeys.has(d.key) ? "ENVELOPE-KEY" : "UNREFERENCED-KEY",
            text: d.key,
        });
    }

    // Check 4: the same key declared more than once. Differing fallbacks are a
    // defect — the extractor scans every copy and the DB is keyed by
    // (key, language), so the last import wins. Identical fallbacks are
    // redundancy: extracted N times, and the first edit to one copy diverges it.
    const byKey = new Map<string, Declaration[]>();
    for (const d of declarations) {
        const list = byKey.get(d.key);
        if (list) list.push(d);
        else byKey.set(d.key, [d]);
    }
    for (const [key, list] of byKey) {
        if (list.length < 2) continue;
        const sorted = [...list].sort((a, b) => a.file.localeCompare(b.file) || a.line - b.line);
        const identical = sorted.every((d) => d.fallback === sorted[0].fallback);
        const where = sorted
            .map((d) => (identical ? `${d.file}:${d.line}` : `${d.file}:${d.line} -> ${d.fallback}`))
            .join(" ; ");
        findings.push({
            file: sorted[0].file,
            line: sorted[0].line,
            kind: identical ? "REDUNDANT-KEY" : "DUPLICATE-KEY",
            text: `${key} declared ${sorted.length}x with ${identical ? "identical fallback" : "differing fallbacks"} - ${where}`,
        });
    }

    // Check 5 and its companion: the shape of a declaration table —
    // translation-system.md §2, rules R1–R4. These findings carry no matchKey:
    // the registry accepts strings, and a malformed table is a defect to fix
    // rather than a string to accept. Each malformed declaration is reported at
    // its own object, and the call sites that reach it are reported separately —
    // the table and its callers are different work.
    const shapeViolations: Declaration[] = [];
    const shape = (d: Declaration, rule: string, detail: string): void => {
        findings.push({
            file: d.file,
            line: d.line,
            kind: "TABLE-SHAPE",
            text: `${rule} ${d.expr} -> ${d.key} — ${detail}`,
        });
        shapeViolations.push(d);
    };

    // R1 — a level that repeats a word the key already carries is depth without
    // meaning: the leaf names the thing, and the intermediate segment adds
    // nothing. R3 — the path must name the key: with the module prefix
    // stripped, what remains is exactly the leaf's path below the table root.
    for (const d of declarations) {
        const path = d.expr.split(".");
        if (path.length < 2) continue;
        const leafPath = path.slice(1);
        const lower = new Set(d.key.split("."));
        const redundant = path.slice(1, -1).filter((segment) => lower.has(segment));
        if (redundant.length) {
            shape(d, "R1", `intermediate segment(s) repeat the key: ${redundant.join(".")}`);
        }
        const tail = d.key.split(".").slice(-leafPath.length);
        if (tail.join(".") !== leafPath.join(".")) {
            shape(d, "R3", "the path does not name the key");
        }
    }

    // R2 and R4 — enumeration data is not prose. A fallback that leads with a
    // bare number is data (R4); two leaves in one table whose fallbacks differ
    // only by an embedded number are an enumeration family written out by hand
    // (R2), which is one parameterised key's job.
    const digitShaped = new Map<string, Declaration>();
    for (const d of declarations) {
        const fallback = d.fallback.trim();
        if (/^\d/.test(fallback)) {
            shape(d, "R4", `fallback is enumeration data, not prose: ${JSON.stringify(fallback)}`);
            continue;
        }
        const table = d.expr.split(".")[0];
        const family = `${table}|${fallback.replace(/\d+/g, "#")}`;
        const first = digitShaped.get(family);
        if (first && first.fallback.trim() !== fallback) {
            shape(
                d,
                "R2",
                `${JSON.stringify(first.fallback)} vs ${JSON.stringify(fallback)} — an enumeration family, not one parameterised key`,
            );
        } else if (!first) {
            digitShaped.set(family, d);
        }
    }

    // The call sites that reach each malformed declaration, as their own kind at
    // their own location. The shape finding says the table is wrong; these say
    // who depends on it, which is the blast radius a correction has to carry.
    const flagged = new Map<string, Declaration>();
    for (const d of shapeViolations) if (!flagged.has(d.expr)) flagged.set(d.expr, d);
    for (const [expr, d] of flagged) {
        for (const site of useSites.get(expr) ?? []) {
            findings.push({
                file: site.file,
                line: site.line,
                kind: "TABLE-SHAPE-USE",
                text: `${expr} (declared at ${d.file}:${d.line})`,
            });
        }
    }
    // Check 6: one English text declared under two or more distinct keys.
    // The rule that two keys must never carry the same fallback is mechanical in
    // its reason: the table is keyed by (key, language), so one text under two
    // keys is one string stored twice, and the second copy is the one that
    // drifts. Reported per group rather than per key — the correction is to
    // collapse the key names onto one, which is a single decision, and the group
    // is that decision's scope.
    // Scope is the frontend's own declarations. A text shared with a backend key
    // is a different question with a different answer: the frontend's fallback is
    // also its compiled tier-3 value and the object its typed reference points
    // at, so "collapse toward the backend's key" costs more than it saves — see
    // workbench-frontend-translation-discussion-notes.md §14. Two declarations of
    // the SAME key are not a group here; that is check 4's subject.
    // No matchKey, as the other key-shaped kinds: a text declared twice is a
    // defect to fix, not a string to accept.
    const byFallback = new Map<string, Declaration[]>();
    for (const d of declarations) {
        const list = byFallback.get(d.fallback);
        if (list) list.push(d);
        else byFallback.set(d.fallback, [d]);
    }
    for (const [fallback, list] of byFallback) {
        const keys = [...new Set(list.map((d) => d.key))].sort();
        if (keys.length < 2) continue;
        const first = [...list].sort((a, b) => a.file.localeCompare(b.file) || a.line - b.line)[0];
        findings.push({
            file: first.file,
            line: first.line,
            kind: "DUPLICATE-FALLBACK",
            text: `${fallback} — shared by ${keys.length} keys: ${keys.join(" ; ")}`,
        });
    }

    findings.sort((a, b) => a.file.localeCompare(b.file) || a.line - b.line);

    // --- Whitelist: a matched finding becomes an exception ------------------
    const unaccepted = findings.filter((f) => !(f.matchKey && byText.has(f.matchKey)));
    const matched = new Map<string, Finding[]>();
    for (const f of findings) {
        if (!f.matchKey || !byText.has(f.matchKey)) continue;
        const list = matched.get(f.matchKey);
        if (list) list.push(f);
        else matched.set(f.matchKey, [f]);
    }

    for (const f of unaccepted) {
        console.log(`${f.kind}: ${f.file}:${f.line} — ${JSON.stringify(f.text.replace(/\s+/g, " ").trim())}`);
    }

    let shown = 0;
    for (const [text, group] of matched) {
        const entry = byText.get(text)!;
        const sites = new Set(entry.sites);
        for (const f of group) {
            const site = `${f.file}:${f.line}`;
            const newSite = entry.scope === "sites" && !sites.has(site);
            // A match somewhere new is a change rather than a routine encounter,
            // so `default` prints it even when the entry is not visible — the
            // same reason a stale entry always prints. `none` is an explicit
            // request for no detail lines at all, and it wins over both.
            const show =
                exceptionsMode === "all" ||
                (exceptionsMode === "default" && (entry.visible || newSite));
            if (show) {
                shown += 1;
                const label = newSite ? "EXCEPTION-NEW-SITE" : "EXCEPTION";
                console.log(
                    `${label}: ${site} — ${JSON.stringify(f.text.replace(/\s+/g, " ").trim())}`,
                );
                console.log(`           [${entry.kind}] ${entry.reason}`);
                if (newSite) {
                    const recorded = [...sites].sort().join(", ") || "(no sites recorded)";
                    console.log(`           recorded at ${recorded}; review or update the entry`);
                }
            }
        }
    }

    // Stale entries are detail lines, so the mode gates them like any other:
    // `none` prints none of them, and the count below still prints.
    // Only the entries this side owns. An entry owned by another linter is not
    // this run's business — it is unmatched here by construction, and reporting
    // it as stale would say nothing about the string, only about which tree this
    // tool reads.
    if (exceptionsMode !== "none") {
        for (const e of whitelist) {
            if (e.side !== "frontend" && e.side !== "any") continue;
            if (!matched.has(e.text)) {
                console.log(`STALE-ENTRY: ${JSON.stringify(e.text)} — no match in this run (side: ${e.side})`);
            }
        }
    }

    if (whitelist.length) {
        const encountered = [...matched.values()].reduce((total, group) => total + group.length, 0);
        const hint = shown < encountered && exceptionsMode !== "all" ? "; --exceptions=all to list" : "";
        console.log(
            `EXCEPTIONS: ${encountered} encountered (${shown} shown, ${encountered - shown} not visible${hint})`,
        );
    }

    const n = unaccepted.length;
    if (n) {
        console.log(`${n} finding(s)`);
    } else {
        console.log("frontend translation-compliance check passed");
    }

    // Which keys the envelope classification had to work with. A run whose
    // classification could not be applied in full must not look like one where it
    // was — the reason the two header lines above exist — but this is a note and
    // not a gate: an unreadable source narrows the classification instead of
    // breaking the run.
    console.log(
        `note: envelope sources: ${envelopeParts.join(", ")} — ${backendKeys.size} distinct keys`,
    );

    // Self-guard: the declarations parsed should account for the keys the
    // extractor emits. A mismatch normally means locales/en.yaml needs
    // re-extracting rather than that the checks are wrong, so it is reported as
    // a note and never as a failure.
    try {
        const data = yaml.load(fs.readFileSync(path.join(process.cwd(), "locales", "en.yaml"), "utf8"));
        const yamlKeys = Object.keys(data as Record<string, unknown>).length;
        const distinct = byKey.size;
        console.log(
            yamlKeys === distinct
                ? `note: ${distinct} distinct declared keys reconcile with locales/en.yaml (${yamlKeys})`
                : `note: ${distinct} distinct declared keys vs ${yamlKeys} keys in locales/en.yaml - re-run the extractor if declarations changed`,
        );
    } catch {
        // locales/en.yaml unreadable: the reconciliation is a diagnostic, not a gate.
    }

    // A registry that could not be applied in full is the same class of failure
    // as the broken-parser guard above, and outranks unaccepted findings.
    if (registryProblems) {
        console.log(
            `WHITELIST-BROKEN: ${registryProblems} problem(s) — the registry was not applied in full; exit code 2`,
        );
        process.exit(2);
    }

    process.exit(n ? 1 : 0);
}

main();
