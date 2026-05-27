from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from cmcf.config import CompileConfig
from cmcf.core.clang import ClangInterface, ClangError
from cmcf.core.linker import LinkerInterface, LinkerError
from cmcf.core.ir_visitor import IRWalker, WalkReport
from cmcf.mc.handlers import build_router
from cmcf.mc.handlers import memory as _
from cmcf.mc.handlers import arithmetic as _
from cmcf.mc.handlers import comparison as _
from cmcf.mc.handlers import control_flow as _
from cmcf.mc.handlers import call as _
from cmcf.mc.handlers import aggregate as _


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cmcf",
        description="C to Minecraft Function Compiler",
    )
    parser.add_argument(
        "inputs", nargs="+", type=Path,
        help="Input files (.c or .bc)",
    )
    parser.add_argument(
        "-c", action="store_true",
        help="Compile only; produce .bc files, do not generate datapack",
    )
    parser.add_argument(
        "-o", dest="output", type=Path, default=None,
        help="Output path (-c: .bc file, otherwise: datapack directory)",
    )
    parser.add_argument(
        "-O", dest="opt", type=int, choices=[0, 1], default=1,
        help="Optimization level (0 or 1, default: 1)",
    )
    parser.add_argument(
        "-I", "--include", dest="include_paths",
        action="append", default=[], type=Path,
        help="Add include search path (repeatable)",
    )
    parser.add_argument(
        "-D", dest="defines",
        action="append", default=[],
        help="Define preprocessor macro (repeatable)",
    )
    parser.add_argument(
        "--clang", default="clang", help="Path to clang executable",
    )
    parser.add_argument(
        "--llvm-link", default="llvm-link",
        help="Path to llvm-link executable",
    )
    parser.add_argument(
        "--output-ir", dest="output_ir", type=Path, default=None,
        help="Save combined LLVM IR to file for debugging",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Verbose output (IR traversal debug to stderr)",
    )
    args = parser.parse_args()

    _validate_inputs(args.inputs)

    config = CompileConfig(
        sources=tuple(p.resolve() for p in args.inputs),
        output=args.output.resolve() if args.output else None,
        compile_only=args.c,
        clang_path=args.clang,
        llvm_link_path=args.llvm_link,
        opt_level=args.opt,
        include_paths=tuple(p.resolve() for p in args.include_paths),
        defines=tuple(args.defines),
        verbose=args.verbose,
        output_ir=args.output_ir,
    )

    if args.c:
        _do_compile_only(config)
    else:
        _do_build(config)


# ---------------------------------------------------------------------------
# compile-only (-c) path
# ---------------------------------------------------------------------------

def _do_compile_only(config: CompileConfig) -> None:
    if config.output and len(config.sources) > 1:
        print("cmcf: error: cannot specify -o with -c and multiple files",
              file=sys.stderr)
        sys.exit(1)

    clang = ClangInterface(config)
    if not clang.is_available():
        print(f"cmcf: error: clang not found at '{config.clang_path}'",
              file=sys.stderr)
        sys.exit(1)

    has_bc = any(_is_bc(s) for s in config.sources)
    if has_bc:
        print("cmcf: error: .bc inputs not allowed with -c", file=sys.stderr)
        sys.exit(1)

    for source in config.sources:
        if config.output:
            output = config.output
        else:
            output = source.with_suffix(".bc")

        try:
            clang.compile_to_bc(source, output)
            if config.verbose:
                print(f"  -> {output}", file=sys.stderr)
        except ClangError as e:
            print(f"cmcf: error: clang failed for {source.name}",
                  file=sys.stderr)
            if e.stderr:
                print(e.stderr, file=sys.stderr)
            sys.exit(1)


# ---------------------------------------------------------------------------
# build (datapack) path
# ---------------------------------------------------------------------------

