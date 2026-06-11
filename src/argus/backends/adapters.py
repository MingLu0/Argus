from __future__ import annotations

from dataclasses import dataclass

from argus.models import BackendInvocation


@dataclass(frozen=True)
class BackendAdapter:
    id: str
    binary: str

    def build_invocation(self, *, path: str, prompt: str) -> BackendInvocation:
        return BackendInvocation(backend_id=self.id, command=[path], input_text=prompt)


class ClaudeAdapter(BackendAdapter):
    def build_invocation(self, *, path: str, prompt: str) -> BackendInvocation:
        return BackendInvocation(backend_id=self.id, command=[path, "-p", prompt], input_text="")


class OpenCodeAdapter(BackendAdapter):
    def build_invocation(self, *, path: str, prompt: str) -> BackendInvocation:
        return BackendInvocation(
            backend_id=self.id,
            command=[path, "run", "--print", prompt],
            input_text="",
        )


class CodexAdapter(BackendAdapter):
    def build_invocation(self, *, path: str, prompt: str) -> BackendInvocation:
        return BackendInvocation(backend_id=self.id, command=[path, "exec", prompt], input_text="")


ADAPTERS: dict[str, BackendAdapter] = {
    "claude": ClaudeAdapter(id="claude", binary="claude"),
    "opencode": OpenCodeAdapter(id="opencode", binary="opencode"),
    "codex": CodexAdapter(id="codex", binary="codex"),
    "fake": BackendAdapter(id="fake", binary="fake-agent"),
    "fake-success": BackendAdapter(id="fake-success", binary="fake-agent"),
    "fake-delay": BackendAdapter(id="fake-delay", binary="fake-delay-agent"),
    "fake-timeout": BackendAdapter(id="fake-timeout", binary="fake-timeout-agent"),
    "fake-nonzero": BackendAdapter(id="fake-nonzero", binary="fake-nonzero-agent"),
    "fake-stderr": BackendAdapter(id="fake-stderr", binary="fake-stderr-agent"),
    "fake-missing": BackendAdapter(id="fake-missing", binary="fake-missing-agent"),
    "fake-postgres": BackendAdapter(id="fake-postgres", binary="fake-postgres-agent"),
    "fake-dynamodb": BackendAdapter(id="fake-dynamodb", binary="fake-dynamodb-agent"),
    "fake-high-risk": BackendAdapter(id="fake-high-risk", binary="fake-high-risk-agent"),
}


def adapter_for(backend_id: str) -> BackendAdapter:
    return ADAPTERS.get(backend_id, BackendAdapter(id=backend_id, binary=backend_id))
