# ADR 0018 — Separate saved replay from new model execution

Status: accepted for Phase 24.

Package allowlisted Git-visible source/config/docs/tests plus explicitly selected
saved run files in a deterministic ZIP. Include resolved model/effort/seed and
input/config hashes; retain every run score and trace. Preserve benchmark
attribution. Do not include credentials, environment files, spending databases,
model caches or full dataset downloads. This is a local research archive, not a
public dataset release.

Verification checks exact member inventory and content hashes without extraction;
traversal, duplicate names and modified/extra members are rejected. Inputs must
stay within the repository and symlinks are refused. The source commit and dirty
status describe exactly what was archived; a clean committed tree is the release
path. Export never changes the original project ledger.

A small Python driver runs fixed fixture commands in a fresh checkout, or
recomputes saved paper outputs in a fresh destination. It rejects .env and removes
the key from child environments. No automatic paid execution or redownload is
part of replay. The script verifies numeric tables and statistics exactly while
allowing platform-dependent figure rendering and fixture timestamps.
