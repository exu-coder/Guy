#!/usr/bin/env python3
import asyncio
import base64
import io
import json
import os
import re
import time
import logging
import sys
from datetime import datetime, timezone
from urllib.parse import quote

import httpx
from dotenv import load_dotenv
from telegram import BotCommand, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (Application, CommandHandler, ContextTypes, CallbackQueryHandler)

# ============================================================================
# 𝐋𝐨𝐠𝐠𝐢𝐧𝐠 𝐂𝐨𝐧𝐟𝐢𝐠𝐮𝐫𝐚𝐭𝐢𝐨𝐧
# ============================================================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================================
# 𝐋𝐨𝐚𝐝 𝐄𝐧𝐯𝐢𝐫𝐨𝐧𝐦𝐞𝐧𝐭
# ============================================================================
load_dotenv()

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GH_TOKEN = os.getenv("GITHUB_TOKEN")

if not TG_TOKEN:
    logger.error("❌ 𝐓𝐄𝐋𝐄𝐆𝐑𝐀𝐌_𝐁𝐎𝐓_𝐓𝐎𝐊𝐄𝐍 𝐧𝐨𝐭 𝐬𝐞𝐭!")
    sys.exit(1)

logger.info(f"✅ 𝐁𝐨𝐭 𝐭𝐨𝐤𝐞𝐧 𝐥𝐨𝐚𝐝𝐞𝐝: {TG_TOKEN[:10]}...")

API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "gh-scraper-tgbot",
    "X-GitHub-Api-Version": "2022-11-28",
}
if GH_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GH_TOKEN}"
    logger.info("✅ 𝐆𝐢𝐭𝐇𝐮𝐛 𝐭𝐨𝐤𝐞𝐧 𝐥𝐨𝐚𝐝𝐞𝐝")
else:
    logger.warning("⚠️ 𝐍𝐨 𝐆𝐢𝐭𝐇𝐮𝐛 𝐭𝐨𝐤𝐞𝐧 - 𝐫𝐚𝐭𝐞 𝐥𝐢𝐦𝐢𝐭 𝐰𝐢𝐥𝐥 𝐛𝐞 𝐯𝐞𝐫𝐲 𝐥𝐨𝐰")

# 𝐒𝐭𝐨𝐫𝐞 𝐮𝐬𝐞𝐫 𝐭𝐚𝐫𝐠𝐞𝐭𝐬
user_targets = {}

# ---------------------------------------------------------------------------
# 𝐏𝐚𝐭𝐭𝐞𝐫𝐧𝐬: 𝐞𝐧𝐯 𝐟𝐢𝐥𝐞𝐬 + 𝐀𝐏𝐈 𝐜𝐫𝐞𝐝𝐞𝐧𝐭𝐢𝐚𝐥𝐬 / 𝐀𝐈 𝐭𝐨𝐤𝐞𝐧𝐬
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

ENV_SEARCH_QUERIES = [
    "filename:.env", "filename:.env.local", "filename:.env.production",
    "filename:credentials.json", "filename:serviceAccountKey.json",
    "filename:.npmrc", "path:.aws filename:credentials",
]

