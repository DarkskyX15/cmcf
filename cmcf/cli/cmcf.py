from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from cmcf.core.config import CompileConfig
from cmcf.core.clang import ClangInterface
from cmcf.core.linker import LinkerInterface
from cmcf.core.models import (
    ProjectManifest, ModuleManifest, M3Manifest, M3VersionEntry,
    InstalledManifest, InstalledModuleEntry,
)


def main() -> None:
    parser = argparse.ArgumentParser(prog="cmcf", description="CMCF Project Manager")
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    init_p = sub.add_parser("init", help="Initialize a new CMCF project")
    init_p.add_argument("dir", type=Path, help="Project directory")
    init_p.add_argument("--id", default=None, help="Project id")
    init_p.add_argument("--name", default=None, help="Project display name")

    # repo
    repo_p = sub.add_parser("repo", help="Manage local module repository")
    repo_sub = repo_p.add_subparsers(dest="repo_command", required=True)
    r_install = repo_sub.add_parser("install", help="Install module to site_libs")
    r_install.add_argument("path", type=Path)
    r_remove = repo_sub.add_parser("remove", help="Remove module from site_libs")
    r_remove.add_argument("name")
    repo_sub.add_parser("list", help="List available modules")

    # install
    inst_p = sub.add_parser("install", help="Install module to project")
    inst_p.add_argument("name", help="Module name[@version]")

    # remove
    rem_p = sub.add_parser("remove", help="Remove module from project")
    rem_p.add_argument("name", help="Module name")

    # build
    sub.add_parser("build", help="Build project")

    args = parser.parse_args()

    if args.command == "init":
        _cmd_init(args)
    elif args.command == "repo":
        _cmd_repo(args)
    elif args.command == "install":
        _cmd_install(args)
    elif args.command == "remove":
        _cmd_remove(args)
    elif args.command == "build":
        _cmd_build(args)


# ======================================================================
# init
# ======================================================================

def _cmd_init(args) -> None:
    proj_dir = args.dir.resolve()
    cmcf_dir = proj_dir / ".cmcf"
    proj_id = args.id or proj_dir.name

    manifest: ProjectManifest = {
        "project": {
            "id": proj_id,
            "name": args.name or proj_id,
            "namespace": proj_id,
            "version": "0.1.0",
            "pack_format": {"min": [4, 0], "max": [88, 0]},
            "dist": "./output",
        },
        "compile": {
            "mode": "datapack",
            "opt_level": 1,
            "clang_path": "clang",
            "llvm_link_path": "llvm-link",
        },
    }

    cmcf_dir.mkdir(parents=True, exist_ok=True)
    (cmcf_dir / "cmcf.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (cmcf_dir / "modules.json").write_text("{}\n", encoding="utf-8")
    (cmcf_dir / "handler").mkdir(exist_ok=True)

    src_dir = proj_dir / "src"
    src_dir.mkdir(exist_ok=True)
    main_c = src_dir / "main.c"
    if not main_c.exists():
        main_c.write_text("int main(void) { return 0; }\n", encoding="utf-8")

    print(f"Initialized project: {proj_dir}")


# ======================================================================
# repo
# ======================================================================

def _cmd_repo(args) -> None:
    if args.repo_command == "install":
        _repo_install(args)
    elif args.repo_command == "remove":
        _repo_remove(args)
    elif args.repo_command == "list":
        _repo_list(args)


def _repo_install(args) -> None:
    src = args.path.resolve()
    if not src.is_dir():
        print(f"cmcf: error: not a directory: {src}", file=sys.stderr)
        sys.exit(1)

    mod_json = src / "module.json"
    if not mod_json.exists():
        print(f"cmcf: error: module.json not found in {src}", file=sys.stderr)
        sys.exit(1)

    with open(mod_json, encoding="utf-8") as f:
        manifest: ModuleManifest = json.load(f)

    name = manifest["name"]
    version = manifest["version"]

    # check builtin conflict
    package_dir = Path(__file__).resolve().parent.parent
    libs_m3_path = package_dir / "libs" / "m3.json"
    if libs_m3_path.exists():
        with open(libs_m3_path, encoding="utf-8") as f:
            libs_m3: M3Manifest = json.load(f)
        if name in libs_m3:
            print(f"cmcf: error: builtin module '{name}' cannot be overridden",
                  file=sys.stderr)
            sys.exit(1)

    # copy to site_libs
    site_dir = package_dir / "site_libs"
    site_dir.mkdir(parents=True, exist_ok=True)
    dest = site_dir / f"{name}-{version}"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)

    # update m3.json
    m3_path = site_dir / "m3.json"
    m3: M3Manifest = {}
    if m3_path.exists():
        with open(m3_path, encoding="utf-8") as f:
            m3 = json.load(f)

    deps = manifest.get("dependencies", {})
    entry: M3VersionEntry = {
        "path": dest.name,
        "source": str(src),
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "dependencies": deps,
    }
    m3.setdefault(name, {})[version] = entry

    with open(m3_path, "w", encoding="utf-8") as f:
        json.dump(m3, f, indent=2)
        f.write("\n")

    print(f"Installed: {name}@{version}")


