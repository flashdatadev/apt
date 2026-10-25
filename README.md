# FlashData APT repository

[简体中文](README.zh-CN.md) · [FlashData](https://flashdata.dev) · [API docs](https://flashdata.dev/docs) · [CLI repository](https://github.com/flashdatadev/flashdata-cli)

The official signed APT repository for the open-source FlashData CLI. [FlashData](https://flashdata.dev) provides structured Google Search and YouTube data. The CLI adds secure credential profiles, background jobs, bulk exports and durable run recovery.

Packages support **Ubuntu 22.04/24.04 and Debian 12/13**, on **amd64 and arm64**. Package `flashdata` **1.2.1-1** contains the unchanged CLI **1.2.1** executable. The suffix `-1` is the Debian packaging revision. No Go, Python or Node.js runtime is required.

## Install

Run these Bash commands with sudo access. They install the HTTPS/GPG prerequisites, check the public key fingerprint, configure repository-scoped trust and package selection, and install the CLI:

```bash
(
  set -eu
  arch="$(dpkg --print-architecture)"
  case "$arch" in amd64|arm64) ;; *) echo "Unsupported architecture: $arch" >&2; exit 1 ;; esac
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl gnupg
  work_dir="$(mktemp -d)"
  trap 'rm -rf -- "$work_dir"' EXIT
  curl --fail --location https://flashdatadev.github.io/apt/flashdata.asc --output "$work_dir/flashdata.asc"
  expected=19F337AC01C5F5B646A5583A04C7934A11D38FFA
  actual="$(gpg --batch --show-keys --with-colons "$work_dir/flashdata.asc" 2>/dev/null | awk -F: '$1 == "fpr" { print $10; exit }')"
  test "$actual" = "$expected"
  sudo install -d -m 0755 /etc/apt/keyrings
  sudo install -m 0644 "$work_dir/flashdata.asc" /etc/apt/keyrings/flashdata.asc
  sudo tee /etc/apt/sources.list.d/flashdata.sources >/dev/null <<EOF
Types: deb
URIs: https://flashdatadev.github.io/apt/
Suites: stable
Components: main
Architectures: $arch
Signed-By: /etc/apt/keyrings/flashdata.asc $expected
EOF
  sudo tee /etc/apt/preferences.d/flashdata >/dev/null <<'EOF'
Package: flashdata
Pin: release o=FlashData
Pin-Priority: 500

Package: *
Pin: release o=FlashData
Pin-Priority: -1
EOF
  sudo apt-get update
  sudo apt-get install -y flashdata
  flashdata --version
  flashdata --help
)
```

The repository is `https://flashdatadev.github.io/apt/`, suite `stable`, component `main`. Its dedicated signing certificate is **`19F337AC01C5F5B646A5583A04C7934A11D38FFA`**, identified as `FlashData APT Signing <support@flashdata.dev>`. The [public key](keys/flashdata.asc) and [fingerprint](keys/fingerprint.txt) are also recorded in this source repository. Do not disable signature checking or import this key into APT's global trusted keyring.

After installation, set up your agent:

```bash
flashdata setup
```

Setup selects Codex, Claude Code or Cursor, installs bundled skills and verifies access without a paid query. Content queries in skills use plain text by default; bulk exports stay JSONL. CLI v1.2.1 bundles bulk guides for the main skill and five YouTube skills. Rerun `flashdata setup` after upgrading to refresh unmodified skills; MCP is optional. To use an existing key, run `flashdata auth login` before setup. For the uv installation option, see the [CLI setup guide](https://github.com/flashdatadev/flashdata-cli#readme).

Installation and offline version/help checks need no API key. Submitted API queries and jobs use normal FlashData billing. See the [English CLI README](https://github.com/flashdatadev/flashdata-cli#readme) and [简体中文](https://github.com/flashdatadev/flashdata-cli/blob/main/README.zh-CN.md) for query, onboarding, bulk and recovery workflows.

## Upgrade

```bash
sudo apt-get update
sudo apt-get install --only-upgrade flashdata
flashdata --version
```

APT upgrades become available when a newer CLI or Debian package revision is published. The binary's version is the upstream CLI version; inspect the packaging revision with:

```bash
dpkg-query -W -f='${Version}\n' flashdata
apt-cache policy flashdata
```

If you previously installed with Homebrew or a standalone archive, check `command -v flashdata`. An earlier PATH entry may hide `/usr/bin/flashdata`. Uninstall or move that old executable, or adjust PATH; retain the CLI state directory and restart the shell or run `hash -r`.

## Documentation and uninstall

```bash
ls /usr/share/doc/flashdata/examples
ls /usr/share/doc/flashdata/docs
man flashdata
```

Examples, English/Chinese release docs, build provenance and third-party license notices are included. These are the v1.2.1 release documentation snapshot; current installation instructions are in this repository and the CLI repository.

```bash
sudo apt-get remove flashdata
```

Package removal or purge does not revoke API keys or delete per-user profiles and run history. To remove a saved credential, use `flashdata auth logout` for that profile before uninstalling. See [credential storage](https://github.com/flashdatadev/flashdata-cli/blob/main/docs/security.md).

To also remove the repository configuration:

```bash
sudo rm -f /etc/apt/sources.list.d/flashdata.sources /etc/apt/preferences.d/flashdata /etc/apt/keyrings/flashdata.asc
sudo apt-get update
```

## Verification and maintenance

[GitHub Actions](https://github.com/flashdatadev/apt/actions) reproduces both packages from pinned release archives, signs the APT indexes, tests Ubuntu 22.04/24.04 and Debian 12/13 on both architectures before deployment, and repeats installation/upgrade checks against the published HTTPS repository. Tests cover reinstall/removal, preservation of user state, and rejection of unrelated keys, changed signatures and modified package bytes.

Upgrade checks install the actual previous **1.2.0-1** package and upgrade through APT to **1.2.1-1**, verifying the new executable hash and preserved user state. An additional test-only packaging revision (`1.2.1-1~upgradetest`) checks packaging upgrades; it is never publicly indexed. Both original 1.0.0 packages remain available unchanged.

Signed metadata expires after 30 days. The publishing workflow refreshes it weekly and supports manual runs; the workflow refuses a signing key expiring within 30 days. See [maintainer instructions](docs/maintaining.md) and [signing/security](SECURITY.md). Package updates require a new Debian version; existing versioned packages and upstream tags must remain unchanged.

Packaging issues: [repository issues](https://github.com/flashdatadev/apt/issues). CLI bugs: [CLI issues](https://github.com/flashdatadev/flashdata-cli/issues). Account support: [support@flashdata.dev](mailto:support@flashdata.dev).
