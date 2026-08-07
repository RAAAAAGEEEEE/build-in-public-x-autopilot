"""LLM cascade: the paid Claude Max subscription first, free tiers as backup.

Project rule, restated 07/08/2026: any automatic text writing goes through
the Claude Max subscription that is paid for anyway. Third-party free tiers
stay acceptable *in second position*, as a fallback when the subscription is
unavailable -- which is exactly how they are wired below.

Every free-tier provider was tested against a real account, and the limits
are the ones the APIs actually reported, not the ones their marketing pages
claim. Where a documented limit turned out to be wrong, the comment says so.

The cascade tries the subscription, then each free provider in order, and
returns the first usable answer. A provider that is out of quota, rate
limited, or returns a truncated response is skipped rather than retried, so
one dead key never stalls a run.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

# Wrapper for the VPS Claude Max subscription (token in
# /root/.claude/cron_token.env, never purchased API credits). It lives in the
# landing repo because the blog editorial chain used it first.
CLAUDE_CALL = Path("/opt/claude/tools/claude_call.sh")


@dataclass
class Provider:
    """One free-tier endpoint.

    min_interval_s exists because some free tiers cap requests per MINUTE far
    below what a burst of drafts needs. Cerebras allows 5 requests/minute:
    without pacing, generating 3 drafts with retries is rejected halfway
    through. The cascade sleeps to respect it instead of failing.
    """

    name: str
    url: str
    model: str
    env_key: str
    # Reasoning models spend hidden "thinking" tokens that count against
    # max_tokens without appearing in completion_tokens. Ask one for a
    # 600-character post with a 220-token ceiling and you get 46 tokens of
    # real output, cut mid-sentence. Flagging them lets callers raise the
    # ceiling only where it is needed.
    reasoning: bool = False
    min_interval_s: float = 0.0
    notes: str = ""
    _last_call: float = field(default=0.0, repr=False)


# Ordered best-effort-first. Rationale for the order:
#   1. Cerebras has the largest daily token budget by a wide margin, but the
#      tightest per-minute cap -- ideal for a few high-value calls a day.
#   2. Mistral is a strong writer, especially in French, with a comfortable
#      per-minute budget.
#   3. OpenRouter's free pool includes very large models and is the widest
#      safety net.
#   4. Gemini has a generous token budget but a low daily request count.
PROVIDERS: tuple[Provider, ...] = (
    Provider(
        name="cerebras",
        url="https://api.cerebras.ai/v1/chat/completions",
        model="gemma-4-31b",
        env_key="CEREBRAS_API_KEY",
        reasoning=False,
        # Measured: 1,000,000 tokens/day, 2,400 requests/day,
        # 5 requests/minute, 30,000 tokens/minute.
        # 5 rpm is the binding constraint -- hence 13s spacing.
        min_interval_s=13.0,
        notes="Largest daily token budget. gemma-4-31b is the only "
              "non-reasoning model offered, so it is the one to write with; "
              "zai-glm-4.7 and gpt-oss-120b both spend reasoning tokens.",
    ),
    Provider(
        name="mistral",
        url="https://api.mistral.ai/v1/chat/completions",
        model="mistral-small-latest",
        env_key="MISTRAL_API_KEY",
        reasoning=False,
        # Measured from response headers: 50,000 tokens/minute,
        # 50 requests/minute.
        min_interval_s=0.0,
        notes="Strong writer, notably in French. Comfortable per-minute "
              "budget, so it absorbs bursts well.",
    ),
    Provider(
        name="openrouter",
        url="https://openrouter.ai/api/v1/chat/completions",
        model="nvidia/nemotron-3-ultra-550b-a55b:free",
        env_key="OPENROUTER_API_KEY",
        reasoning=False,
        min_interval_s=0.0,
        notes="17 models are free here. This 550B one has a 1M context "
              "window and answered correctly under test. Individual free "
              "models return 429 when their shared pool is busy, so treat "
              "any single one as best-effort.",
    ),
    Provider(
        name="gemini",
        url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        model="gemini-2.5-flash",
        env_key="GEMINI_API_KEY",
        reasoning=True,
        # Measured: 250 requests/day, 250,000 tokens/minute, 10 req/min.
        # The daily request count is the binding constraint, so this is a
        # judge/verifier rather than a writer.
        min_interval_s=6.0,
        notes="Reasoning model. Wasteful for writing prose, excellent for "
              "judging and verifying. 250 requests/day is the real limit.",
    ),
)

# Providers deliberately left out, with the reason -- so nobody wastes an
# afternoon rediscovering it:
#   groq      : returned HTTP 403 on a previously working key.
#   deepseek  : returned HTTP 402 Payment Required (free credits exhausted).
# Both are fine services; they simply cannot be relied on for a free tier
# that must not break.


class AllProvidersFailed(RuntimeError):
    """No provider produced a usable answer. Carries every failure reason so
    the caller can alert with something actionable instead of 'it broke'."""

    def __init__(self, failures: list[str]):
        self.failures = failures
        super().__init__("all providers failed:\n  - " + "\n  - ".join(failures))


def _post(provider: Provider, api_key: str, prompt: str, max_tokens: int,
          temperature: float, timeout: int) -> tuple[str, dict]:
    payload = json.dumps({
        "model": provider.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode("utf-8")
    request = urllib.request.Request(
        provider.url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Not optional. Cerebras sits behind Cloudflare and answers
            # 403 (error 1010) to requests without a browser-like
            # User-Agent, which reads exactly like an invalid key.
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read())

    choice = data["choices"][0]
    if choice.get("finish_reason") == "length":
        raise RuntimeError(
            f"answer truncated at the token ceiling (max_tokens={max_tokens}). "
            f"{'This is a reasoning model: raise the ceiling.' if provider.reasoning else ''}"
        )
    text = (choice.get("message") or {}).get("content") or ""
    if not text.strip():
        raise RuntimeError("empty answer")
    return text.strip(), data.get("usage") or {}


def _claude_subscription(prompt: str, model: str, timeout: int, log) -> str | None:
    """One call to the Claude Max subscription. None on any failure.

    Model ids are spelled out in full rather than passed as the `sonnet`
    alias: the CLI resolves bare aliases to whatever version IT considers
    current, which on 07/08/2026 was the previous generation, silently. The
    wrapper now translates aliases too, but being explicit here means this
    file does not depend on that.
    """
    if not CLAUDE_CALL.is_file():
        log(f"claude: {CLAUDE_CALL} not found, falling back to free tiers")
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
            log(f"claude: exit {proc.returncode}, falling back to free tiers")
            return None
        text = (proc.stdout or "").strip()
        return text or None
    except Exception as exc:
        log(f"claude: {type(exc).__name__}: {exc}, falling back to free tiers")
        return None
    finally:
        if path:
            Path(path).unlink(missing_ok=True)


def complete(prompt: str, keys: dict[str, str], *, max_tokens: int = 4000,
             temperature: float = 0.4, timeout: int = 90,
             prefer: str | None = None,
             claude_model: str = "claude-sonnet-5",
             log=lambda msg: None) -> tuple[str, str, dict]:
    """Run `prompt` through the cascade.

    Returns (text, provider_name, usage). Raises AllProvidersFailed if none
    answered, with every reason collected.

    max_tokens defaults high on purpose: a reasoning model's hidden thinking
    counts against it, and a truncated answer is worse than a slow one. Cap
    the *content* length in your prompt, not here.

    claude_model picks which subscription model answers. Writing work uses
    Sonnet; judging and verifying use `claude-opus-5`, because a text checked
    by the same model that wrote it gets rubber-stamped -- the reviewer has
    to be a DIFFERENT and stronger model for the check to mean anything.

    prefer names a free-tier provider to try first, and only matters once the
    subscription is unavailable and we are down in the fallback cascade.
    """
    failures: list[str] = []

    # The paid subscription first. Only if it yields nothing do we fall back
    # to the free tiers below -- that ordering IS the project rule, not a
    # performance preference.
    text = _claude_subscription(prompt, claude_model, timeout, log)
    if text:
        return text, f"claude/{claude_model}", {}
    failures.append("claude: subscription unavailable")

    order = list(PROVIDERS)
    if prefer:
        order.sort(key=lambda p: p.name != prefer)

    for provider in order:
        api_key = keys.get(provider.env_key, "")
        if not api_key:
            failures.append(f"{provider.name}: no key configured")
            continue

        wait = provider.min_interval_s - (time.monotonic() - provider._last_call)
        if provider._last_call and wait > 0:
            log(f"{provider.name}: pacing {wait:.1f}s to respect its per-minute cap")
            time.sleep(wait)

        try:
            provider._last_call = time.monotonic()
            text, usage = _post(provider, api_key, prompt, max_tokens,
                                temperature, timeout)
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", "ignore")[:160]
            except Exception:
                pass
            hint = {
                402: " (out of credits)",
                403: " (key rejected, or a missing User-Agent header)",
                429: " (rate limited or daily quota reached)",
            }.get(exc.code, "")
            failures.append(f"{provider.name}: HTTP {exc.code}{hint} {body}")
            log(f"{provider.name}: HTTP {exc.code}{hint}, trying the next one")
            continue
        except Exception as exc:
            failures.append(f"{provider.name}: {type(exc).__name__}: {exc}")
            log(f"{provider.name}: {type(exc).__name__}: {exc}, trying the next one")
            continue

        log(f"{provider.name} answered ({provider.model}), usage={usage}")
        return text, provider.name, usage

    raise AllProvidersFailed(failures)