def _repo_remove(args) -> None:
    package_dir = Path(__file__).resolve().parent.parent
    site_dir = package_dir / "site_libs"
    m3_path = site_dir / "m3.json"
    if not m3_path.exists():
        print(f"cmcf: error: no modules installed", file=sys.stderr)
        sys.exit(1)

    with open(m3_path, encoding="utf-8") as f:
        m3: M3Manifest = json.load(f)

    if args.name not in m3:
        print(f"cmcf: error: module '{args.name}' not found", file=sys.stderr)
        sys.exit(1)

    for version, entry in m3[args.name].items():
        p = site_dir / entry["path"]
        if p.exists():
            shutil.rmtree(p)

    del m3[args.name]
    with open(m3_path, "w", encoding="utf-8") as f:
        json.dump(m3, f, indent=2)
        f.write("\n")
    print(f"Removed: {args.name}")


def _repo_list(args) -> None:
    package_dir = Path(__file__).resolve().parent.parent
    for repo, label in [("libs", "builtin"), ("site_libs", "third-party")]:
        m3_path = package_dir / repo / "m3.json"
        if not m3_path.exists():
            continue
        with open(m3_path, encoding="utf-8") as f:
            m3: M3Manifest = json.load(f)
        print(f"\n[{label}]")
        for mod_name, versions in sorted(m3.items()):
            for ver in sorted(versions.keys()):
                deps = ", ".join(f"{k}{v}" for k, v in
                                 versions[ver].get("dependencies", {}).items())
                print(f"  {mod_name}@{ver}" + (f"  (deps: {deps})" if deps else ""))


# ======================================================================
# install (project)
# ======================================================================

def _cmd_install(args) -> None:
    proj_dir = Path.cwd()
    cmcf_dir = proj_dir / ".cmcf"
    if not (cmcf_dir / "cmcf.json").exists():
        print("cmcf: error: not a cmcf project (run 'cmcf init' first)",
              file=sys.stderr)
        sys.exit(1)

    name, _, want_version = args.name.partition("@")
    mod_path = _find_module(name)
    if mod_path is None:
        print(f"cmcf: error: module '{name}' not found", file=sys.stderr)
        sys.exit(1)

    mod_json = mod_path / "module.json"
    with open(mod_json, encoding="utf-8") as f:
        manifest: ModuleManifest = json.load(f)

    version = manifest["version"]
    if want_version and want_version != version:
        print(f"cmcf: error: requested {name}@{want_version}, found {name}@{version}",
              file=sys.stderr)
        sys.exit(1)

    # check pack_format compatibility
    proj_json = cmcf_dir / "cmcf.json"
    with open(proj_json, encoding="utf-8") as f:
        proj_manifest: ProjectManifest = json.load(f)
    proj_pf = proj_manifest["project"]["pack_format"]
    mod_pf = manifest["pack_format"]
    if not _pf_compatible(proj_pf, mod_pf):
        print(f"cmcf: error: pack_format incompatible (project {proj_pf}, "
              f"module {mod_pf})", file=sys.stderr)
        sys.exit(1)

    # syscall conflict check
    new_syscalls: dict[str, str] = manifest.get("syscalls", {})
    modules_path = cmcf_dir / "modules.json"
    if modules_path.exists():
        with open(modules_path, encoding="utf-8") as f:
            installed: InstalledManifest = json.load(f)
        for mod, entry in installed.items():
            existing = entry.get("syscalls", {})
            conflict = set(new_syscalls.keys()) & set(existing.keys())
            if conflict:
                print(f"cmcf: error: syscall conflict with '{mod}': "
                      f"{', '.join(sorted(conflict))}", file=sys.stderr)
                sys.exit(1)
    else:
        installed = {}

    # install_paths
    install_paths: list[str] = []

    # handler
    handler_src = manifest.get("handler")
    if handler_src:
        src_dir = mod_path / handler_src
        dest_dir = cmcf_dir / "handler" / name
        if src_dir.exists():
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(src_dir, dest_dir)
            install_paths.append(str(dest_dir.relative_to(proj_dir)))

    # source
    source_src = manifest.get("source")
    if source_src:
        src_dir = mod_path / source_src
        alias = manifest.get("source_alias", name)
        dest_dir = proj_dir / "include" / alias
        if src_dir.exists():
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(src_dir, dest_dir)
            install_paths.append(str(dest_dir.relative_to(proj_dir)))

    # files
    files = manifest.get("files", {})
    for key, rel_path in files.items():
        src_dir = mod_path / rel_path
        dest_dir = cmcf_dir / key / name
        if src_dir.exists():
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(src_dir, dest_dir)
            install_paths.append(str(dest_dir.relative_to(proj_dir)))

    # update modules.json
    entry: InstalledModuleEntry = {
        "version": version,
        "install_paths": install_paths,
        "syscalls": new_syscalls,
        "dependencies": manifest.get("dependencies", {}),
    }
    installed[name] = entry
    with open(modules_path, "w", encoding="utf-8") as f:
        json.dump(installed, f, indent=2)
        f.write("\n")

    # invalidate pass.json
    pass_path = cmcf_dir / "pass.json"
    if pass_path.exists():
        pass_path.unlink()

    print(f"Installed: {name}@{version}")


