from __future__ import annotations

import argparse
import importlib
import json
import sys
import tempfile
from pathlib import Path

from cmcf.core.config import CompileConfig
from cmcf.core.clang import ClangInterface, ClangError
from cmcf.core.linker import LinkerInterface, LinkerError
from cmcf.core.handler import get_registry, compute_fingerprint
from cmcf.core.context import WalkContext
from cmcf.core.ir_walker import TreeWalker
from cmcf.core.models import InstalledManifest, ProjectManifest


def main() -> None:
    parser = argparse.ArgumentParser(prog="mcc", description="Minecraft C Compiler")
    sub = parser.add_subparsers(dest="command", required=True)

    cc = sub.add_parser("compile", help="Compile C source to LLVM bitcode")
    cc.add_argument("source", type=Path, help="C source file")
    cc.add_argument("-o", dest="output", type=Path, required=True, help="Output .bc file")
    cc.add_argument("-O", dest="opt", type=int, choices=[0, 1], default=1)
    cc.add_argument("-I", dest="includes", action="append", default=[], type=Path)
    cc.add_argument("-D", dest="defines", action="append", default=[])
    cc.add_argument("--clang", default="clang")

    lk = sub.add_parser("link", help="Link multiple .bc files")
    lk.add_argument("inputs", nargs="+", type=Path, help="Input .bc files")
    lk.add_argument("-o", dest="output", type=Path, required=True, help="Output .bc file")
    lk.add_argument("--llvm-link", default="llvm-link")

    bd = sub.add_parser("build", help="Generate datapack from bitcode")
    bd.add_argument("input", type=Path, help="Combined .bc file")
    bd.add_argument("--project", dest="project_dir", type=Path, default=None,
                    help="Project directory (reads .cmcf/)")
    bd.add_argument("-o", dest="output", type=Path, default=None,
                    help="Output directory override")
    bd.add_argument("--export-header", action="store_true")

    args = parser.parse_args()

    if args.command == "compile":
        _cmd_compile(args)
    elif args.command == "link":
        _cmd_link(args)
    elif args.command == "build":
        _cmd_build(args)


def _cmd_compile(args) -> None:
    clang = ClangInterface(
        clang_path=args.clang, opt_level=args.opt,
        include_paths=tuple(p.resolve() for p in args.includes),
        defines=tuple(args.defines),
    )
    source = args.source.resolve()
    output = args.output.resolve()
    if not source.exists():
        print(f"mcc: error: file not found: {source}", file=sys.stderr)
        sys.exit(1)
    try:
        clang.compile_to_bc(source, output)
    except ClangError as e:
        print(f"mcc: error: {e}", file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        sys.exit(1)


def _cmd_link(args) -> None:
    linker = LinkerInterface(llvm_link_path=args.llvm_link)
    inputs = [p.resolve() for p in args.inputs]
    output = args.output.resolve()
    try:
        linker.link(inputs, output)
    except LinkerError as e:
        print(f"mcc: error: {e}", file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        sys.exit(1)


def _cmd_build(args) -> None:
    bc = args.input.resolve()
    if not bc.exists():
        print(f"mcc: error: file not found: {bc}", file=sys.stderr)
        sys.exit(1)

    config = _load_project_config(args)

    proj_dir = args.project_dir.resolve() if args.project_dir else bc.parent.parent
    _load_handlers(proj_dir, config)

    reg = get_registry()
    pass_path = proj_dir / ".cmcf" / "pass.json"
    modules_path = proj_dir / ".cmcf" / "modules.json"
    fingerprint = compute_fingerprint(modules_path)
    for key, col in reg.items():
        col._ensure_key(key)
        col.sort(fingerprint, pass_path)

    output_dir = args.output.resolve() if args.output else proj_dir / config.output
    ctx = WalkContext.from_config(config, output_dir)

    # load syscall registry from installed modules
    if modules_path.exists():
        with open(modules_path, encoding="utf-8") as f:
            installed: InstalledManifest = json.load(f)
        ctx.registries.syscall = type(ctx.registries.syscall).from_installed_manifest(
            installed
        )

    # preflight
    for col in reg.values():
        col.preflight(ctx)

    # walk
    walker = TreeWalker()
    walker.walk(bc, ctx)
    print(f"output: {output_dir}")


def _load_project_config(args) -> CompileConfig:
    proj_dir = args.project_dir.resolve() if args.project_dir else Path.cwd()
    cmcf_json = proj_dir / ".cmcf" / "cmcf.json"
    if cmcf_json.exists():
        with open(cmcf_json, encoding="utf-8") as f:
            manifest: ProjectManifest = json.load(f)
        config = CompileConfig.from_manifest(manifest)
    else:
        config = CompileConfig(sources=())

    if args.output:
        config.output = args.output
    if args.export_header:
        config.export_header = True
    return config


def _load_handlers(proj_dir: Path, config: CompileConfig) -> None:
    handler_dir = proj_dir / ".cmcf" / "handler"
    if not handler_dir.is_dir():
        return

    sys.path.insert(0, str(handler_dir))

    for module_dir in sorted(handler_dir.iterdir()):
        if not module_dir.is_dir():
            continue
        name = module_dir.name
        try:
            importlib.import_module(name)
        except Exception as e:
            print(f"mcc: warning: failed to load handler {name}: {e}",
                  file=sys.stderr)


if __name__ == "__main__":
    main()
