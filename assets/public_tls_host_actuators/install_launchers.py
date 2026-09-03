from __future__ import annotations

"""Install executable launchers for the Python host actuator modules.

GitHub/Certbot interfaces expect executable file paths. The canonical logic remains in
Python modules; these wrappers only provide stable executable entrypoints on the
resident host and can be regenerated safely on every deployment.
"""

from pathlib import Path
import json
import os
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BIN = Path(
    os.environ.get(
        "KEDDEH_HOST_ACTUATOR_BIN",
        "/mnt/data/keddeh_deploy/resident_v5/KEDDEH_REGISTRAR_V5_EVIDENCE/HOST_ACTUATORS/bin",
    )
)

LAUNCHERS = {
    "dns01-auth": "assets.public_tls_host_actuators.dns01_resident_actuator auth",
    "dns01-cleanup": "assets.public_tls_host_actuators.dns01_resident_actuator cleanup",
    "server-tls-install": "assets.public_tls_host_actuators.server_tls_actuator install",
    "server-tls-rollback": "assets.public_tls_host_actuators.rollback_server_tls",
}


def install(bin_root: Path = DEFAULT_BIN) -> dict:
    bin_root.mkdir(parents=True, exist_ok=True)
    python = Path(sys.executable).resolve()
    paths: dict[str, str] = {}
    for name, module_and_args in LAUNCHERS.items():
        module, *args = module_and_args.split()
        target = bin_root / name
        argv = " ".join(args)
        script = (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            f"cd {json.dumps(str(ROOT))}\n"
            f"exec {json.dumps(str(python))} -m {module} {argv} \"$@\"\n"
        )
        target.write_text(script, encoding="utf-8")
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        if not os.access(target, os.X_OK):
            raise RuntimeError(f"HOST_ACTUATOR_LAUNCHER_NOT_EXECUTABLE:{target}")
        paths[name] = str(target)
    return {
        "schema": "kex.braink.host-actuator-launchers.v1",
        "repository_root": str(ROOT),
        "python": str(python),
        "launchers": paths,
    }


def main() -> int:
    result = install()
    print(json.dumps(result, indent=2, sort_keys=True))
    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        mapping = {
            "KEDDEH_PUBLIC_CA_AUTH_HOOK": result["launchers"]["dns01-auth"],
            "KEDDEH_PUBLIC_CA_CLEANUP_HOOK": result["launchers"]["dns01-cleanup"],
            "KEDDEH_SERVER_TLS_INSTALL_HOOK": result["launchers"]["server-tls-install"],
            "KEDDEH_SERVER_TLS_ROLLBACK_HOOK": result["launchers"]["server-tls-rollback"],
        }
        with open(github_env, "a", encoding="utf-8") as fh:
            for key, value in mapping.items():
                fh.write(f"{key}={value}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
