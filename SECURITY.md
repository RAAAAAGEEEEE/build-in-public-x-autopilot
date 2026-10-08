# Security policy

## Scope

This tool reads local conversation exports, sends their content to a text
generation backend, and can send drafts through a Telegram bot. The sensitive
elements are the Telegram bot token and chat id in `config.json`, and any
credential contained in your own conversation exports. See
[docs/PRIVACY_AND_SECURITY.md](docs/PRIVACY_AND_SECURITY.md).

## Reporting a vulnerability

Please do not post secrets or exploit details publicly. Open an issue at
https://github.com/RAAAAAGEEEEE/build-in-public-x-autopilot/issues titled
"Security: private contact requested", with no technical details, and the
maintainer will arrange a private channel. If GitHub's private vulnerability
reporting is enabled on the repository, you can use the "Security" tab instead.

This is a personal project in alpha: there is no formal response-time
commitment.

## If you leaked a token

Revoke the Telegram bot token with @BotFather (`/revoke`), issue a new one, and
update your local `config.json`.
