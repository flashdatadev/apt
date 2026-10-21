"""Build reproducible .deb packages from pinned, unmodified upstream executables."""
import argparse
import datetime as dt
import email.utils
import gzip
import hashlib
import io
import json
import lzma
import pathlib
import struct
import tarfile
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]


def manifest():
    return json.loads((ROOT / "releases.json").read_text())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def gz(data):
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as stream:
        stream.write(data)
    return output.getvalue()


def tar_xz(files, epoch):
    output = io.BytesIO()
    directories = {str(p) for name in files for p in pathlib.PurePosixPath(name).parents if str(p) != "."}
    with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name in sorted(directories):
            info = tarfile.TarInfo(name + "/")
            info.type, info.mode = tarfile.DIRTYPE, 0o755
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            info.mtime = epoch
            archive.addfile(info)
        for name, (data, mode) in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), mode, epoch
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            archive.addfile(info, io.BytesIO(data))
    return lzma.compress(output.getvalue(), format=lzma.FORMAT_XZ, preset=6)


def ar(members, epoch):
    output = bytearray(b"!<arch>\n")
    for name, data in members:
        header = f"{name + '/':<16}{epoch:<12}{0:<6}{0:<6}{'100644':<8}{len(data):<10}`\n".encode()
        if len(header) != 60:
            raise ValueError("Invalid ar header")
        output.extend(header + data + (b"\n" if len(data) % 2 else b""))
    return bytes(output)


def control(release, arch, installed_size):
    return (
        "Package: flashdata\n"
        f"Version: {release['debian_version']}\n"
        "Section: utils\nPriority: optional\n"
        f"Architecture: {arch}\n"
        "Maintainer: FlashData <support@flashdata.dev>\n"
        f"Installed-Size: {installed_size}\n"
        "Depends: ca-certificates\n"
        "Homepage: https://flashdata.dev\n"
        "Description: FlashData search, YouTube data and bulk workflows\n"
        " Standalone API client with secure credential profiles, background jobs,\n"
        " bulk exports and durable run recovery. API use requires a FlashData key.\n"
    )


