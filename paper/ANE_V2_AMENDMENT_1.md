# ANE Trace Protocol Amendment 1: Signing and Publication Boundary

Date: 2026-08-29
Status: prospective; no ANE trace has been collected

`EXPERIMENT_PROTOCOL_V1.md` requires the Release application used for the ANE
trace to be identified and signed. A complete signing record can contain a
development-team identifier and certificate authority strings, while trace
commands and raw trace exports can contain persistent device identifiers and
host paths. These values are not scientific inputs and will not be published.

Before installation, the identity preparation step will run
`codesign --verify --deep --strict` against the sealed Release application.
The public record may state `signed: true` only after that command succeeds.
The Xcode project embeds `$(CONFIGURATION)` in the generated Info.plist, and
identity preparation requires the built value to be exactly `Release`; the
script cannot assign that configuration label itself.
The step will then create two bound records:

- a private record, stored outside both the repository and publication
  directory with mode `0600`, containing the signing Identifier, team
  identifier, authority chain, verification result, and the SHA-256 digest of
  the public identity record; and
- a public record containing only the fixed bundle identifier, `signed: true`,
  CDHash, signature format, SHA-256 digests of the entitlements and complete
  `codesign` display, and the existing executable, Info.plist, and app-bundle
  manifest digests.

The public analyzer will accept that signing allowlist exactly and will reject
an unsigned build, an unexpected bundle identifier, the previous public
identity schema, or injected signing Identifier, team, or authority fields.
Run metadata will record that the private-to-public binding was verified, but
will not disclose the private record or a reusable digest of it. The amendment
itself and its SHA-256 digest become part of the source identity.

The publication boundary also changes before acquisition:

1. Neither the device identifier nor a hash of it is written to public
   evidence. Public command records use fixed placeholders for the device,
   template, trace, and export paths; the executed commands remain private.
2. Application marker records expose only stable protocol events and fields.
   Reflected error strings, raw console output, and unknown event fields remain
   private.
3. Canonicalization writes a complete canonical table to the private directory
   and a separate public table containing only rows owned by the captured PID.
   The public table records a SHA-256 commitment to the complete table and an
   aggregate count of omitted other-process rows. Public analysis contains
   only target-process measurements and aggregate exclusion counts; it never
   copies another process's row.
4. The signed application, provisioning profile, build logs, device console,
   raw stdout/stderr, raw trace, and unreviewed trace exports remain private.
   Their retained private evidence is content-addressed; only a separately
   reviewed, allowlisted public bundle may be published.

The three published column mappings use exact top-level and per-column
allowlists. The public-bundle validator scans original JSON bytes before
parsing, rejects private paths and tokens, rejects duplicate keys, and then
applies exact schemas to every public JSON document. It also recomputes the
current Git commit and the actual protocol, amendment, analyzer,
canonicalizer, sealer, validator, application-source, and Xcode-project bytes
recorded by the source identity. Altering any bound file after identity sealing
invalidates the run. The Core AI build is accepted only as a complete dotted
version token parsed from a Core AI build/version field or row in the retained
ODIEProfile XML, not as an arbitrary byte substring.

The public target rows, deterministic analysis, commitment value, and declared
omission count are independently inspectable. Because the omitted rows remain
private, the public bundle alone cannot recompute the commitment or verify the
omission count; that limitation is the deliberate privacy boundary.

No trace is admissible unless the strict signature verification, public/private
binding, source and artifact identity checks, fixed application records, and
recursive public-bundle privacy check all pass. This amendment changes no
model artifact, workload, trace template, signpost interval, target device,
toolchain, or ANE attribution rule.
