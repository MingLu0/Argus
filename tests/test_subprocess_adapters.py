from __future__ import annotations

from argus.backends.adapters import adapter_for


def test_claude_adapter_uses_print_mode() -> None:
    invocation = adapter_for("claude").build_invocation(path="/bin/claude", prompt="review this")

    assert invocation.command == ["/bin/claude", "-p", "review this"]
    assert invocation.input_text == ""


def test_opencode_adapter_uses_run_print_command() -> None:
    invocation = adapter_for("opencode").build_invocation(
        path="/bin/opencode", prompt="review this"
    )

    assert invocation.command == ["/bin/opencode", "run", "--print", "review this"]
    assert invocation.input_text == ""


def test_codex_adapter_uses_exec_command() -> None:
    invocation = adapter_for("codex").build_invocation(path="/bin/codex", prompt="review this")

    assert invocation.command == ["/bin/codex", "exec", "review this"]
    assert invocation.input_text == ""


def test_fake_adapter_reads_prompt_from_stdin() -> None:
    invocation = adapter_for("fake-success").build_invocation(
        path="/bin/fake", prompt="review this"
    )

    assert invocation.command == ["/bin/fake"]
    assert invocation.input_text == "review this"