SECRET_PATTERNS = {
    "OpenAI Key":          re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}T3BlbkFJ[A-Za-z0-9_-]{20,}"),
    "OpenAI (legacy)":     re.compile(r"\bsk-[A-Za-z0-9]{48}\b"),
    "Anthropic Key":       re.compile(r"sk-ant-(?:api)?[0-9A-Za-z_-]{20,}"),
    "Google AI/Gemini":    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    "Google Service Acct": re.compile(r'"type":\s*"service_account"'),
    "HuggingFace Token":   re.compile(r"\bhf_[A-Za-z0-9]{34,}\b"),
    "Groq API Key":        re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b"),
    "Replicate Token":     re.compile(r"\br8_[A-Za-z0-9]{36,}\b"),
    "xAI/Grok Key":        re.compile(r"\bxai-[A-Za-z0-9]{40,}\b"),
    "Perplexity Key":      re.compile(r"\bpplx-[A-Za-z0-9]{40,}\b"),
    "OpenRouter Key":      re.compile(r"\bsk-or-v1-[0-9a-f]{64}\b"),
    "DeepSeek Key":        re.compile(r"\bsk-(?:ds|deepseek)-[0-9a-zA-Z]{20,}\b"),
    "Mistral Key":         re.compile(r"\b(?:mistral|ms)-[0-9a-zA-Z]{32}\b"),
    "Together AI Key":     re.compile(r"\b[0-9a-f]{64}\b(?=.*together)"),
    "Cohere Token":        re.compile(r"\b[0-9a-f]{40}\b(?=.*cohere)"),
    "Stability AI Key":    re.compile(r"\bsk-[A-Za-z0-9]{48}(?=.*stability)"),
    "AWS Access Key":      re.compile(r"\b(?:A3T[A-Z0-9]|AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}\b"),
    "AWS Secret (ctx)":    re.compile(r"(?i)aws.{0,20}['\"][0-9a-zA-Z/+=]{40}['\"]"),
    "Azure Storage Key":   re.compile(r"(?i)AccountKey=[A-Za-z0-9/+=]{88}"),
    "DigitalOcean Token":  re.compile(r"\bdop_v1_[0-9a-f]{64}\b"),
    "Stripe Key":          re.compile(r"\b[sr]k_live_[0-9a-zA-Z]{24,}\b"),
    "Twilio API Key":      re.compile(r"\bSK[0-9a-fA-F]{32}\b"),
    "Twilio SID":          re.compile(r"\bAC[a-zA-Z0-9]{32}\b"),
    "SendGrid Key":        re.compile(r"\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}\b"),
    "Mailgun Key":         re.compile(r"\bkey-[0-9a-zA-Z]{32}\b"),
    "Slack Token":         re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "Slack Webhook":       re.compile(r"https://hooks\.slack\.com/services/T[A-Za-z0-9_]+/B[A-Za-z0-9_]+/[A-Za-z0-9]+"),
    "Telegram Bot Token":  re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_-]{33}\b"),
    "Discord Bot Token":   re.compile(r"\b[\w-]{24}\.[\w-]{6}\.[\w-]{27}\b"),
    "GitHub Token":        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "GitLab Token":        re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    "NPM Token":           re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"),
    "PyPI Token":          re.compile(r"pypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]+"),
    "Shopify Token":       re.compile(r"\bshp(?:at|ca|pa)_[0-9a-fA-F]{32}\b"),
    "Heroku API Key":      re.compile(r"(?i)heroku.{0,25}[0-9a-f-]{36}"),
    "JWT":                 re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\b"),
    "Private Key":         re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    "Database URL":        re.compile(r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^\s'\"<>]{8,}"),
    "Generic Secret":      re.compile(r"(?i)(?:api[_-]?key|secret|token|passwd|password)\s*[:=]\s*['\"][A-Za-z0-9_\-/.+=]{8,}['\"]"),
}

MAX_FILE_BYTES = 200_000
JUICY_FILE_RE = re.compile(
    r"(?i)(env|secret|credential|key|token|config|settings|\.pem|\.p12|\.db|\.sql|dump|backup)"
)


# ---------------------------------------------------------------------------
# 𝐆𝐢𝐭𝐇𝐮𝐛 𝐀𝐏𝐈 𝐡𝐞𝐥𝐩𝐞𝐫𝐬
# ---------------------------------------------------------------------------
async def gh_get(client: httpx.AsyncClient, url: str, params: dict = None):
    """𝐆𝐄𝐓 𝐰𝐢𝐭𝐡 𝐫𝐚𝐭𝐞-𝐥𝐢𝐦𝐢𝐭 𝐡𝐚𝐧𝐝𝐥𝐢𝐧𝐠."""
    while True:
        try:
            r = await client.get(url, params=params)
            if r.headers.get("X-RateLimit-Remaining") == "0":
                reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait = max(reset - time.time(), 1)
                logger.warning(f"⏳ 𝐑𝐚𝐭𝐞 𝐥𝐢𝐦𝐢𝐭, 𝐬𝐥𝐞𝐞𝐩𝐢𝐧𝐠 {wait:.0f}𝐬")
                await asyncio.sleep(min(wait, 300))
                continue
            if r.status_code == 403 and "secondary rate limit" in r.text.lower():
                logger.warning("⏳ 𝐒𝐞𝐜𝐨𝐧𝐝𝐚𝐫𝐲 𝐫𝐚𝐭𝐞 𝐥𝐢𝐦𝐢𝐭, 𝐬𝐥𝐞𝐞𝐩𝐢𝐧𝐠 60𝐬")
                await asyncio.sleep(60)
                continue
            return r
        except Exception as e:
            logger.error(f"❌ 𝐆𝐢𝐭𝐇𝐮𝐛 𝐀𝐏𝐈 𝐞𝐫𝐫𝐨𝐫: {e}")
            await asyncio.sleep(5)
            continue


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
# 𝐒𝐜𝐚𝐧 𝐥𝐨𝐠𝐢𝐜
# ---------------------------------------------------------------------------
def scan_text(text: str):
    hits = []
    for name, pat in SECRET_PATTERNS.items():
        for m in pat.finditer(text):
            snippet = text[max(0, m.start() - 25):m.end() + 25].replace("\n", " ").strip()
            hits.append((name, snippet))
    return hits


