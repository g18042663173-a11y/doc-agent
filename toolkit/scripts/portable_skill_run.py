"""Skill-relative portable entry point, copied unchanged into each release."""
from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import sys


def main() -> None:
    root = Path(__file__).resolve().parent
    config = json.loads((root / "portable.json").read_text(encoding="utf-8"))
    sys.dont_write_bytecode = True
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    if config.get("graphviz"):
        os.environ["PATH"] = str(root / "runtime/graphviz/bin") + os.pathsep + os.environ.get("PATH", "")
    if os.environ.get("SKILL_NETWORK_DISABLED") == "1":
        def deny_network(event: str, arguments: tuple) -> None:
            if event in {"socket.connect", "socket.connect_ex", "socket.getaddrinfo", "socket.bind"}:
                raise PermissionError("Network disabled for portable acceptance")
        sys.addaudithook(deny_network)
    if sys.argv[1:] == ["--verify-runtime"]:
        import importlib.metadata
        import shutil
        import socket
        blocked = False
        if os.environ.get("SKILL_NETWORK_DISABLED") == "1":
            try:
                socket.getaddrinfo("portable-acceptance.invalid", 443)
            except PermissionError:
                blocked = True
            if not blocked:
                raise RuntimeError("Offline acceptance network guard did not activate")
        python_root = (root / "runtime/python").resolve()
        for path in sys.path:
            Path(path).resolve().relative_to(python_root)
        dot = shutil.which("dot") if config.get("graphviz") else None
        if config.get("graphviz") and (not dot or Path(dot).resolve() != (root / "runtime/graphviz/bin/dot.exe").resolve()):
            raise RuntimeError("The generation skill did not resolve its bundled Graphviz")
        print(json.dumps({"pass": True, "skill": config["skill_name"], "python": sys.executable,
              "version": sys.version.split()[0], "network_blocked": blocked, "sys_path": sys.path,
              "graphviz_executable": dot,
              "packages": sorted({d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}.items())},
              ensure_ascii=False))
        return
    entry = root / config["entry"]
    sys.argv = [str(entry), *sys.argv[1:]]
    runpy.run_path(str(entry), run_name="__main__")


if __name__ == "__main__":
    main()