def upstream(release, arch):
    name = f"flashdata_{release['upstream_version']}_linux_{arch}.tar.gz"
    cache = ROOT / ".cache" / name
    if not cache.exists():
        cache.parent.mkdir(exist_ok=True)
        url = f"https://github.com/flashdatadev/flashdata-cli/releases/download/v{release['upstream_version']}/{name}"
        with urllib.request.urlopen(url, timeout=90) as response:
            cache.write_bytes(response.read())
    payload = cache.read_bytes()
    if sha(payload) != release["archives"][arch]:
        raise ValueError(f"Upstream archive checksum mismatch: {name}")
    files = {}
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        for member in archive.getmembers():
            path = pathlib.PurePosixPath(member.name)
            if not member.isfile() or path.is_absolute() or ".." in path.parts or member.name in files:
                raise ValueError(f"Unexpected upstream member: {member.name}")
            files[member.name] = archive.extractfile(member).read()
    binary = files["flashdata"]
    if sha(binary) != release["executables"][arch]:
        raise ValueError("Executable differs from verified v1.0.0 release")
    if binary[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", binary, 18)[0] != {"amd64": 62, "arm64": 183}[arch]:
        raise ValueError("Executable architecture mismatch")
    return files


def build(release, arch, upstream_files):
    epoch = release["source_date_epoch"]
    doc = "usr/share/doc/flashdata/"
    files = {"usr/bin/flashdata": (upstream_files["flashdata"], 0o755)}
    for name, data in upstream_files.items():
        if name != "flashdata" and name != "release-files.json":
            files[doc + name] = (data, 0o644)
    files[doc + "copyright"] = ((
        "Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/\n"
        "Upstream-Name: FlashData CLI\nSource: https://github.com/flashdatadev/flashdata-cli\n\n"
        "Files: *\nCopyright: 2026 FlashData\nLicense: MIT\n "
        + upstream_files["LICENSE"].decode().strip().replace("\n\n", "\n.\n").replace("\n", "\n ")
        + "\n\nComment: Dependency notices and license texts are shipped in THIRD_PARTY_NOTICES.md and licenses/.\n"
    ).encode(), 0o644)
    date = email.utils.format_datetime(dt.datetime.fromtimestamp(epoch, dt.timezone.utc))
    changelog = f"flashdata ({release['debian_version']}) stable; urgency=medium\n\n  * Package official FlashData CLI {release['upstream_version']} without changing the executable.\n\n -- FlashData <support@flashdata.dev>  {date}\n"
    files[doc + "changelog.Debian.gz"] = (gz(changelog.encode()), 0o644)
    provenance = {k: release[k] for k in ("upstream_version", "debian_version", "source_commit")}
    provenance.update({"architecture": arch, "archive_sha256": release["archives"][arch], "executable_sha256": release["executables"][arch]})
    files[doc + "build-info.json"] = ((json.dumps(provenance, indent=2) + "\n").encode(), 0o644)
    man = f'''.TH FLASHDATA 1 "2026-10" "FlashData {release['upstream_version']}" "User Commands"
.SH NAME
flashdata \\- Google Search, YouTube data and bulk workflows
.SH SYNOPSIS
.B flashdata
[command] [flags]
.SH DESCRIPTION
FlashData CLI provides API-key profiles, background jobs, bulk exports and durable run recovery.
.SH COMMANDS
.TP
.B auth login
Import an API key with hidden input. Obtain a key from https://flashdata.dev.
.TP
.B search QUERY
Run a Google search. Normal FlashData billing applies.
.TP
.B query --input FILE
Run a Data API JSON request.
.TP
.B bulk
Create, upload, control and export bulk tasks.
.TP
.B runs
Inspect or recover durable local runs.
.SH OPTIONS
.TP
.B --help
Show help; command-specific help is available with COMMAND --help.
.TP
.B --version
Show the upstream version and source commit without network access.
.TP
.B --json
Write a versioned JSON envelope.
.SH FILES
Examples and English/Chinese documentation: /usr/share/doc/flashdata/.
Package removal does not delete credentials or run history. See the security documentation.
.SH SEE ALSO
https://flashdata.dev/docs
.br
https://github.com/flashdatadev/flashdata-cli
'''
    files["usr/share/man/man1/flashdata.1.gz"] = (gz(man.encode()), 0o644)
    text = control(release, arch, (sum(len(data) for data, _ in files.values()) + 1023) // 1024)
    sums = "".join(f"{hashlib.md5(data, usedforsecurity=False).hexdigest()}  {name}\n" for name, (data, _) in sorted(files.items()))
    controls = {"control": (text.encode(), 0o644), "md5sums": (sums.encode(), 0o644)}
    package = ar([("debian-binary", b"2.0\n"), ("control.tar.xz", tar_xz(controls, epoch)), ("data.tar.xz", tar_xz(files, epoch))], epoch)
    return package, text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--create", action="store_true", help="Create new package files; record checksums in manifest separately")
    parser.add_argument("--fixtures", type=pathlib.Path)
    args = parser.parse_args()
    for release in manifest()["releases"]:
        for arch in ("amd64", "arm64"):
            source = upstream(release, arch)
            package, _ = build(release, arch, source)
            path = ROOT / "packages" / f"flashdata_{release['debian_version']}_{arch}.deb"
            if args.create and not path.exists():
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(package)
            if not path.exists() or path.read_bytes() != package:
                raise ValueError(f"Package is missing or not reproducible: {path.name}")
            expected = release["packages"].get(arch)
            if expected and sha(package) != expected:
                raise ValueError(f"Published package checksum changed: {path.name}; use a new Debian revision")
            if not expected and not args.create:
                raise ValueError("Record the new Debian package SHA-256 in releases.json before publishing")
            if args.fixtures:
                old = {**release, "debian_version": release["debian_version"] + "~upgrade-test"}
                data, _ = build(old, arch, source)
                args.fixtures.mkdir(parents=True, exist_ok=True)
                (args.fixtures / f"older_{arch}.deb").write_bytes(data)
            print(f"{path.name}  {sha(package)}")


if __name__ == "__main__":
    main()
