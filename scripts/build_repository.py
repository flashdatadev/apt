"""Generate the APT tree, retaining immutable packages and historical by-hash indexes."""
import argparse
import datetime as dt
import email.utils
import hashlib
import io
import json
import lzma
import pathlib
import shutil
import tarfile

from build_packages import ROOT, gz, manifest, sha


def read_ar(data):
    if data[:8] != b"!<arch>\n":
        raise ValueError("Invalid Debian package")
    members, offset = {}, 8
    while offset < len(data):
        header = data[offset:offset + 60]
        size = int(header[48:58])
        name = header[:16].decode().strip().rstrip("/")
        members[name] = data[offset + 60:offset + 60 + size]
        offset += 60 + size + size % 2
    return members


def package_record(release, arch, output):
    name = f"flashdata_{release['debian_version']}_{arch}.deb"
    package = (ROOT / "packages" / name).read_bytes()
    if sha(package) != release["packages"][arch]:
        raise ValueError(f"Package checksum mismatch: {name}")
    with tarfile.open(fileobj=io.BytesIO(read_ar(package)["control.tar.xz"]), mode="r:xz") as archive:
        control = archive.extractfile("control").read().decode()
    if f"Version: {release['debian_version']}\n" not in control or f"Architecture: {arch}\n" not in control:
        raise ValueError("Debian control metadata differs from manifest")
    path = f"pool/main/f/flashdata/{name}"
    dest = output / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(package)
    return control + f"Filename: {path}\nSize: {len(package)}\nSHA256: {sha(package)}\nSHA512: {hashlib.sha512(package).hexdigest()}\n\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=ROOT / "dist")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use an empty output directory; never overwrite a live repository in place")
    output.mkdir(parents=True, exist_ok=True)
    releases = manifest()["releases"]
    indexes = []
    for arch in ("amd64", "arm64"):
        folder = output / "dists/stable/main" / f"binary-{arch}"
        folder.mkdir(parents=True)
        text = ""
        for release in releases:
            text += package_record(release, arch, output)
            raw = text.encode()
            for name, payload in [("Packages", raw), ("Packages.gz", gz(raw)), ("Packages.xz", lzma.compress(raw, preset=6))]:
                # Retain all historical index hashes for clients holding an older signed Release.
                by_hash = folder / "by-hash/SHA256" / sha(payload)
                by_hash.parent.mkdir(parents=True, exist_ok=True)
                by_hash.write_bytes(payload)
                (folder / name).write_bytes(payload)
        indexes.extend(folder / name for name in ("Packages", "Packages.gz", "Packages.xz"))
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    release_text = (
        "Origin: FlashData\nLabel: FlashData\nSuite: stable\nCodename: stable\n"
        f"Date: {email.utils.format_datetime(now, usegmt=True)}\n"
        f"Valid-Until: {email.utils.format_datetime(now + dt.timedelta(days=30), usegmt=True)}\n"
        "Architectures: amd64 arm64\nComponents: main\nAcquire-By-Hash: yes\n"
        "Description: Official FlashData CLI packages\n"
    )
    for algorithm in ("sha256", "sha512"):
        release_text += algorithm.upper() + ":\n"
        for path in sorted(indexes):
            payload = path.read_bytes()
            relative = path.relative_to(output / "dists/stable").as_posix()
            release_text += f" {hashlib.new(algorithm, payload).hexdigest()} {len(payload):16d} {relative}\n"
    (output / "dists/stable/Release").write_text(release_text, encoding="utf-8", newline="\n")
    shutil.copyfile(ROOT / "keys/flashdata.asc", output / "flashdata.asc")
    shutil.copyfile(ROOT / "keys/fingerprint.txt", output / "fingerprint.txt")
    for name in ("index.html", ".nojekyll"):
        shutil.copyfile(ROOT / "web" / name, output / name)
    print(json.dumps({"output": str(output), "suite": "stable", "versions": [r["debian_version"] for r in releases], "validUntil": (now + dt.timedelta(days=30)).isoformat()}))


if __name__ == "__main__":
    main()
