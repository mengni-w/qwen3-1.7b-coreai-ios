# Public speed-v2 acquisition evidence

This directory is the publication-safe copy of one immutable acquisition.
Raw files that can contain a device identifier, signing team, signing identity,
personal device name, or absolute local path remain private. The public evidence
index binds the complete private index by byte count and SHA-256 digest without
repeating private filenames. Scientific result files are copied byte for byte.
Structured public JSON is rebuilt from fixed field allowlists. Text transcripts
are normalized only for private identifiers and absolute local paths; benchmark
events and ordinary diagnostic lines are otherwise retained. The two ABI-only
preflight records precede every measured block and prove that each app reached
its own code on the device. Build `.xcresult` bundles remain private originals
committed by the private index.