def redact(snippet: str) -> str:
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


async def fetch_file(client, repo_full_name: str, path: str, ref: str):
    try:
        r = await gh_get(client, f"/repos/{repo_full_name}/contents/{quote(path)}",
                         {"ref": ref})
        if r.status_code != 200:
            return None
        data = r.json()
        if isinstance(data, dict) and data.get("content"):
            return base64.b64decode(data["content"]).decode("utf-8", "ignore")[:MAX_FILE_BYTES]
    except Exception as e:
        logger.error(f"❌ 𝐅𝐞𝐭𝐜𝐡 𝐟𝐢𝐥𝐞 𝐞𝐫𝐫𝐨𝐫: {e}")
    return None


async def hunt_env_files(client, target, repos):
    results = []
    seen = set()

    if GH_TOKEN:
        for q in ENV_SEARCH_QUERIES:
            try:
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
                    results.append({
                        "repo": key[0], "path": key[1],
                        "url": f"https://github.com/{key[0]}/blob/HEAD/{quote(key[1])}",
                        "hits": scan_text(content),
                    })
            except Exception as e:
                logger.error(f"❌ 𝐒𝐞𝐚𝐫𝐜𝐡 𝐞𝐫𝐫𝐨𝐫: {e}")

    for repo in repos:
        ref = repo.get("default_branch", "main")
        for fname in ENV_FILENAMES:
            key = (repo["full_name"], fname)
            if key in seen:
                continue
            content = await fetch_file(client, repo["full_name"], fname, ref)
            if content is None:
                continue
            seen.add(key)
            results.append({
                "repo": key[0], "path": fname,
                "url": f"https://github.com/{key[0]}/blob/{ref}/{quote(fname)}",
                "hits": scan_text(content),
            })
    return results