# ======================================================================
# remove (project)
# ======================================================================

def _cmd_remove(args) -> None:
    proj_dir = Path.cwd()
    cmcf_dir = proj_dir / ".cmcf"
    modules_path = cmcf_dir / "modules.json"
    if not modules_path.exists():
        print("cmcf: error: no modules installed", file=sys.stderr)
        sys.exit(1)

    with open(modules_path, encoding="utf-8") as f:
        installed: InstalledManifest = json.load(f)

    if args.name not in installed:
        print(f"cmcf: error: module '{args.name}' not installed", file=sys.stderr)
        sys.exit(1)

    entry = installed[args.name]

    # check reverse dependencies
    for mod, e in installed.items():
        if mod != args.name and args.name in e.get("dependencies", {}):
            print(f"cmcf: warning: module '{mod}' depends on '{args.name}'",
                  file=sys.stderr)

    # remove files
    for p in entry.get("install_paths", []):
        full = proj_dir / p
        if full.exists():
            if full.is_dir():
                shutil.rmtree(full)
            else:
                full.unlink()

    del installed[args.name]
    with open(modules_path, "w", encoding="utf-8") as f:
        json.dump(installed, f, indent=2)
        f.write("\n")

    pass_path = cmcf_dir / "pass.json"
    if pass_path.exists():
        pass_path.unlink()

    print(f"Removed: {args.name}")


# ======================================================================
# build
# ======================================================================

def _cmd_build(args) -> None:
    proj_dir = Path.cwd()
    cmcf_dir = proj_dir / ".cmcf"
    if not (cmcf_dir / "cmcf.json").exists():
        print("cmcf: error: not a cmcf project", file=sys.stderr)
        sys.exit(1)

    with open(cmcf_dir / "cmcf.json", encoding="utf-8") as f:
        proj_manifest: ProjectManifest = json.load(f)

    config = CompileConfig.from_manifest(proj_manifest)
    clang = ClangInterface.from_config(config)
    linker = LinkerInterface(llvm_link_path=config.llvm_link_path)

    with tempfile.TemporaryDirectory(prefix="cmcf_build_") as tmpdir:
        tmp = Path(tmpdir)
        bc_files: list[Path] = []

        # compile src/
        src_dir = proj_dir / "src"
        for c_file in sorted(src_dir.glob("*.c")):
            out = tmp / c_file.with_suffix(".bc").name
            clang.compile_to_bc(c_file, out)
            bc_files.append(out)

        # compile include/**/*.c
        include_dir = proj_dir / "include"
        for c_file in sorted(include_dir.rglob("*.c")) if include_dir.exists() else []:
            out = tmp / f"{c_file.parent.name}_{c_file.with_suffix('.bc').name}"
            clang.compile_to_bc(c_file, out)
            bc_files.append(out)

        # link
        if len(bc_files) == 1:
            combined = bc_files[0]
        else:
            combined = tmp / "combined.bc"
            linker.link(bc_files, combined)

        # call mcc build
        import subprocess as sp
        import os
        mcc_cmd = [sys.executable, "-m", "cmcf.cli.mcc", "build", str(combined),
                   "--project", str(proj_dir)]
        env = {**os.environ}
        pkg_root = str(Path(__file__).resolve().parent.parent.parent)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{pkg_root}{os.pathsep}{existing}" if existing else pkg_root
        if config.verbose:
            mcc_cmd.append("--verbose")
        sp.run(mcc_cmd, check=True, env=env)


# ======================================================================
# helpers
# ======================================================================

def _find_module(name: str) -> Path | None:
    package_dir = Path(__file__).resolve().parent.parent
    for repo in ("site_libs", "libs"):
        m3_path = package_dir / repo / "m3.json"
        if not m3_path.exists():
            continue
        with open(m3_path, encoding="utf-8") as f:
            m3: M3Manifest = json.load(f)
        if name in m3:
            versions = m3[name]
            latest = sorted(versions.keys())[-1]
            return package_dir / repo / versions[latest]["path"]
    return None


def _pf_compatible(proj_pf: dict[str, list[int]],
                   mod_pf: dict[str, list[int]]) -> bool:
    pmin, pmax = proj_pf.get("min", [4, 0]), proj_pf.get("max", [88, 0])
    mmin, mmax = mod_pf.get("min", [4, 0]), mod_pf.get("max", [88, 0])
    return (pmax[0] >= mmin[0] and pmin[0] <= mmax[0])


if __name__ == "__main__":
    main()
