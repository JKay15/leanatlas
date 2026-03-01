# ripgrep (`rg`) Install and Verify

> `rg` is not a Lean compiler dependency, but it is important in two cases:
> 1) one local-search backend for `lean-lsp-mcp`
> 2) deterministic in-repo fallback search when MCP is unavailable
>
> Version requirement: see `tools/deps/pins.json` (current recommendation `>= 13.0.0`).

## 1) Install

- macOS (Homebrew):
  ```bash
  brew install ripgrep
  ```

- Ubuntu/Debian:
  ```bash
  sudo apt-get update
  sudo apt-get install -y ripgrep
  ```

- Arch:
  ```bash
  sudo pacman -S ripgrep
  ```

- Windows:
  - recommended via scoop/choco, or download from release page

## 2) Verify

```bash
rg --version
```

## 3) Where LeanAtlas uses it

- OPERATOR: retrieval-ladder fallback when MCP is unavailable
- MAINTAINER: bulk scans (imports/rename/migration pre-checks)
