ONBOARDING — API key quick start

Note: The package import name is `dc_mar_sdk`. Use `import dc_mar_sdk` in your code. CLI entry points are `dc-mar-sdk-cli`, `dc-mar-sdk-release`, and `dc-mar-sdk-geocode-collect`.

This short guide helps first-time users obtain, set, and verify the DC MAR API key so the CLI and Python client work on first run.

1) How to obtain a key

- Request an API key from your DC data team or the project administrator. The key is a short opaque token (e.g. sk_... or a random string).
- Store it securely (password manager, OS keyring, or CI secrets).

2) How to set the key (copy-paste friendly)

Bash / macOS / Linux (recommended)

```bash
# set for current shell session
export DC_MAR_API_KEY="your_api_key_here"

# persist (example for bash ~/.bashrc or zsh ~/.zshrc)
echo 'export DC_MAR_API_KEY="your_api_key_here"' >> ~/.bashrc
# then reload: source ~/.bashrc
```

Fish shell

```fish
set -x DC_MAR_API_KEY "your_api_key_here"
# persist: set -Ux DC_MAR_API_KEY "your_api_key_here"
```

PowerShell (Windows)

```powershell
$env:DC_MAR_API_KEY = "your_api_key_here"
# persist: setx DC_MAR_API_KEY "your_api_key_here"
```

Windows CMD

```cmd
set DC_MAR_API_KEY=your_api_key_here
```

3) Env var vs CLI flag

- Environment variable (DC_MAR_API_KEY) — convenient for repeated use, CI, and scripting. Recommended for local development.
- CLI flag (--api-key or -k) — good for one-off runs or ephemeral keys. Example:

```bash
uv run dc-mar-sdk-cli analyze --query "1600 Pennsylvania" --api-key "your_api_key_here"
```

Notes:
- If both are provided, the CLI flag wins for that invocation (the code prefers the explicit option when given).
- Use environment variables in CI: set the repository or workflow secret DC_MAR_API_KEY and reference it as ${{ secrets.DC_MAR_API_KEY }}.

4) Quick verification commands (copy-paste)

Verify the env var is set (bash / zsh / sh):

```bash
echo "$DC_MAR_API_KEY"
```

PowerShell:

```powershell
echo $env:DC_MAR_API_KEY
```

Run a minimal CLI check (autocomplete)

```bash
# using env var
uv run dc-mar-sdk-cli autocomplete "1600 Pennsylvania"

# using flag
uv run dc-mar-sdk-cli autocomplete "1600 Pennsylvania" --api-key "$DC_MAR_API_KEY"
```

Raw API check with curl (shows HTTP status + response)

```bash
# URL-encode the query or use quoted path component
curl -sS -H "Accept: application/json" -H "apiKey: $DC_MAR_API_KEY" "https://datagate.dc.gov/mar/open/api/v2.2/autocomplete/1600%20Pennsylvania"
```

If you get JSON suggestions or HTTP 200 — key is valid.

5) Common mistakes & fixes

- Truncated key: copying from a wrapped email or chat may omit characters. Fix: copy from the original source, or paste into a temporary file to verify full length.
- Extra quotes/spaces: ensure no surrounding quotes or trailing spaces. Example wrong: export DC_MAR_API_KEY=' abc...' (leading space). Fix: remove quotes or use exact value.
- Wrong env var name: use DC_MAR_API_KEY (not DC_MAR_KEY, DC_MARAPIKEY, etc.).
- Not exported in current shell: if you set the var in ~/.bashrc, run `source ~/.bashrc` or open a new terminal.
- Using setx on Windows without reopening: after setx, start a new shell to inherit the value.
- Invalid key: API returns 401/403 or the CLI will raise network/auth errors. Contact your API admin to verify the token.

6) Troubleshooting checklist

- Is DC_MAR_API_KEY visible in this shell? `echo "$DC_MAR_API_KEY"`
- Does the CLI accept the key as a flag? `uv run dc-mar-sdk-cli autocomplete "1600 Pennsylvania" --api-key "$DC_MAR_API_KEY"`
- Inspect raw HTTP with curl to confirm header usage and server response status.
- If you see permission errors, confirm the key hasn't expired or been revoked with your admin.

7) Security tips

- Never commit keys to source control. Add patterns to .gitignore or use environment-specific configuration.
- Use CI secrets for automated runs; reference them as environment variables in workflow files.

If anything here is unclear or you need an example adapted to your shell or CI provider, open an issue or contact the maintainers.
