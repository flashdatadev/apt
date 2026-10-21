"""Sign repository metadata using only the CI signing subkey, in an isolated keyring."""
import argparse
import datetime as dt
import os
import pathlib
import shutil
import subprocess
import tempfile

from build_packages import ROOT


def gpg_path(path):
    path = pathlib.Path(path).resolve()
    if os.name == "nt":
        return "/" + path.drive[0].lower() + path.as_posix()[2:]
    return str(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=ROOT / "dist")
    parser.add_argument("--gpg", default="gpg")
    args = parser.parse_args()
    secret = os.environ.pop("APT_SIGNING_PRIVATE_KEY")
    password = os.environ.pop("APT_SIGNING_PASSPHRASE")
    fingerprint = (ROOT / "keys/fingerprint.txt").read_text().strip()
    temporary_root = pathlib.Path(tempfile.gettempdir()).resolve()
    home = pathlib.Path(tempfile.mkdtemp(prefix="fd-apt-", dir=temporary_root)).resolve()
    home.chmod(0o700)

    def gpg(*options, data=None):
        result = subprocess.run([args.gpg, "--homedir", gpg_path(home), "--batch", "--yes", *options], input=data, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors="replace"))
        return result.stdout

    try:
        gpg("--import", data=secret.encode())
        listing = gpg("--with-colons", "--list-keys", fingerprint).decode()
        first = next(line for line in listing.splitlines() if line.startswith("fpr:")).split(":")[9]
        if first != fingerprint:
            raise ValueError("Signing key differs from pinned public fingerprint")
        for line in listing.splitlines():
            fields = line.split(":")
            if fields[0] in ("pub", "sub") and fields[6] and int(fields[6]) < dt.datetime.now(dt.timezone.utc).timestamp() + 30 * 86400:
                raise ValueError("Signing key expires within 30 days; rotate before publishing")
        public = gpg("--armor", "--export", fingerprint)
        # Ensure the complete public certificate matches the reviewed, checked-in key.
        if public.replace(b"\r\n", b"\n") != (ROOT / "keys/flashdata.asc").read_bytes().replace(b"\r\n", b"\n"):
            raise ValueError("Public certificate differs from repository key")
        (args.output / "flashdata.gpg").write_bytes(gpg("--export", fingerprint))
        release = args.output / "dists/stable/Release"
        for name, mode in (("InRelease", "--clearsign"), ("Release.gpg", "--detach-sign")):
            gpg("--pinentry-mode", "loopback", "--passphrase-fd", "0", "--local-user", fingerprint,
                "--digest-algo", "SHA256", "--armor", "--output", gpg_path(release.parent / name), mode,
                gpg_path(release), data=(password + "\n").encode())
        gpg("--verify", gpg_path(release.parent / "InRelease"))
        print(f"Signed stable metadata with {fingerprint}; private certification key is not required")
    finally:
        gpgconf = str(pathlib.Path(args.gpg).with_name("gpgconf.exe")) if os.name == "nt" else "gpgconf"
        subprocess.run([gpgconf, "--homedir", gpg_path(home), "--kill", "all"], capture_output=True)
        if home.parent != temporary_root or not home.name.startswith("fd-apt-"):
            raise RuntimeError("Refusing cleanup outside the generated signing directory")
        shutil.rmtree(home)


if __name__ == "__main__":
    main()
