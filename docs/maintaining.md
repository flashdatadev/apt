# Maintaining the signed repository

[FlashData](https://flashdata.dev) · [English installation](../README.md) · [简体中文](../README.zh-CN.md)

The repository is served at https://flashdatadev.github.io/apt/ using GitHub Pages. Source, pinned package files, release checksums and public keys are in `flashdatadev/apt`; the generated APT tree is a Pages artifact, never a working directory containing secrets.

## New versions

1. Release and verify the upstream CLI Linux amd64/arm64 archives first. Record their upstream version, source commit, source-date epoch, archive hashes and executable hashes in a new entry in `releases.json`.
2. Choose a new Debian version, such as `1.0.1-1` for a new CLI or `1.0.0-2` for a packaging-only correction. Never replace an existing version's `.deb`, binary, tag or manifest checksum.
3. Run `python3 scripts/build_packages.py --create`. Review the packages and record their printed SHA-256 values in the entry's `packages` field. Commit both immutable `.deb` files under `packages/` with the manifest change. Keep old entries and packages so older authenticated indexes remain usable.
4. Run `python3 -m unittest discover -s tests -p 'test_*.py'` and `python3 scripts/build_packages.py`. Update the test version assertions when intentionally releasing a new package. Review Ubuntu/Debian and architecture support before adding dependencies.
5. Push the reviewed change to main. The workflow validates reproducibility, signs metadata, tests the candidate in eight native-architecture Ubuntu/Debian containers, deploys through GitHub Pages, then tests the public HTTPS endpoint in the same matrix. Check every job before announcing the release.

For v1.0.1, all eight candidate and eight public containers install the actual **1.0.0-1** package, upgrade through APT to **1.0.1-1**, verify package/executable integrity and retain user state. Tests also use an older local packaging fixture with the same current executable; it is a short-lived CI artifact and never appears in public APT indexes. Current/previous versions are read from the append-only ledger.

## Metadata freshness

`Release` has a 30-day Valid-Until. A Monday workflow refreshes metadata and reruns checks, even if package versions have not changed. Run the **APT repository** workflow manually to renew or recover a failed deployment. A failed pre-deployment test keeps the previously published site intact. Watch workflow failures and the key's expiry; a repository whose metadata has expired must be repaired by its maintainer, not by telling users to bypass date/signature checks.

GitHub may disable schedules in inactive public repositories after an extended period without activity. Check the workflow is enabled during routine release maintenance; a manual workflow run can refresh metadata. Keep security expiry enforcement in place.

Package records are authenticated through InRelease/Release.gpg → SHA-256/SHA-512 indexes → package SHA-256/SHA-512. Acquire-By-Hash is enabled, and historical index hashes are retained by regenerating each prefix of the immutable release ledger.

## Signing and recovery

The `apt-signing` GitHub environment is restricted to main and contains `APT_SIGNING_PRIVATE_KEY` (signing subkey export with a stub primary secret) and `APT_SIGNING_PASSPHRASE`. Only the signing job receives these values; candidate/public tests and pull requests do not. The certification primary key is kept out of CI. The signing job imports into a temporary private keyring outside the artifact tree, validates the pinned public certificate and expiry, signs with SHA-256, and removes the temporary keyring.

The initial owner's full primary/subkey export, passphrase and revocation certificate are backed up in a Windows DPAPI-encrypted file at `%LOCALAPPDATA%\FlashData\apt-signing\signing-backup.dpapi`, with an ACL limited to that Windows user and SYSTEM. Recovery needs that Windows account/profile; this is not a portable organizational backup. An account owner should place a separately encrypted recovery export in FlashData's approved offline secret store before migrating or deleting the Windows profile. Never put key exports, passphrases or decrypted backups in Git, release assets, logs or Pages artifacts.

For rotation, use the protected certification key or establish a replacement certificate, review the new fingerprint through a trusted channel, update public key files and instructions, update environment secrets, and test every supported APT version before switching signatures. Existing installations must receive and verify the new certificate before old signatures expire. Maintain an overlap period where needed. For compromise, stop deployment, revoke the affected key, publish the revocation and replacement guidance, and use a separately trusted channel to distribute the new fingerprint. Do not silently overwrite the key at a stable URL and ask users to accept it without verification.
