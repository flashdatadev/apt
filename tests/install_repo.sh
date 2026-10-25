#!/usr/bin/env bash
# Run only in disposable Ubuntu/Debian containers as root.
set -euo pipefail
trap 'echo "APT test failed at line $LINENO" >&2' ERR
export DEBIAN_FRONTEND=noninteractive
base_url="${1:?repository URL required}"
fixtures="${2:?fixture directory required}"
mode="${3:-candidate}"
arch="$(dpkg --print-architecture)"
fingerprint=19F337AC01C5F5B646A5583A04C7934A11D38FFA
apt-get update -o APT::Update::Error-Mode=any
apt-get install -y --no-install-recommends ca-certificates curl gnupg python3
version="$(python3 -c "import json;print(json.load(open('/work/releases.json'))['releases'][-1]['upstream_version'])")"
package_version="$(python3 -c "import json;print(json.load(open('/work/releases.json'))['releases'][-1]['debian_version'])")"
if [ "$mode" = live ]; then
  apt-get install -y --no-install-recommends sudo
  # Execute the exact documented Bash block, including sudo and fingerprint checks.
  python3 - > /tmp/documented-install.sh <<'PY'
import pathlib,re
first=lambda name: re.search(r'```bash\n(.*?)```', pathlib.Path('/work',name).read_text(), re.S).group(1)
assert first('README.md') == first('README.zh-CN.md')
print(first('README.md'))
PY
  bash /tmp/documented-install.sh
fi
curl -fsSL "$base_url/flashdata.asc" -o /tmp/flashdata.asc
actual="$(gpg --batch --show-keys --with-colons /tmp/flashdata.asc 2>/dev/null | awk -F: '$1 == "fpr" {print $10; exit}')"
test "$actual" = "$fingerprint"
install -d -m 0755 /etc/apt/keyrings
install -m 0644 /tmp/flashdata.asc /etc/apt/keyrings/flashdata.asc
cat > /etc/apt/sources.list.d/flashdata.sources <<EOF
Types: deb
URIs: $base_url/
Suites: stable
Components: main
Architectures: $arch
Signed-By: /etc/apt/keyrings/flashdata.asc $fingerprint
By-Hash: force
EOF
cat > /etc/apt/preferences.d/flashdata <<'EOF'
Package: flashdata
Pin: release o=FlashData
Pin-Priority: 500

Package: *
Pin: release o=FlashData
Pin-Priority: -1
EOF
apt-get update -o APT::Update::Error-Mode=any
apt-cache policy flashdata
apt-get install -y flashdata
test "$(dpkg-query -W -f='${Version}' flashdata)" = "$package_version"
flashdata --version --json | tee /tmp/flashdata-version.json
python3 - <<'PY'
import json
v=json.load(open('/tmp/flashdata-version.json'))
m=json.load(open('/work/releases.json'))['releases'][-1]
assert v['ok'] and v['data']=={'version':m['upstream_version'],'commit':m['source_commit']}
PY
flashdata --help
flashdata discover plans --help
flashdata discover status --help
flashdata commands --json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert {"auth","bulk","query","runs","setup","skills"} <= {c["name"] for c in d["data"]["commands"]}'
# Exercise the bundled skills without credentials or paid queries.
skill_project="$(mktemp -d)"
flashdata setup --skip-auth --agent codex --directory "$skill_project" --non-interactive
flashdata skills verify --agent codex --directory "$skill_project" --non-interactive
test -s "$skill_project/.agents/skills/flashdata/SKILL.md"
test -s "$skill_project/.agents/skills/youtube-transcript/SKILL.md"
test -s /usr/share/doc/flashdata/README.zh-CN.md
test -s /usr/share/doc/flashdata/examples/query.json
test -s /usr/share/man/man1/flashdata.1.gz
dpkg -V flashdata
install -d -m 0700 "$HOME/.local/state/flashdata"
printf 'preserve profiles and run history\n' > "$HOME/.local/state/flashdata/package-test-marker"
chmod 0600 "$HOME/.local/state/flashdata/package-test-marker"
python3 /work/tests/upgrade_state.py prepare "$HOME/.local/state/flashdata"
apt-get install -y --reinstall flashdata
test -s "$HOME/.local/state/flashdata/package-test-marker"
apt-get remove -y flashdata
test ! -e /usr/bin/flashdata
test -s "$HOME/.local/state/flashdata/package-test-marker"
# Exercise a real previous public release, not only a packaging fixture.
previous="$(python3 -c "import json;print(json.load(open('/work/releases.json'))['releases'][-2]['debian_version'])")"
dpkg -i "/work/packages/flashdata_${previous}_${arch}.deb"
test "$(dpkg-query -W -f='${Version}' flashdata)" = "$previous"
flashdata --version
python3 /work/tests/upgrade_state.py check "$HOME/.local/state/flashdata"
apt-get install -y --only-upgrade flashdata
test "$(dpkg-query -W -f='${Version}' flashdata)" = "$package_version"
test -s "$HOME/.local/state/flashdata/package-test-marker"
dpkg -V flashdata
python3 /work/tests/upgrade_state.py check "$HOME/.local/state/flashdata"
apt-get remove -y flashdata
dpkg -i "$fixtures/older_${arch}.deb"
dpkg --compare-versions "$(dpkg-query -W -f='${Version}' flashdata)" lt "$package_version"
apt-get install -y --only-upgrade flashdata
test "$(dpkg-query -W -f='${Version}' flashdata)" = "$package_version"
test -s "$HOME/.local/state/flashdata/package-test-marker"
dpkg -V flashdata
python3 /work/tests/upgrade_state.py check "$HOME/.local/state/flashdata"
python3 - "$arch" <<'PY'
import hashlib,json,sys
m=json.load(open('/work/releases.json'))['releases'][-1]
assert hashlib.sha256(open('/usr/bin/flashdata','rb').read()).hexdigest()==m['executables'][sys.argv[1]]
PY
apt-get purge -y flashdata
test ! -e /usr/bin/flashdata
test -s "$HOME/.local/state/flashdata/package-test-marker"

