#!/usr/bin/env python3
"""Agent invocation resolver for Phase6 runners and automation advisor paths."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional

from jsonschema import Draft202012Validator


DEFAULT_PROVIDER_PRESETS: Dict[str, Dict[str, str]] = {
    "codex_cli": {
        "base_cmd": "codex exec",
        "prompt_transport": "stdin",
    },
    "claude_code": {
        "base_cmd": "claude exec",
        "prompt_transport": "stdin",
    },
}


@dataclass(frozen=True)
class ResolvedAgentInvocation:
    provider_id: str
    agent_cmd: str
    source: str
    profile_path: Optional[str]
    env: Dict[str, str]
    env_map: Dict[str, str]
    prompt_transport: str
    prompt_arg: str
    capabilities: Dict[str, bool]

    def apply_env_map(self, env: Dict[str, str]) -> Dict[str, str]:
        out = dict(env)
        for source_key, target_key in self.env_map.items():
            if source_key in out:
                out[target_key] = out[source_key]
        out.update(self.env)
        return out

    def to_metadata(self) -> Dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "source": self.source,
            "profile_path": self.profile_path,
            "agent_cmd_sha256": hashlib.sha256(self.agent_cmd.encode("utf-8")).hexdigest(),
            "env_keys": sorted(self.env.keys()),
            "env_map": dict(self.env_map),
            "prompt_transport": self.prompt_transport,
            "prompt_arg": self.prompt_arg,
            "capabilities": dict(self.capabilities),
        }


def _load_schema(repo_root: Path) -> Dict[str, object]:
    path = repo_root / "docs" / "schemas" / "AgentProfile.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_profile(path: Path, *, repo_root: Path) -> Dict[str, object]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    schema = _load_schema(repo_root)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(obj), key=lambda e: list(e.absolute_path))
    if errors:
        lines = [f"Agent profile failed schema validation: {path}"]
        for err in errors[:20]:
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            lines.append(f"- {loc}: {err.message}")
        if len(errors) > 20:
            lines.append(f"- ... {len(errors) - 20} more")
        raise ValueError("\n".join(lines))
    if not isinstance(obj, dict):
        raise ValueError(f"Agent profile root must be object: {path}")
    return obj


def _resolve_provider_preset(provider_id: str) -> Dict[str, str]:
    preset = DEFAULT_PROVIDER_PRESETS.get(provider_id)
    if preset is None:
        known = ", ".join(sorted(DEFAULT_PROVIDER_PRESETS.keys()))
        raise ValueError(f"Unknown provider `{provider_id}`. Known providers: {known}")
    return preset


def _build_default_command(*, provider_id: str, prompt_transport: str, prompt_arg: str) -> str:
    preset = _resolve_provider_preset(provider_id)
    base_cmd = str(preset.get("base_cmd") or "").strip()
    if not base_cmd:
        raise ValueError(f"provider `{provider_id}` has empty base command")
    prompt_env = '"$LEANATLAS_EVAL_PROMPT"'
    if prompt_transport == "stdin":
        return f"{base_cmd} - < {prompt_env}"
    if prompt_transport == "env_path":
        return f"{base_cmd} {prompt_env}"
    if prompt_transport == "arg":
        flag = prompt_arg.strip() or "--prompt-file"
        return f"{base_cmd} {flag} {prompt_env}"
    raise ValueError(f"Unknown prompt_transport `{prompt_transport}`")


def _normalize_env(env_obj: object) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if isinstance(env_obj, dict):
        for k, v in env_obj.items():
            if isinstance(k, str) and isinstance(v, str):
                out[k] = os.path.expandvars(v)
    return out


def _normalize_env_map(env_map_obj: object) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if isinstance(env_map_obj, dict):
        for src, dst in env_map_obj.items():
            if isinstance(src, str) and isinstance(dst, str) and src.strip() and dst.strip():
                out[src.strip()] = dst.strip()
    return out


def _normalize_capabilities(cap_obj: object) -> Dict[str, bool]:
    out: Dict[str, bool] = {}
    if not isinstance(cap_obj, dict):
        return out
    for key in ("supports_tool_calls", "supports_streaming", "supports_json_mode"):
        raw = cap_obj.get(key)
        if isinstance(raw, bool):
            out[key] = raw
    return out


def _resolve_from_profile(
    *,
    repo_root: Path,
    profile_path: Path,
    override_provider: str,
) -> ResolvedAgentInvocation:
    obj = _load_profile(profile_path, repo_root=repo_root)
    provider_id = str(obj.get("provider_id", "")).strip()
    if not provider_id:
        raise ValueError(f"Invalid provider_id in profile: {profile_path}")
    if override_provider and override_provider != provider_id:
        raise ValueError(
            f"--agent-provider `{override_provider}` mismatches profile provider_id `{provider_id}` in {profile_path}"
        )

    preset = DEFAULT_PROVIDER_PRESETS.get(provider_id)
    prompt_transport = str(
        obj.get("prompt_transport") or (preset.get("prompt_transport") if preset else "custom")
    ).strip()
    prompt_arg = str(obj.get("prompt_arg") or "").strip()
    cmd = str(obj.get("agent_cmd", "")).strip()
    if not cmd:
        if preset is None:
            known = ", ".join(sorted(DEFAULT_PROVIDER_PRESETS.keys()))
            raise ValueError(
                f"Unknown provider `{provider_id}` in profile {profile_path}; "
                f"set agent_cmd explicitly or use one of: {known}"
            )
        cmd = _build_default_command(
            provider_id=provider_id,
            prompt_transport=prompt_transport,
            prompt_arg=prompt_arg,
        )
    return ResolvedAgentInvocation(
        provider_id=provider_id,
        agent_cmd=cmd,
        source="cli.agent_profile",
        profile_path=str(profile_path),
        env=_normalize_env(obj.get("env")),
        env_map=_normalize_env_map(obj.get("env_map")),
        prompt_transport=prompt_transport,
        prompt_arg=prompt_arg,
        capabilities=_normalize_capabilities(obj.get("capabilities")),
    )


def _resolve_from_provider(provider_id: str) -> ResolvedAgentInvocation:
    preset = _resolve_provider_preset(provider_id)
    prompt_transport = str(preset.get("prompt_transport") or "stdin")
    cmd = _build_default_command(
        provider_id=provider_id,
        prompt_transport=prompt_transport,
        prompt_arg="",
    )
    return ResolvedAgentInvocation(
        provider_id=provider_id,
        agent_cmd=cmd,
        source="cli.agent_provider",
        profile_path=None,
        env={},
        env_map={},
        prompt_transport=prompt_transport,
        prompt_arg="",
        capabilities={},
    )


def _resolve_from_cmd(agent_cmd: str) -> ResolvedAgentInvocation:
    return ResolvedAgentInvocation(
        provider_id="legacy_cmd",
        agent_cmd=agent_cmd,
        source="cli.agent_cmd",
        profile_path=None,
        env={},
        env_map={},
        prompt_transport="custom",
        prompt_arg="",
        capabilities={},
    )


def resolve_agent_invocation(
    *,
    repo_root: Path,
    mode: str,
    agent_cmd: Optional[str],
    agent_provider: Optional[str],
    agent_profile: Optional[str],
) -> Optional[ResolvedAgentInvocation]:
    """Resolve final invocation.

    Precedence:
    1) explicit --agent-cmd
    2) --agent-profile
    3) --agent-provider
    """

    cmd_raw = (agent_cmd or "").strip()
    provider_raw = (agent_provider or "").strip()
    profile_raw = (agent_profile or "").strip()

    if cmd_raw and (provider_raw or profile_raw):
        raise ValueError("Do not combine --agent-cmd with --agent-provider/--agent-profile")

    if cmd_raw:
        return _resolve_from_cmd(cmd_raw)

    if profile_raw:
        p = Path(profile_raw).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"--agent-profile not found: {p}")
        return _resolve_from_profile(repo_root=repo_root, profile_path=p, override_provider=provider_raw)

    if provider_raw:
        return _resolve_from_provider(provider_raw)

    if mode == "run":
        raise ValueError("--mode run requires one of: --agent-cmd, --agent-profile, --agent-provider")
    return None


def apply_env_map(
    *,
    resolved: ResolvedAgentInvocation,
    env: Mapping[str, str],
) -> Dict[str, str]:
    """Apply resolver env-map + static env overlays onto a base environment."""
    return resolved.apply_env_map(dict(env))
