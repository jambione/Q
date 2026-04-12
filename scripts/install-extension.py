"""
install-extension.py — Install Q as a permanent VS Code extension via directory junction.

No admin rights required on Windows (uses mklink /J junction, not a symlink).
Run once. After that Q loads automatically every time VS Code starts.

Usage:
  python scripts/install-extension.py           Install (or reinstall)
  python scripts/install-extension.py --remove  Remove the extension
  python scripts/install-extension.py --status  Check current install status
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


EXTENSION_NAME = "q-conscience-0.1.0"


def find_repo_root() -> Path:
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "q-config.json").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent.parent


def find_vscode_extensions_dir() -> Path | None:
    """Find the VS Code extensions directory for the current user."""
    candidates = [
        Path.home() / ".vscode" / "extensions",
        Path.home() / ".vscode-insiders" / "extensions",
        # VS Code installed via scoop on Windows
        Path.home() / "scoop" / "apps" / "vscode" / "current" / "data" / "extensions",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    # Try creating the default path if VS Code is installed but extensions dir doesn't exist yet
    default = Path.home() / ".vscode" / "extensions"
    try:
        default.mkdir(parents=True, exist_ok=True)
        return default
    except Exception:
        return None


def create_junction_windows(link: Path, target: Path) -> bool:
    """Create a directory junction on Windows using mklink /J (no admin required)."""
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def remove_junction_windows(link: Path) -> bool:
    """Remove a directory junction on Windows."""
    result = subprocess.run(
        ["cmd", "/c", "rmdir", str(link)],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def install(repo_root: Path, extensions_dir: Path) -> None:
    extension_src = repo_root / "vscode-extension"
    extension_link = extensions_dir / EXTENSION_NAME

    if not extension_src.exists():
        print(f"ERROR: vscode-extension/ folder not found at {extension_src}")
        sys.exit(1)

    if not (extension_src / "package.json").exists():
        print(f"ERROR: vscode-extension/package.json not found. Extension folder is incomplete.")
        sys.exit(1)

    # Remove existing link/folder if present
    if extension_link.exists() or extension_link.is_symlink():
        print(f"Removing existing install at {extension_link} ...")
        if sys.platform == "win32":
            remove_junction_windows(extension_link)
        else:
            if extension_link.is_symlink():
                extension_link.unlink()
            else:
                shutil.rmtree(extension_link)

    print(f"Installing Q extension ...")
    print(f"  Source : {extension_src}")
    print(f"  Link   : {extension_link}")

    if sys.platform == "win32":
        success = create_junction_windows(extension_link, extension_src)
    else:
        try:
            extension_link.symlink_to(extension_src)
            success = True
        except Exception as e:
            print(f"ERROR: Could not create symlink: {e}")
            success = False

    if success:
        print()
        print("✓ Q extension installed successfully.")
        print()
        print("Next steps:")
        print("  1. Restart VS Code (or press Ctrl+Shift+P → 'Developer: Reload Window')")
        print("  2. Open any project that has a q-config.json in its root")
        print("  3. Q: ◦ will appear in the status bar (bottom right)")
        print("  4. Save any watched file — Q will check it automatically")
        print()
        print("  To review the current file manually: Ctrl+Shift+P → 'Q: Review Current File'")
        print("  To see learned exceptions: Ctrl+Shift+P → 'Q: Open Learned Exceptions'")
        print()
        print("  Q uses your GitHub Copilot subscription — no Anthropic API key needed.")
    else:
        print()
        print("ERROR: Installation failed.")
        if sys.platform == "win32":
            print("Try running this script from a terminal (not a restricted shell).")
        sys.exit(1)


def remove(extensions_dir: Path) -> None:
    extension_link = extensions_dir / EXTENSION_NAME

    if not extension_link.exists() and not extension_link.is_symlink():
        print(f"Q extension is not installed at {extension_link}")
        return

    print(f"Removing Q extension from {extension_link} ...")
    if sys.platform == "win32":
        success = remove_junction_windows(extension_link)
    else:
        try:
            if extension_link.is_symlink():
                extension_link.unlink()
            else:
                shutil.rmtree(extension_link)
            success = True
        except Exception as e:
            print(f"ERROR: {e}")
            success = False

    if success:
        print("✓ Q extension removed.")
        print("  Restart VS Code to complete the uninstall.")
    else:
        print("ERROR: Removal failed.")
        sys.exit(1)


def status(repo_root: Path, extensions_dir: Path) -> None:
    extension_src = repo_root / "vscode-extension"
    extension_link = extensions_dir / EXTENSION_NAME

    print(f"Q Extension Status")
    print(f"──────────────────────────────────────")
    print(f"  Source folder : {extension_src}")
    print(f"  Source exists : {'✓' if extension_src.exists() else '✗ MISSING'}")
    print()
    print(f"  Extensions dir: {extensions_dir}")
    print(f"  Installed link: {extension_link}")

    if extension_link.exists():
        if extension_link.is_symlink():
            print(f"  Install status: ✓ installed (symlink)")
            print(f"  Points to     : {extension_link.resolve()}")
        else:
            # On Windows, junctions appear as directories, not symlinks
            print(f"  Install status: ✓ installed (junction)")
    else:
        print(f"  Install status: ✗ not installed")
        print()
        print("  Run: python scripts/install-extension.py")


def main():
    parser = argparse.ArgumentParser(description="Install Q as a VS Code extension")
    parser.add_argument("--remove", action="store_true", help="Remove the Q extension")
    parser.add_argument("--status", action="store_true", help="Check install status")
    args = parser.parse_args()

    repo_root = find_repo_root()
    extensions_dir = find_vscode_extensions_dir()

    if not extensions_dir:
        print("ERROR: Could not find VS Code extensions directory.")
        print("Is VS Code installed? Looked for: ~/.vscode/extensions/")
        sys.exit(1)

    if args.status:
        status(repo_root, extensions_dir)
    elif args.remove:
        remove(extensions_dir)
    else:
        install(repo_root, extensions_dir)


if __name__ == "__main__":
    main()
