# Public-package security boundary

This repository must remain reproducible without publishing private or
redistribution-restricted payloads.

## Included

- documentation;
- source patch;
- compression recipe;
- sanitized aggregate results;
- unsigned, resource-free companion source;
- license and third-party notices.

## Excluded

- SafeTensors weights and tokenizer payloads;
- `.aimodel`, `.aimodelc`, `.mlirb`, AAR, and compiled app bundles;
- signing teams, provisioning profiles, certificates, keys, and entitlements;
- device identifiers, serial numbers, tunnel addresses, and local account
  paths;
- raw device logs, Instruments traces, private prompts, and product source;
- credentials, access tokens, and API keys.

Generated Core AI containers may preserve absolute build paths even when their
sidecar metadata has been sanitized. Any separately distributed `.aimodel` or
`.aimodelc` must therefore be rebuilt under a neutral path and pass
`scripts/audit-public-artifact.sh` before upload. Binary string replacement is
not an accepted remediation because it can invalidate the generated container.

Before each public release:

1. verify every JSON and YAML file parses;
2. apply the patch against the locked Apple base;
3. run the focused unit tests, Ruff, and companion unsigned build;
4. scan for local paths, device/signing identifiers, credentials, and excluded
   binary extensions;
5. regenerate `CHECKSUMS.sha256` last.

Security issues should be reported privately to the repository owner rather
than posted with sensitive reproduction data.

## Current release audit

Audit date: 2026-07-19

Status: **pass**

- 23 public files before the checksum manifest;
- no local home/temp paths, local account names, private product identifiers,
  signing teams, device identifiers, development-server addresses, or
  credentials detected;
- no model, tokenizer, compiled artifact, signed application, trace, result
  bundle, certificate, key, or provisioning payload detected;
- no file larger than 5 MiB;
- every JSON, YAML, project, and Swift package resolution file parsed;
- the patch applied cleanly to Apple main
  `04a3fd6cfe9bfae9cf05b1f246cf915d930d1c0a`;
- 28 focused tests and Ruff passed from the applied public patch;
- the preset dry-run resolved the frozen mechanism;
- the resource-free companion built unsigned with Xcode 27 against the same
  Apple main revision.
