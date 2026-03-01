# tools/gc/gcroots (optional: local symlink roots)

This is an **optional** GC roots mechanism inspired by Nix gcroots.

- If you want to temporarily/local-pin a Seed, create a symlink here that points to the Seed file.
- GC merges these local roots with the version-controlled roots in `tools/gc/roots.json`.

Why optional?
- Symlinks are not always friendly on Windows/some environments.
- The repo-level source of truth remains `tools/gc/roots.json`.

## Usage

Example: pin a seed (use a relative path so it is portable):

```bash
ln -s ../../LeanAtlas/Incubator/Seeds/Algebra/MySeed.lean tools/gc/gcroots/pin-myseed
```

Remove the pin:

```bash
rm tools/gc/gcroots/pin-myseed
```

## Git convention

This directory defaults to **not committing symlinks** (see `.gitignore`).

- If a local pin should become a long-term repo policy, backfill it into `tools/gc/roots.json`.
