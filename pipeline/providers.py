"""The single place this pipeline talks to a model.

Project rule: any automatic text writing goes through the Claude Max
subscription that is paid for anyway.

There used to be a free-tier cascade here -- Cerebras, Mistral, OpenRouter,
Gemini, tried in order, first usable answer wins. It was removed on
07/08/2026. The reason is not cost: it is that a weaker model would answer,
nothing checked what it wrote, and the run still looked successful. Silent
degradation is worse than a clean failure, so this module now produces
either a subscription answer or an exception.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

# External wrapper script around the Claude CLI (authenticated with a
# subscription, never purchased API credits). It is NOT part of this
# repository; see docs/CONFIGURATION.md.
CLAUDE_CALL = Path("/opt/claude/tools/claude_call.sh")


class AllProvidersFailed(RuntimeError):
    """The subscription produced no usable answer.

    The name is kept from the cascade era because callers catch it by name
    across the pipeline, and renaming it would be churn for no gain. It
    carries every failure reason so the caller can alert with something
    actionable instead of 'it broke'.
    """

    def __init__(self, failures: list[str]):
        self.failures = failures
        super().__init__("no usable answer:\n  - " + "\n  - ".join(failures))


def _claude_subscription(prompt: str, model: str, timeout: int, log) -> str | None:
    """One call to the Claude Max subscription. None on any failure.

    Model ids are spelled out in full rather than passed as the `sonnet`
    alias: the CLI resolves bare aliases to whatever version IT considers
    current, which on 07/08/2026 was the previous generation, silently. The
    wrapper now translates aliases too, but being explicit here means this
    file does not depend on that.
    """
    if not CLAUDE_CALL.is_file():
        log(f"claude: {CLAUDE_CALL} not found")
        return None
    path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                         encoding="utf-8") as f:
            f.write(prompt)
            path = f.name
        proc = subprocess.run([str(CLAUDE_CALL), path, model, str(timeout)],
                              capture_output=True, text=True, timeout=timeout + 60)
        if proc.returncode != 0:
            log(f"claude: exit {proc.returncode}")
            return None
        text = (proc.stdout or "").strip()
        return text or None
    except Exception as exc:
        log(f"claude: {type(exc).__name__}: {exc}")
        return None
    finally:
        if path:
            Path(path).unlink(missing_ok=True)


def complete(prompt: str, keys: dict[str, str], *, max_tokens: int = 4000,
             temperature: float = 0.4, timeout: int = 90,
             prefer: str | None = None,
             claude_model: str = "claude-sonnet-5",
             log=lambda msg: None) -> tuple[str, str, dict]:
    """Run `prompt` through the subscription.

    Returns (text, model_name, usage). Raises AllProvidersFailed if the
    subscription gave nothing usable.

    claude_model picks which model answers. Writing work uses Sonnet; judging
    and verifying use `claude-opus-5`, because a text checked by the same
    model that wrote it gets rubber-stamped -- the reviewer has to be a
    DIFFERENT and stronger model for the check to mean anything.

    keys, max_tokens, temperature and prefer are accepted and ignored. They
    were the cascade's parameters and every call site still passes them;
    keeping the signature avoids touching four call sites for no behaviour
    change. Length is capped in the prompt, not here.
    """
    text = _claude_subscription(prompt, claude_model, timeout, log)
    if text:
        return text, f"claude/{claude_model}", {}
    raise AllProvidersFailed(["claude: subscription unavailable or unusable answer"])
