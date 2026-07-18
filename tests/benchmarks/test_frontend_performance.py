import pytest
import os
import json
import glob
from tests.benchmarks.benchmark_utils import BenchmarkRunner


FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
BUILD_DIR = os.path.join(FRONTEND_DIR, ".next")


@pytest.fixture
def bench():
    return BenchmarkRunner(iterations=10, warmup=2)


def get_file_size(path):
    return os.path.getsize(path)


def count_lines(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return sum(1 for _ in f)


def test_frontend_bundle_analysis():
    """Analyze frontend bundle sizes (requires production build)."""
    if not os.path.isdir(BUILD_DIR):
        pytest.skip("No .next build directory found. Run 'npm run build' first.")

    report_lines = []
    report_lines.append("\n--- Frontend Bundle Size Analysis ---\n")

    js_files = glob.glob(os.path.join(BUILD_DIR, "static", "chunks", "*.js"), recursive=True)
    if not js_files:
        js_files = glob.glob(os.path.join(BUILD_DIR, "**", "*.js"), recursive=True)

    total_size = 0
    file_sizes = []
    for fpath in js_files:
        size = get_file_size(fpath)
        total_size += size
        rel_path = os.path.relpath(fpath, FRONTEND_DIR)
        file_sizes.append((rel_path, size))

    file_sizes.sort(key=lambda x: x[1], reverse=True)

    report_lines.append(f"Total JS bundle size: {total_size / 1024:.1f} KB ({total_size:,} bytes)")
    report_lines.append(f"Total JS files: {len(file_sizes)}")
    report_lines.append("")

    report_lines.append(f"{'File':<80} {'Size (KB)':<12}")
    report_lines.append("-" * 92)
    for rel_path, size in file_sizes[:20]:
        report_lines.append(f"{rel_path:<80} {size / 1024:<12.1f}")

    if len(file_sizes) > 20:
        report_lines.append(f"... and {len(file_sizes) - 20} more files")

    build_id_path = os.path.join(BUILD_DIR, "BUILD_ID")
    if os.path.isfile(build_id_path):
        with open(build_id_path, "r") as f:
            report_lines.append(f"\nBuild ID: {f.read().strip()}")

    print("\n".join(report_lines))


def test_frontend_source_analysis():
    """Analyze frontend source code for component count and import patterns."""
    if not os.path.isdir(FRONTEND_DIR):
        pytest.skip("No frontend directory found")

    report_lines = []
    report_lines.append("\n--- Frontend Source Analysis ---\n")

    tsx_files = glob.glob(os.path.join(FRONTEND_DIR, "**", "*.tsx"), recursive=True)
    ts_files = glob.glob(os.path.join(FRONTEND_DIR, "**", "*.ts"), recursive=True)
    page_files = glob.glob(os.path.join(FRONTEND_DIR, "app", "**", "page.tsx"), recursive=True)
    component_files = glob.glob(os.path.join(FRONTEND_DIR, "components", "**", "*.tsx"), recursive=True)
    hook_files = glob.glob(os.path.join(FRONTEND_DIR, "hooks", "**", "*.ts"), recursive=True)

    report_lines.append(f"Total TSX files: {len(tsx_files)}")
    report_lines.append(f"Total TS files: {len(ts_files)}")
    report_lines.append(f"Page files: {len(page_files)}")
    report_lines.append(f"Component files: {len(component_files)}")
    report_lines.append(f"Hook files: {len(hook_files)}")

    total_lines = 0
    for fpath in tsx_files + ts_files:
        try:
            total_lines += count_lines(fpath)
        except Exception:
            pass
    report_lines.append(f"Total source lines: {total_lines:,}")

    report_lines.append("\n--- Largest Source Files ---\n")
    file_lines = []
    for fpath in tsx_files + ts_files:
        try:
            lines = count_lines(fpath)
            rel_path = os.path.relpath(fpath, FRONTEND_DIR)
            file_lines.append((rel_path, lines))
        except Exception:
            pass
    file_lines.sort(key=lambda x: x[1], reverse=True)

    report_lines.append(f"{'File':<80} {'Lines':<10}")
    report_lines.append("-" * 90)
    for rel_path, lines in file_lines[:15]:
        report_lines.append(f"{rel_path:<80} {lines:<10}")

    report_lines.append("\n--- Import Analysis: Key Libraries ---\n")
    key_libs = ["react", "next", "axios", "socket.io", "recharts", "d3", "lodash", "zustand", "redux", "tailwind"]
    lib_usage = {}
    for fpath in tsx_files + ts_files:
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                for lib in key_libs:
                    if lib in content:
                        lib_usage[lib] = lib_usage.get(lib, 0) + 1
        except Exception:
            pass

    for lib in sorted(lib_usage.keys()):
        report_lines.append(f"  {lib:<30} {lib_usage[lib]:>4} files")

    print("\n".join(report_lines))


def test_frontend_unused_assets():
    """Check for potentially unused assets in the public directory."""
    public_dir = os.path.join(FRONTEND_DIR, "public")
    if not os.path.isdir(public_dir):
        pytest.skip("No public directory found")

    report_lines = []
    report_lines.append("\n--- Frontend Asset Analysis ---\n")

    asset_extensions = ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.svg", "*.ico", "*.webp", "*.woff", "*.woff2"]
    assets = []
    for ext in asset_extensions:
        assets.extend(glob.glob(os.path.join(public_dir, "**", ext), recursive=True))

    report_lines.append(f"Total public assets: {len(assets)}")

    total_asset_size = 0
    asset_details = []
    for asset in assets:
        size = get_file_size(asset)
        total_asset_size += size
        rel_path = os.path.relpath(asset, FRONTEND_DIR)
        asset_details.append((rel_path, size))

    report_lines.append(f"Total asset size: {total_asset_size / 1024:.1f} KB ({total_asset_size:,} bytes)")
    report_lines.append("")

    asset_details.sort(key=lambda x: x[1], reverse=True)

    report_lines.append(f"{'Asset':<80} {'Size (KB)':<12}")
    report_lines.append("-" * 92)
    for rel_path, size in asset_details[:15]:
        report_lines.append(f"{rel_path:<80} {size / 1024:<12.1f}")

    if len(asset_details) > 15:
        report_lines.append(f"... and {len(asset_details) - 15} more assets")

    package_json_path = os.path.join(FRONTEND_DIR, "package.json")
    if os.path.isfile(package_json_path):
        with open(package_json_path, "r") as f:
            pkg = json.load(f)
        deps = pkg.get("dependencies", {})
        dev_deps = pkg.get("devDependencies", {})
        report_lines.append(f"\nDependencies: {len(deps)} production, {len(dev_deps)} dev")
        total_dep_size = len(deps) + len(dev_deps)
        report_lines.append(f"Total dependencies: {total_dep_size}")

    print("\n".join(report_lines))


def test_react_component_patterns():
    """Analyze React component patterns for performance anti-patterns."""
    if not os.path.isdir(FRONTEND_DIR):
        pytest.skip("No frontend directory found")

    component_files = glob.glob(os.path.join(FRONTEND_DIR, "components", "**", "*.tsx"), recursive=True)
    app_files = glob.glob(os.path.join(FRONTEND_DIR, "app", "**", "*.tsx"), recursive=True)
    all_comp_files = component_files + app_files

    report_lines = []
    report_lines.append("\n--- React Component Performance Pattern Analysis ---\n")

    patterns = {
        "'use client'": "Client component",
        "useEffect": "useEffect usage",
        "useState": "useState usage",
        "useMemo": "useMemo usage",
        "useCallback": "useCallback usage",
        "useRef": "useRef usage",
        "memo(": "React.memo usage",
        "React.lazy": "Lazy loading",
        "Suspense": "Suspense usage",
        "React.memo": "React.memo (explicit)",
        "useContext": "Context usage",
        "useReducer": "useReducer usage",
        "async function": "Async function",
        ".map(": "Array.map (potential re-render)",
        "useTransition": "useTransition usage",
        "useDeferredValue": "useDeferredValue usage",
    }

    pattern_counts = {k: 0 for k in patterns}
    pattern_files = {k: set() for k in patterns}

    for fpath in all_comp_files:
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                for pattern in patterns:
                    if pattern in content:
                        pattern_counts[pattern] += content.count(pattern)
                        pattern_files[pattern].add(fpath)
        except Exception:
            pass

    report_lines.append(f"{'Pattern':<35} {'Occurrences':<14} {'Files':<8}" )
    report_lines.append("-" * 57)
    for pattern, label in patterns.items():
        if pattern_counts[pattern] > 0:
            report_lines.append(
                f"{label:<35} {pattern_counts[pattern]:<14} {len(pattern_files[pattern]):<8}"
            )

    report_lines.append("\n'use client' files:")
    client_files = pattern_files.get("'use client'", set())
    for f in sorted(client_files)[:10]:
        report_lines.append(f"  {os.path.relpath(f, FRONTEND_DIR)}")

    if len(client_files) > 10:
        report_lines.append(f"  ... and {len(client_files) - 10} more")

    print("\n".join(report_lines))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--capture=no"])
