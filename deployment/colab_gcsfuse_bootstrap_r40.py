from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


def run(*args: str, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), check=check, text=True, capture_output=True, input=input_text)


def in_colab() -> bool:
    try:
        import google.colab  # type: ignore
        return True
    except Exception:
        return False


def authenticate_colab() -> None:
    if not in_colab():
        return
    from google.colab import auth  # type: ignore
    auth.authenticate_user()


def ensure_gcsfuse(*, install: bool) -> None:
    if shutil.which("gcsfuse"):
        return
    if not install:
        raise RuntimeError("BLOCKED:GCSFUSE_NOT_INSTALLED")
    run("sudo", "apt-get", "update")
    run("sudo", "apt-get", "install", "-y", "curl", "lsb-release")
    codename = run("lsb_release", "-c", "-s").stdout.strip()
    if not codename:
        raise RuntimeError("FAILED:DISTRO_CODENAME_UNAVAILABLE")
    keyring = "/usr/share/keyrings/cloud.google.asc"
    key = run("curl", "-fsSL", "https://packages.cloud.google.com/apt/doc/apt-key.gpg").stdout
    run("sudo", "tee", keyring, input_text=key)
    repo = f"deb [signed-by={keyring}] https://packages.cloud.google.com/apt gcsfuse-{codename} main\n"
    run("sudo", "tee", "/etc/apt/sources.list.d/gcsfuse.list", input_text=repo)
    run("sudo", "apt-get", "update")
    run("sudo", "apt-get", "install", "-y", "gcsfuse")


def main() -> int:
    parser = argparse.ArgumentParser(description="Mount a GCS bucket for BRAINK R40 replica/failover storage.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--mount-point", default="/content/0SxDNA_SUBSTRATE")
    parser.add_argument("--install-gcsfuse", action="store_true")
    parser.add_argument("--verify-write", action="store_true")
    args = parser.parse_args()

    authenticate_colab()
    if not shutil.which("gcloud"):
        raise RuntimeError("BLOCKED:GCLOUD_NOT_INSTALLED")

    os.environ["GOOGLE_CLOUD_PROJECT"] = args.project
    run("gcloud", "config", "set", "project", args.project)
    run("gcloud", "storage", "buckets", "describe", f"gs://{args.bucket}")

    ensure_gcsfuse(install=args.install_gcsfuse)
    mount = Path(args.mount_point)
    mount.mkdir(parents=True, exist_ok=True)

    if not os.path.ismount(mount):
        run("gcsfuse", "--implicit-dirs", args.bucket, str(mount))

    probe = {
        "project": args.project,
        "bucket": args.bucket,
        "mount_point": str(mount),
        "mounted": os.path.ismount(mount),
        "capacity_model": "CLOUD_OBJECT_STORAGE_NO_FIXED_100TB_VOLUME_CLAIM",
        "role": "BRAINK_REPLICA_FAILOVER_TARGET",
    }

    if args.verify_write:
        test_path = mount / ".braink-r40-write-probe"
        test_path.write_text("braink-r40\n", encoding="utf-8")
        if test_path.read_text(encoding="utf-8") != "braink-r40\n":
            raise RuntimeError("FAILED:GCSFUSE_WRITE_READBACK")
        test_path.unlink()

    print(json.dumps(probe, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
