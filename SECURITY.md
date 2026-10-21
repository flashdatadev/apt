# APT signing and security

[FlashData](https://flashdata.dev) · [Installation](README.md) · [简体中文](README.zh-CN.md)

Report vulnerabilities privately to [support@flashdata.dev](mailto:support@flashdata.dev). Do not post API keys, credentials or signing secrets in public issues.

The dedicated primary signing certificate fingerprint is `19F337AC01C5F5B646A5583A04C7934A11D38FFA` (`FlashData APT Signing <support@flashdata.dev>`). A signing subkey authenticates InRelease and Release.gpg. Signed metadata authenticates index checksums, which authenticate package bytes; individual `.deb` files are not separately OpenPGP signed. Use APT with the documented Signed-By configuration to verify the complete chain.

The signing key has a two-year expiry and the metadata has a 30-day validity window, refreshed by the publishing workflow. The workflow rejects keys expiring within 30 days. Packages include the exact checked upstream executable, English/Chinese documentation, license notices and build provenance. They contain no maintainer scripts, do not create users/services, and do not read, write or remove per-user credentials during install, upgrade, removal or purge.

The repository preference permits `flashdata` and blocks other package names from this repository. Trust is scoped to `/etc/apt/keyrings/flashdata.asc`; it is never added to APT's global keyring. Never use `trusted=yes`, `apt-key add`, insecure repository overrides or disabled expiration checking to work around verification failures.

The certification key is excluded from CI. The passphrase-protected signing subkey is stored in a main-only GitHub environment. See [maintenance and key recovery](docs/maintaining.md). Repository administrators and trusted workflow changes can access the signing environment, so review changes to workflows and signing scripts as carefully as a release.