def _do_build(config: CompileConfig) -> None:
    clang = ClangInterface(config)
    linker = LinkerInterface(config)

    if not clang.is_available():
        print(f"cmcf: error: clang not found at '{config.clang_path}'",
              file=sys.stderr)
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix="cmcf_") as tmpdir:
        tmp = Path(tmpdir)
        bc_files: list[Path] = []

        for source in config.sources:
            if _is_bc(source):
                bc_files.append(source)
            else:
                out = tmp / source.with_suffix(".bc").name
                try:
                    clang.compile_to_bc(source, out)
                    bc_files.append(out)
                    if config.verbose:
                        print(f"  [cc] {source.name} -> {out.name}", file=sys.stderr)
                except ClangError as e:
                    print(f"cmcf: error: clang failed for {source.name}",
                          file=sys.stderr)
                    if e.stderr:
                        print(e.stderr, file=sys.stderr)
                    sys.exit(1)

        combined = _link_if_needed(config, linker, bc_files, tmp)

        # TODO: extract function annotations from @llvm.global.annotations
        # TODO: DatapackGenerator: mcfunction output + entry tags
        _walk(config, report_source=" ".join(p.name for p in config.sources), bc=combined)


def _link_if_needed(
    config: CompileConfig,
    linker: LinkerInterface,
    bc_files: list[Path],
    tmp: Path,
) -> Path:
    if len(bc_files) == 1:
        return bc_files[0]

    if not linker.is_available():
        print(
            f"cmcf: error: llvm-link not found at '{config.llvm_link_path}'",
            file=sys.stderr,
        )
        sys.exit(1)

    combined = tmp / "combined.bc"
    try:
        linker.link(bc_files, combined)
        if config.verbose:
            print(f"  [ld] {len(bc_files)} files -> combined.bc", file=sys.stderr)
    except LinkerError as e:
        print("cmcf: error: llvm-link failed", file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        sys.exit(1)
    return combined


def _walk(config: CompileConfig, report_source: str | Path, bc: Path) -> None:
    report = WalkReport(source_file=str(report_source))
    router = build_router(report)

    walker = IRWalker(bc, verbose=config.verbose)
    walker.walk(router, report)

    if config.output_ir:
        ir_text = bc.read_bytes()
        try:
            llvm_mod = walker._parse(bc)
            ir_str = str(llvm_mod)
            config.output_ir.write_text(ir_str, encoding="utf-8")
        except Exception:
            config.output_ir.write_bytes(ir_text)

    _print_report(report)

    # TODO: generate mcfunction datapack from report + IRModule
    print("\n[Phase 2] mcfunction datapack generation not yet implemented.",
          file=sys.stderr)

    sys.exit(1 if report.errors else 0)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _validate_inputs(inputs: list[Path]) -> None:
    for path in inputs:
        if not path.exists():
            print(f"cmcf: error: file not found: {path}", file=sys.stderr)
            sys.exit(1)
        suffix = path.suffix.lower()
        if suffix not in (".c", ".bc"):
            print(f"cmcf: warning: unrecognized suffix '{suffix}' for {path}",
                  file=sys.stderr)


def _is_bc(path: Path) -> bool:
    return path.suffix.lower() == ".bc"


def _print_report(report: WalkReport) -> None:
    print("=== Walk Report ===")
    print(f"Source:              {report.source_file}")
    print(f"Functions defined:   {len(report.functions_defined)} "
          f"({', '.join(report.functions_defined) or '(none)'})")
    print(f"Functions declared:  {len(report.functions_declared)} "
          f"({', '.join(report.functions_declared) or '(none)'})")
    print(f"Syscalls detected:   {len(report.syscalls_detected)} "
          f"({', '.join(report.syscalls_detected) or '(none)'})")
    print("Instruction counts:")
    for opcode, count in sorted(report.instruction_counts.items()):
        print(f"  {opcode:<22} {count}")
    if report.errors:
        print(f"Errors:              {len(report.errors)}")
        for err in report.errors:
            print(f"  - {err}")
    else:
        print("Errors:              0")
    print("=== Done ===")


if __name__ == "__main__":
    main()