if [ "$mode" = candidate ]; then
  # An unrelated signing key must not authorize this repository.
  export GNUPGHOME="$(mktemp -d)"
  chmod 0700 "$GNUPGHOME"
  gpg --batch --passphrase '' --quick-generate-key 'APT negative test <invalid@example.invalid>' ed25519 sign 0
  gpg --export > /tmp/wrong-key.gpg
  cat > /tmp/negative.sources <<EOF
Types: deb
URIs: $base_url/
Suites: stable
Components: main
Architectures: $arch
Signed-By: /tmp/wrong-key.gpg
EOF
  mkdir -p /tmp/negative-lists/partial
  negative_options=(-o Dir::Etc::sourcelist=/tmp/negative.sources -o Dir::Etc::sourceparts=- -o Dir::State::lists=/tmp/negative-lists -o APT::Update::Error-Mode=any)
  if apt-get "${negative_options[@]}" update > /tmp/wrong-key.log 2>&1; then
    echo 'APT accepted an unrelated signing key' >&2; exit 1
  fi
  grep -Ei 'NO_PUBKEY|Missing key|public key|signature|signed' /tmp/wrong-key.log
  # Changing signed metadata must fail authentication.
  cp -a /work/dist /tmp/tampered
  sed -i 's/Origin: FlashData/Origin: Tampered/' /tmp/tampered/dists/stable/InRelease
  python3 -m http.server 8766 --bind 127.0.0.1 --directory /tmp/tampered >/tmp/tampered-server.log 2>&1 &
  server_pid=$!
  trap 'kill "$server_pid" 2>/dev/null || true' EXIT
  sed -i "s|$base_url/|http://127.0.0.1:8766/|; s|/tmp/wrong-key.gpg|/etc/apt/keyrings/flashdata.asc|" /tmp/negative.sources
  sleep 1
  if apt-get "${negative_options[@]}" update > /tmp/bad-signature.log 2>&1; then
    echo 'APT accepted changed signed metadata' >&2; exit 1
  fi
  grep -Ei 'BADSIG|Bad signature|signature|signed' /tmp/bad-signature.log
  # Signed indexes must also protect the package bytes.
  cp /work/dist/dists/stable/InRelease /tmp/tampered/dists/stable/InRelease
  printf 'tamper' >> "/tmp/tampered/pool/main/f/flashdata/flashdata_${package_version}_${arch}.deb"
  apt-get "${negative_options[@]}" update
  mkdir /tmp/tampered-download
  if (cd /tmp/tampered-download && apt-get "${negative_options[@]}" download flashdata) > /tmp/bad-package.log 2>&1; then
    echo 'APT accepted altered package bytes' >&2; exit 1
  fi
  grep -Ei 'unexpected size|Hash Sum mismatch|hash.*mismatch|File has unexpected' /tmp/bad-package.log
fi
echo "PASS: $mode $(. /etc/os-release; echo "$ID $VERSION_ID") $arch install/reinstall/upgrade/purge and preserved user state"
