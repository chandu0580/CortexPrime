import { readFileSync, readdirSync, statSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

/**
 * A fitness test for the browser boundary.
 *
 * The Python architecture gate enforces the backend's boundaries and cannot see
 * TypeScript, so a `BND-PRODUCT-UI-*` rule added there would restate rules that
 * already hold and still not cover the code it names. This is the check that
 * actually covers the workspace: every file in it is read, and any second route
 * out of the browser fails the suite.
 *
 * Sensitivity: these assertions were confirmed to fail when a forbidden import
 * or a fetch to another origin is introduced — they are not vacuous greps over
 * an empty file list.
 */

const ROOT = path.resolve(__dirname, "../..")

const WORKSPACE_DIRS = [
    "app/investigator",
    "components/investigator",
    "hooks/queries/useInvestigator.ts",
    "lib/investigator",
]

function collect(target: string): string[] {
    const full = path.join(ROOT, target)
    const stat = statSync(full)
    if (stat.isFile()) return [full]
    return readdirSync(full).flatMap((entry) => collect(path.join(target, entry)))
}

const FILES = WORKSPACE_DIRS.flatMap(collect).filter((f) => /\.tsx?$/.test(f))

function read(file: string): string {
    return readFileSync(file, "utf8")
}

/**
 * The same source with comments removed.
 *
 * Used by the checks that scan for forbidden *machinery*. Without this, a file
 * that documents "this deliberately uses no embeddings" fails the no-embeddings
 * check — which would make the test punish the one thing it wants: saying out
 * loud what the code does not do.
 */
function code(file: string): string {
    return read(file)
        .replace(/\/\*[\s\S]*?\*\//g, " ")
        .replace(/(^|[^:])\/\/.*$/gm, "$1")
        .replace(/\{\s*\/\*[\s\S]*?\*\/\s*\}/g, " ")
}

describe("the workspace has exactly one route out of the browser", () => {
    it("finds the workspace files (guards against a vacuous pass)", () => {
        expect(FILES.length).toBeGreaterThan(8)
    })

    it("no workspace file imports the V1 api client or axios", () => {
        for (const file of FILES) {
            const source = read(file)
            expect(source, `${file} must not import the V1 api-client`).not.toMatch(
                /from\s+["']@?\/?(lib\/)?api-client["']/,
            )
            expect(source, `${file} must not import axios`).not.toMatch(
                /from\s+["']axios["']/,
            )
        }
    })

    it("only the product-api module calls fetch", () => {
        const offenders = FILES.filter(
            (file) =>
                !file.endsWith(path.join("lib", "product-api.ts")) &&
                /\bfetch\s*\(/.test(read(file)),
        )
        expect(offenders, "only lib/product-api.ts may call fetch").toEqual([])
    })

    it("no workspace file names a provider, connector, worker or credential path", () => {
        const forbidden = [
            /kubernetes\.default/i,
            /:6443/,
            /\/api\/v1\/(providers|connectors|credentials|workers|transport|gateway)/i,
            /prometheus.*\/api\/v1\/query/i,
            /kubeconfig/i,
            /bearer\s+ey/i,
        ]
        for (const file of FILES) {
            const source = code(file)
            for (const pattern of forbidden) {
                expect(source, `${file} must not reference ${pattern}`).not.toMatch(pattern)
            }
        }
    })

    it("no workspace file issues a non-GET request", () => {
        for (const file of FILES) {
            const source = read(file)
            // The client exposes productGet and nothing else; these assert that
            // no component reintroduces a verb by hand.
            expect(source, `${file} must not send a POST`).not.toMatch(/method:\s*["']POST["']/)
            expect(source, `${file} must not send a PUT`).not.toMatch(/method:\s*["']PUT["']/)
            expect(source, `${file} must not send a PATCH`).not.toMatch(/method:\s*["']PATCH["']/)
            expect(source, `${file} must not send a DELETE`).not.toMatch(/method:\s*["']DELETE["']/)
        }
    })

    it("no workspace file reads or writes a tenant in browser storage", () => {
        for (const file of FILES) {
            const source = read(file)
            expect(source, `${file} must not touch localStorage`).not.toMatch(/localStorage/)
            expect(source, `${file} must not touch sessionStorage`).not.toMatch(/sessionStorage/)
            expect(source, `${file} must not set a cookie`).not.toMatch(/document\.cookie\s*=/)
        }
    })

    it("the product API client is the only module naming a backend base URL", () => {
        const offenders = FILES.filter(
            (file) =>
                !file.endsWith(path.join("lib", "product-api.ts")) &&
                /https?:\/\/localhost:\d+|NEXT_PUBLIC_[A-Z_]*API/.test(read(file)),
        )
        expect(offenders).toEqual([])
    })
})

describe("no execution, approval or autonomy control exists in the workspace", () => {
    const ACTION_WORDS = [
        /onClick=\{[^}]*\bapprove\b/i,
        /onClick=\{[^}]*\bexecute\b/i,
        /onClick=\{[^}]*\bremediat/i,
        /onClick=\{[^}]*\bpromote\b/i,
        /useMutation\s*\(/,
    ]

    it("has no mutation hook and no action handler", () => {
        for (const file of FILES) {
            const source = read(file)
            for (const pattern of ACTION_WORDS) {
                expect(source, `${file} must not contain ${pattern}`).not.toMatch(pattern)
            }
        }
    })

    it("renders autonomy without an input that could change it", () => {
        const workspace = read(path.join(ROOT, "components/investigator/Workspace.tsx"))
        expect(workspace).toMatch(/Autonomy/)
        // The one <input> in the workspace tree is the World predicate box, and
        // it lives in WorldStatePanel, not here.
        expect(workspace).not.toMatch(/<input/i)
        expect(workspace).not.toMatch(/<select/i)
        expect(workspace).not.toMatch(/type="checkbox"/i)
    })
})

describe("no RAG was added (Part Q)", () => {
    it("names no embedding, vector or semantic-search machinery", () => {
        for (const file of FILES) {
            const source = code(file)
            for (const pattern of [/embedding/i, /pgvector/i, /\bvector\s*search/i,
                                   /semantic\s*search/i, /\bchroma\b/i, /\bneo4j\b/i]) {
                expect(source, `${file} must not reference ${pattern}`).not.toMatch(pattern)
            }
        }
    })
})