async def scan_repo_contents(client, repos, max_files_per_repo=15):
    findings = []
    for repo in repos:
        ref = repo.get("default_branch", "HEAD")
        r = await gh_get(client, f"/repos/{repo['full_name']}/git/trees/{ref}?recursive=1")
        if r.status_code != 200:
            continue
        tree = r.json().get("tree", [])
        scored = sorted(tree, key=lambda e: (
            0 if JUICY_FILE_RE.search(e.get("path", "")) else 1
        ))
        count = 0
        for entry in scored:
            if count >= max_files_per_repo:
                break
            if entry.get("type") != "blob" or entry.get("size", 0) > MAX_FILE_BYTES:
                continue
            content = await fetch_file(client, repo["full_name"], entry["path"], ref)
            if content is None:
                continue
            hits = scan_text(content)
            if hits:
                findings.append({
                    "repo": repo["full_name"], "path": entry["path"],
                    "url": f"https://github.com/{repo['full_name']}/blob/{ref}/{quote(entry['path'])}",
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
                if name and email and "noreply" not in email:
                    emails.setdefault(email, {"name": name, "repos": set()})
                    emails[email]["repos"].add(repo["full_name"])
    return emails


# ---------------------------------------------------------------------------
# 𝐅𝐨𝐫𝐦𝐚𝐭𝐭𝐢𝐧𝐠
# ---------------------------------------------------------------------------
def fmt_env_results(results):
    if not results:
        return "✅ 𝐍𝐨 𝐞𝐱𝐩𝐨𝐬𝐞𝐝 𝐞𝐧𝐯/𝐜𝐨𝐧𝐟𝐢𝐠 𝐟𝐢𝐥𝐞𝐬 𝐟𝐨𝐮𝐧𝐝."
    lines = [f"🚨 𝐅𝐨𝐮𝐧𝐝 {len(results)} 𝐞𝐱𝐩𝐨𝐬𝐞𝐝 𝐞𝐧𝐯/𝐜𝐨𝐧𝐟𝐢𝐠 𝐟𝐢𝐥𝐞(𝐬):\n"]
    for r in results[:15]:
        lines.append(f"📄 {r['repo']}/{r['path']}")
        lines.append(f"   {r['url']}")
        for name, snip in r["hits"][:6]:
            lines.append(f"   🔑 [{name}] {redact(snip)}")
        lines.append("")
    if len(results) > 15:
        lines.append(f"...𝐚𝐧𝐝 {len(results) - 15} 𝐦𝐨𝐫𝐞 (𝐬𝐞𝐞 /𝐫𝐞𝐩𝐨𝐫𝐭).")
    return "\n".join(lines)


def fmt_findings(findings, title):
    if not findings:
        return f"✅ 𝐍𝐨 𝐞𝐱𝐩𝐨𝐬𝐞𝐝 𝐬𝐞𝐜𝐫𝐞𝐭𝐬 𝐟𝐨𝐮𝐧𝐝 ({title})."
    total = sum(len(f["hits"]) for f in findings)
    lines = [f"🚨 {title}: {total} 𝐩𝐨𝐭𝐞𝐧𝐭𝐢𝐚𝐥 𝐬𝐞𝐜𝐫𝐞𝐭(𝐬) 𝐢𝐧 {len(findings)} 𝐟𝐢𝐥𝐞(𝐬):\n"]
    for f in findings[:15]:
        lines.append(f"📄 {f['repo']}/{f['path']}")
        for name, snip in f["hits"][:5]:
            lines.append(f"   🔑 [{name}] {redact(snip)}")
        lines.append(f"   {f['url']}\n")
    if len(findings) > 15:
        lines.append(f"...𝐚𝐧𝐝 {len(findings) - 15} 𝐦𝐨𝐫𝐞 𝐟𝐢𝐥𝐞𝐬 (𝐬𝐞𝐞 /𝐫𝐞𝐩𝐨𝐫𝐭).")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 𝐈𝐧𝐥𝐢𝐧𝐞 𝐊𝐞𝐲𝐛𝐨𝐚𝐫𝐝 𝐌𝐞𝐧𝐮𝐬
# ---------------------------------------------------------------------------
def get_main_menu():
    keyboard = [
        [
            InlineKeyboardButton("📊 𝐒𝐜𝐫𝐚𝐩𝐞 𝐏𝐫𝐨𝐟𝐢𝐥𝐞", callback_data="scrape"),
            InlineKeyboardButton("📧 𝐇𝐚𝐫𝐯𝐞𝐬𝐭 𝐄𝐦𝐚𝐢𝐥𝐬", callback_data="emails"),
        ],
        [
            InlineKeyboardButton("🔍 𝐅𝐢𝐧𝐝 .𝐞𝐧𝐯 𝐅𝐢𝐥𝐞𝐬", callback_data="env"),
            InlineKeyboardButton("🔑 𝐒𝐜𝐚𝐧 𝐟𝐨𝐫 𝐊𝐞𝐲𝐬", callback_data="keys"),
        ],
        [
            InlineKeyboardButton("📋 𝐅𝐮𝐥𝐥 𝐑𝐞𝐩𝐨𝐫𝐭", callback_data="report"),
            InlineKeyboardButton("❓ 𝐇𝐞𝐥𝐩", callback_data="help"),
        ],
        [
            InlineKeyboardButton("🔄 𝐂𝐥𝐞𝐚𝐫 𝐓𝐚𝐫𝐠𝐞𝐭", callback_data="clear_target"),
            InlineKeyboardButton("📝 𝐒𝐞𝐭 𝐓𝐚𝐫𝐠𝐞𝐭", callback_data="set_target"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_target_menu():
    keyboard = [
        [InlineKeyboardButton("ℹ️ 𝐄𝐧𝐭𝐞𝐫 𝐮𝐬𝐞𝐫𝐧𝐚𝐦𝐞 𝐨𝐫 𝐨𝐫𝐠𝐚𝐧𝐢𝐳𝐚𝐭𝐢𝐨𝐧", callback_data="noop")],
        [InlineKeyboardButton("🔙 𝐁𝐚𝐜𝐤 𝐭𝐨 𝐌𝐚𝐢𝐧 𝐌𝐞𝐧𝐮", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_after_scan_menu():
    keyboard = [
        [
            InlineKeyboardButton("🔄 𝐍𝐞𝐰 𝐒𝐜𝐚𝐧", callback_data="main_menu"),
            InlineKeyboardButton("📊 𝐌𝐚𝐢𝐧 𝐌𝐞𝐧𝐮", callback_data="main_menu"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# ---------------------------------------------------------------------------
# 𝐓𝐞𝐥𝐞𝐠𝐫𝐚𝐦 𝐡𝐚𝐧𝐝𝐥𝐞𝐫𝐬
# ---------------------------------------------------------------------------
async def send_long(update: Update, text: str, reply_markup=None):
    for i in range(0, len(text), 4000):
        if i == 0:
            await update.message.reply_text(text[i:i + 4000], reply_markup=reply_markup, parse_mode='HTML')
        else:
            await update.message.reply_text(text[i:i + 4000], parse_mode='HTML')


async def send_long_callback(query, text: str, reply_markup=None):
    for i in range(0, len(text), 4000):
        if i == 0:
            await query.message.reply_text(text[i:i + 4000], reply_markup=reply_markup, parse_mode='HTML')
        else:
            await query.message.reply_text(text[i:i + 4000], parse_mode='HTML')


async def resolve_target(client, target):
    profile = await get_profile(client, target)
    if not profile:
        return None, False
    return profile, profile.get("type") == "Organization"


async def start_or_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    logger.info(f"📩 /start 𝐟𝐫𝐨𝐦 {update.effective_user.id}")
    welcome_text = (
        "🤖 **𝐆𝐢𝐭𝐇𝐮𝐛 𝐒𝐜𝐫𝐚𝐩𝐞𝐫 𝐁𝐨𝐭**\n\n"
        "𝐈 𝐜𝐚𝐧 𝐡𝐞𝐥𝐩 𝐲𝐨𝐮 𝐠𝐚𝐭𝐡𝐞𝐫 𝐎𝐒𝐈𝐍𝐓 𝐢𝐧𝐟𝐨𝐫𝐦𝐚𝐭𝐢𝐨𝐧 𝐟𝐫𝐨𝐦 𝐆𝐢𝐭𝐇𝐮𝐛.\n\n"
        "**𝐇𝐨𝐰 𝐭𝐨 𝐮𝐬𝐞:**\n"
        "1️⃣ 𝐂𝐥𝐢𝐜𝐤 \"𝐒𝐞𝐭 𝐓𝐚𝐫𝐠𝐞𝐭\" 𝐚𝐧𝐝 𝐞𝐧𝐭𝐞𝐫 𝐚 𝐆𝐢𝐭𝐇𝐮𝐛 𝐮𝐬𝐞𝐫𝐧𝐚𝐦𝐞\n"
        "2️⃣ 𝐓𝐡𝐞𝐧 𝐮𝐬𝐞 𝐚𝐧𝐲 𝐛𝐮𝐭𝐭𝐨𝐧 𝐛𝐞𝐥𝐨𝐰\n\n"
        "**𝐅𝐞𝐚𝐭𝐮𝐫𝐞𝐬:**\n"
        "• 📊 𝐏𝐫𝐨𝐟𝐢𝐥𝐞 & 𝐫𝐞𝐩𝐨𝐬𝐢𝐭𝐨𝐫𝐲 𝐞𝐧𝐮𝐦𝐞𝐫𝐚𝐭𝐢𝐨𝐧\n"
        "• 📧 𝐄𝐦𝐚𝐢𝐥 𝐡𝐚𝐫𝐯𝐞𝐬𝐭𝐢𝐧𝐠\n"
        "• 🔍 .𝐄𝐧𝐯 𝐟𝐢𝐥𝐞 𝐝𝐞𝐭𝐞𝐜𝐭𝐢𝐨𝐧\n"
        "• 🔑 𝐀𝐏𝐈 𝐤𝐞𝐲 & 𝐭𝐨𝐤𝐞𝐧 𝐬𝐜𝐚𝐧𝐧𝐢𝐧𝐠\n"
        "• 📋 𝐅𝐮𝐥𝐥 𝐉𝐒𝐎𝐍 𝐫𝐞𝐩𝐨𝐫𝐭"
    )
    
    user_id = update.effective_user.id
    current_target = user_targets.get(user_id, "𝐍𝐨𝐭 𝐬𝐞𝐭")
    
    await update.message.reply_text(
        welcome_text + f"\n\n💡 **𝐂𝐮𝐫𝐫𝐞𝐧𝐭 𝐭𝐚𝐫𝐠𝐞𝐭:** {current_target}",
        reply_markup=get_main_menu(),
        parse_mode='HTML'
    )


async def set_target(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text(
            "𝐏𝐥𝐞𝐚𝐬𝐞 𝐬𝐩𝐞𝐜𝐢𝐟𝐲 𝐚 𝐭𝐚𝐫𝐠𝐞𝐭:\n"
            "`/𝐭𝐚𝐫𝐠𝐞𝐭 <𝐮𝐬𝐞𝐫𝐧𝐚𝐦𝐞_𝐨𝐫_𝐨𝐫𝐠>`\n\n"
            "𝐄𝐱𝐚𝐦𝐩𝐥𝐞: `/𝐭𝐚𝐫𝐠𝐞𝐭 𝐦𝐢𝐜𝐫𝐨𝐬𝐨𝐟𝐭`",
            parse_mode='HTML'
        )
        return
    
    target = ctx.args[0]
    user_id = update.effective_user.id
    user_targets[user_id] = target
    
    await update.message.reply_text(
        f"✅ **𝐓𝐚𝐫𝐠𝐞𝐭 𝐬𝐞𝐭 𝐭𝐨:** `{target}`\n\n"
        "𝐘𝐨𝐮 𝐜𝐚𝐧 𝐧𝐨𝐰 𝐮𝐬𝐞 𝐭𝐡𝐞 𝐛𝐮𝐭𝐭𝐨𝐧𝐬 𝐛𝐞𝐥𝐨𝐰.",
        reply_markup=get_main_menu(),
        parse_mode='HTML'
    )


async def clear_target(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_targets:
        del user_targets[user_id]
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            "🔄 **𝐓𝐚𝐫𝐠𝐞𝐭 𝐜𝐥𝐞𝐚𝐫𝐞𝐝!**",
            reply_markup=get_main_menu(),
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            "🔄 **𝐓𝐚𝐫𝐠𝐞𝐭 𝐜𝐥𝐞𝐚𝐫𝐞𝐝!**",
            reply_markup=get_main_menu(),
            parse_mode='HTML'
        )


async def perform_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE, scan_type: str):
    user_id = update.effective_user.id
    target = user_targets.get(user_id)
    
    if not target:
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(
                "⚠️ **𝐍𝐨 𝐭𝐚𝐫𝐠𝐞𝐭 𝐬𝐞𝐭!**\n\n"
                "𝐏𝐥𝐞𝐚𝐬𝐞 𝐬𝐞𝐭 𝐚 𝐭𝐚𝐫𝐠𝐞𝐭 𝐟𝐢𝐫𝐬𝐭:\n"
                "`/𝐭𝐚𝐫𝐠𝐞𝐭 <𝐮𝐬𝐞𝐫𝐧𝐚𝐦𝐞>`",
                reply_markup=get_main_menu(),
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                "⚠️ **𝐍𝐨 𝐭𝐚𝐫𝐠𝐞𝐭 𝐬𝐞𝐭!**\n\n"
                "𝐏𝐥𝐞𝐚𝐬𝐞 𝐬𝐞𝐭 𝐚 𝐭𝐚𝐫𝐠𝐞𝐭 𝐟𝐢𝐫𝐬𝐭:\n"
                "`/𝐭𝐚𝐫𝐠𝐞𝐭 <𝐮𝐬𝐞𝐫𝐧𝐚𝐦𝐞>`",
                reply_markup=get_main_menu(),
                parse_mode='HTML'
            )
        return
    
    if update.callback_query:
        await update.callback_query.answer()
        query = update.callback_query
    else:
        query = None
    
    msg = await (query.message.reply_text if query else update.message.reply_text)(
        f"🔎 **𝐒𝐜𝐚𝐧𝐧𝐢𝐧𝐠 `{target}`...**\n"
        f"𝐓𝐡𝐢𝐬 𝐦𝐚𝐲 𝐭𝐚𝐤𝐞 𝐚 𝐟𝐞𝐰 𝐦𝐨𝐦𝐞𝐧𝐭𝐬.",
        parse_mode='HTML'
    )
    
    try:
        async with mk_client() as client:
            profile, is_org = await resolve_target(client, target)
            if not profile:
                await msg.edit_text(
                    f"❌ **𝐄𝐫𝐫𝐨𝐫:** '{target}' 𝐧𝐨𝐭 𝐟𝐨𝐮𝐧𝐝.",
                    reply_markup=get_main_menu()
                )
                return
            
            repos = await list_repos(client, target, is_org)
            
            if scan_type == "scrape":
                lines = [f"👤 {profile.get('login')} ({profile.get('type')})",
                         f"𝐍𝐚𝐦𝐞: {profile.get('name', '—')}",
                         f"𝐋𝐨𝐜𝐚𝐭𝐢𝐨𝐧: {profile.get('location', '—')}",
                         f"𝐄𝐦𝐚𝐢𝐥: {profile.get('email', '—')}",
                         f"𝐁𝐥𝐨𝐠: {profile.get('blog', '—')}",
                         f"𝐁𝐢𝐨: {profile.get('bio', '—')}",
                         f"𝐏𝐮𝐛𝐥𝐢𝐜 𝐫𝐞𝐩𝐨𝐬: {profile.get('public_repos')}",
                         f"𝐂𝐫𝐞𝐚𝐭𝐞𝐝: {str(profile.get('created_at', ''))[:10]}\n",
                         f"📦 **𝐋𝐚𝐭𝐞𝐬𝐭 𝐫𝐞𝐩𝐨𝐬 ({len(repos)}):**"]
                for repo in repos[:25]:
                    lines.append(f"  • {repo['full_name']} ⭐{repo['stargazers_count']} "
                                 f"[{repo.get('language')}]")
                await send_long_callback(query, "\n".join(lines), get_after_scan_menu())
                
            elif scan_type == "emails":
                emails = await harvest_emails(client, repos)
                if not emails:
                    await msg.edit_text(
                        "✅ **𝐍𝐨 𝐜𝐨𝐦𝐦𝐢𝐭 𝐞𝐦𝐚𝐢𝐥𝐬 𝐟𝐨𝐮𝐧𝐝.**",
                        reply_markup=get_after_scan_menu()
                    )
                    return
                lines = [f"📧 **{len(emails)} 𝐞𝐦𝐚𝐢𝐥(𝐬) 𝐟𝐨𝐮𝐧𝐝:**\n"]
                for email, info in list(emails.items())[:50]:
                    lines.append(f"  {info['name']} <{email}>")
                    lines.append(f"    ↳ {', '.join(sorted(info['repos']))[:80]}")
                await send_long_callback(query, "\n".join(lines), get_after_scan_menu())
                
            elif scan_type == "env":
                await msg.edit_text(f"🔍 **𝐇𝐮𝐧𝐭𝐢𝐧𝐠 .𝐞𝐧𝐯 𝐟𝐢𝐥𝐞𝐬...**")
                results = await hunt_env_files(client, target, repos)
                await send_long_callback(query, fmt_env_results(results), get_after_scan_menu())
                
            elif scan_type == "keys":
                await msg.edit_text(f"🔑 **𝐒𝐜𝐚𝐧𝐧𝐢𝐧𝐠 𝐟𝐨𝐫 𝐀𝐏𝐈 𝐤𝐞𝐲𝐬...**")
                findings = await scan_repo_contents(client, repos)
                await send_long_callback(query, fmt_findings(findings, "𝐒𝐞𝐜𝐫𝐞𝐭 𝐬𝐜𝐚𝐧"), get_after_scan_menu())
                
            elif scan_type == "report":
                await msg.edit_text(f"🧪 **𝐅𝐮𝐥𝐥 𝐬𝐜𝐚𝐧...**")
                env_results = await hunt_env_files(client, target, repos)
                findings = await scan_repo_contents(client, repos)
                emails = await harvest_emails(client, repos)

                report = {
                    "target": target,
                    "scanned_at": datetime.now(timezone.utc).isoformat(),
                    "profile": profile,
                    "repo_count": len(repos),
                    "env_files": [
                        {"repo": r["repo"], "path": r["path"], "url": r["url"], "hits": r["hits"]}
                        for r in env_results
                    ],
                    "secret_findings": [
                        {"repo": f["repo"], "path": f["path"], "url": f["url"], "hits": f["hits"]}
                        for f in findings
                    ],
                    "emails": {
                        e: {"name": i["name"], "repos": sorted(i["repos"])}
                        for e, i in emails.items()
                    },
                }
                buf = io.BytesIO(json.dumps(report, indent=2, default=str).encode())
                buf.name = f"github_scan_{target}.json"
                await query.message.reply_document(
                    buf, filename=buf.name, caption=f"📋 **𝐑𝐞𝐩𝐨𝐫𝐭: {target}**",
                    reply_markup=get_after_scan_menu(),
                    parse_mode='HTML'
                )
                await msg.delete()
                
    except Exception as e:
        logger.error(f"❌ 𝐒𝐜𝐚𝐧 𝐞𝐫𝐫𝐨𝐫: {e}")
        await msg.edit_text(
            f"❌ **𝐄𝐫𝐫𝐨𝐫:** {str(e)[:200]}",
            reply_markup=get_main_menu()
        )


# ---------------------------------------------------------------------------
# 𝐂𝐚𝐥𝐥𝐛𝐚𝐜𝐤 𝐡𝐚𝐧𝐝𝐥𝐞𝐫
# ---------------------------------------------------------------------------
async def button_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "main_menu":
        await query.answer()
        user_id = update.effective_user.id
        current_target = user_targets.get(user_id, "𝐍𝐨𝐭 𝐬𝐞𝐭")
        await query.message.edit_text(
            f"🤖 **𝐆𝐢𝐭𝐇𝐮𝐛 𝐒𝐜𝐫𝐚𝐩𝐞𝐫 𝐁𝐨𝐭**\n\n"
            f"💡 **𝐓𝐚𝐫𝐠𝐞𝐭:** {current_target}",
            reply_markup=get_main_menu(),
            parse_mode='HTML'
        )
    
    elif data == "set_target":
        await query.answer()
        await query.message.reply_text(
            "📝 **𝐒𝐞𝐭 𝐭𝐚𝐫𝐠𝐞𝐭:**\n"
            "`/𝐭𝐚𝐫𝐠𝐞𝐭 <𝐮𝐬𝐞𝐫𝐧𝐚𝐦𝐞>`\n\n"
            "𝐄𝐱𝐚𝐦𝐩𝐥𝐞: `/𝐭𝐚𝐫𝐠𝐞𝐭 𝐠𝐨𝐨𝐠𝐥𝐞`",
            reply_markup=get_main_menu(),
            parse_mode='HTML'
        )
    
    elif data == "clear_target":
        await clear_target(update, ctx)
    
    elif data == "help":
        await query.answer()
        await query.message.reply_text(
            "❓ **𝐇𝐞𝐥𝐩**\n\n"
            "**𝐂𝐨𝐦𝐦𝐚𝐧𝐝𝐬:**\n"
            "• /𝐬𝐭𝐚𝐫𝐭 - 𝐌𝐚𝐢𝐧 𝐦𝐞𝐧𝐮\n"
            "• /𝐭𝐚𝐫𝐠𝐞𝐭 <𝐮> - 𝐒𝐞𝐭 𝐭𝐚𝐫𝐠𝐞𝐭\n\n"
            "**𝐒𝐜𝐚𝐧𝐬:**\n"
            "• 📊 𝐒𝐜𝐫𝐚𝐩𝐞 - 𝐏𝐫𝐨𝐟𝐢𝐥𝐞\n"
            "• 📧 𝐄𝐦𝐚𝐢𝐥𝐬 - 𝐂𝐨𝐦𝐦𝐢𝐭𝐬\n"
            "• 🔍 .𝐄𝐧𝐯 - 𝐂𝐨𝐧𝐟𝐢𝐠\n"
            "• 🔑 𝐊𝐞𝐲𝐬 - 𝐓𝐨𝐤𝐞𝐧𝐬\n"
            "• 📋 𝐑𝐞𝐩𝐨𝐫𝐭 - 𝐅𝐮𝐥𝐥",
            reply_markup=get_main_menu(),
            parse_mode='HTML'
        )
    
    elif data == "noop":
        await query.answer()
    
    elif data in ["scrape", "emails", "env", "keys", "report"]:
        class DummyUpdate:
            def __init__(self, query):
                self.callback_query = query
                self.effective_user = query.from_user
                self.message = query.message
        dummy = DummyUpdate(query)
        await perform_scan(dummy, ctx, data)


# ---------------------------------------------------------------------------
# 𝐄𝐫𝐫𝐨𝐫 𝐇𝐚𝐧𝐝𝐥𝐞𝐫
# ---------------------------------------------------------------------------
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"❌ 𝐔𝐩𝐝𝐚𝐭𝐞 {update} 𝐜𝐚𝐮𝐬𝐞𝐝 𝐞𝐫𝐫𝐨𝐫 {context.error}")
    try:
        await update.message.reply_text(
            "❌ **𝐒𝐨𝐫𝐫𝐲, 𝐚𝐧 𝐞𝐫𝐫𝐨𝐫 𝐨𝐜𝐜𝐮𝐫𝐫𝐞𝐝.**\n"
            "𝐏𝐥𝐞𝐚𝐬𝐞 𝐭𝐫𝐲 𝐚𝐠𝐚𝐢𝐧 𝐥𝐚𝐭𝐞𝐫.",
            parse_mode='HTML'
        )
    except:
        pass


# ---------------------------------------------------------------------------
# 𝐌𝐚𝐢𝐧
# ---------------------------------------------------------------------------
async def post_init(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start", "𝐒𝐡𝐨𝐰 𝐦𝐚𝐢𝐧 𝐦𝐞𝐧𝐮"),
        BotCommand("target", "𝐒𝐞𝐭 𝐆𝐢𝐭𝐇𝐮𝐛 𝐭𝐚𝐫𝐠𝐞𝐭"),
        BotCommand("help", "𝐒𝐡𝐨𝐰 𝐡𝐞𝐥𝐩"),
    ])
    logger.info("✅ 𝐁𝐨𝐭 𝐜𝐨𝐦𝐦𝐚𝐧𝐝𝐬 𝐫𝐞𝐠𝐢𝐬𝐭𝐞𝐫𝐞𝐝")


def main():
    logger.info("🚀 𝐒𝐭𝐚𝐫𝐭𝐢𝐧𝐠 𝐆𝐢𝐭𝐇𝐮𝐛 𝐒𝐜𝐫𝐚𝐩𝐞𝐫 𝐁𝐨𝐭...")
    
    app = Application.builder().token(TG_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_or_help))
    app.add_handler(CommandHandler("help", start_or_help))
    app.add_handler(CommandHandler("target", set_target))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)

    logger.info("✅ 𝐁𝐨𝐭 𝐢𝐬 𝐫𝐞𝐚𝐝𝐲! 𝐏𝐨𝐥𝐥𝐢𝐧𝐠 𝐬𝐭𝐚𝐫𝐭𝐞𝐝.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
