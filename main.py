#!/usr/bin/env python3
import os
import re
import base64
import json
import time
import asyncio
import threading
from datetime import datetime, timezone
from urllib.parse import quote
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import httpx
from dotenv import load_dotenv
import io

# ============================================================================
# 𝐋𝐨𝐚𝐝 𝐄𝐧𝐯𝐢𝐫𝐨𝐧𝐦𝐞𝐧𝐭
# ============================================================================
load_dotenv()

app = Flask(__name__)
CORS(app)

GH_TOKEN = os.getenv("GITHUB_TOKEN", "")
PORT = int(os.getenv("PORT", 5000))

API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "gh-scraper-webapp",
    "X-GitHub-Api-Version": "2022-11-28",
}
if GH_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GH_TOKEN}"

# ============================================================================
# 𝐏𝐚𝐭𝐭𝐞𝐫𝐧𝐬
# ============================================================================
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
    "OpenAI Key": re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}T3BlbkFJ[A-Za-z0-9_-]{20,}"),
    "OpenAI (legacy)": re.compile(r"\bsk-[A-Za-z0-9]{48}\b"),
    "Anthropic Key": re.compile(r"sk-ant-(?:api)?[0-9A-Za-z_-]{20,}"),
    "Google AI/Gemini": re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    "Google Service Acct": re.compile(r'"type":\s*"service_account"'),
    "HuggingFace Token": re.compile(r"\bhf_[A-Za-z0-9]{34,}\b"),
    "Groq API Key": re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b"),
    "Replicate Token": re.compile(r"\br8_[A-Za-z0-9]{36,}\b"),
    "xAI/Grok Key": re.compile(r"\bxai-[A-Za-z0-9]{40,}\b"),
    "Perplexity Key": re.compile(r"\bpplx-[A-Za-z0-9]{40,}\b"),
    "OpenRouter Key": re.compile(r"\bsk-or-v1-[0-9a-f]{64}\b"),
    "DeepSeek Key": re.compile(r"\bsk-(?:ds|deepseek)-[0-9a-zA-Z]{20,}\b"),
    "Mistral Key": re.compile(r"\b(?:mistral|ms)-[0-9a-zA-Z]{32}\b"),
    "Together AI Key": re.compile(r"\b[0-9a-f]{64}\b(?=.*together)"),
    "Cohere Token": re.compile(r"\b[0-9a-f]{40}\b(?=.*cohere)"),
    "Stability AI Key": re.compile(r"\bsk-[A-Za-z0-9]{48}(?=.*stability)"),
    "AWS Access Key": re.compile(r"\b(?:A3T[A-Z0-9]|AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}\b"),
    "AWS Secret (ctx)": re.compile(r"(?i)aws.{0,20}['\"][0-9a-zA-Z/+=]{40}['\"]"),
    "Azure Storage Key": re.compile(r"(?i)AccountKey=[A-Za-z0-9/+=]{88}"),
    "DigitalOcean Token": re.compile(r"\bdop_v1_[0-9a-f]{64}\b"),
    "Stripe Key": re.compile(r"\b[sr]k_live_[0-9a-zA-Z]{24,}\b"),
    "Twilio API Key": re.compile(r"\bSK[0-9a-fA-F]{32}\b"),
    "Twilio SID": re.compile(r"\bAC[a-zA-Z0-9]{32}\b"),
    "SendGrid Key": re.compile(r"\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}\b"),
    "Mailgun Key": re.compile(r"\bkey-[0-9a-zA-Z]{32}\b"),
    "Slack Token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "Slack Webhook": re.compile(r"https://hooks\.slack\.com/services/T[A-Za-z0-9_]+/B[A-Za-z0-9_]+/[A-Za-z0-9]+"),
    "Telegram Bot Token": re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_-]{33}\b"),
    "Discord Bot Token": re.compile(r"\b[\w-]{24}\.[\w-]{6}\.[\w-]{27}\b"),
    "GitHub Token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "GitLab Token": re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    "NPM Token": re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"),
    "PyPI Token": re.compile(r"pypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]+"),
    "Shopify Token": re.compile(r"\bshp(?:at|ca|pa)_[0-9a-fA-F]{32}\b"),
    "Heroku API Key": re.compile(r"(?i)heroku.{0,25}[0-9a-f-]{36}"),
    "JWT": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\b"),
    "Private Key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    "Database URL": re.compile(r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^\s'\"<>]{8,}"),
    "Generic Secret": re.compile(r"(?i)(?:api[_-]?key|secret|token|passwd|password)\s*[:=]\s*['\"][A-Za-z0-9_\-/.+=]{8,}['\"]"),
}

MAX_FILE_BYTES = 200_000
JUICY_FILE_RE = re.compile(
    r"(?i)(env|secret|credential|key|token|config|settings|\.pem|\.p12|\.db|\.sql|dump|backup)"
)

# ============================================================================
# 𝐆𝐢𝐭𝐇𝐮𝐛 𝐀𝐏𝐈 𝐇𝐞𝐥𝐩𝐞𝐫𝐬
# ============================================================================
async def gh_get(client: httpx.AsyncClient, url: str, params: dict = None):
    while True:
        try:
            r = await client.get(url, params=params)
            if r.headers.get("X-RateLimit-Remaining") == "0":
                reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait = max(reset - time.time(), 1)
                await asyncio.sleep(min(wait, 300))
                continue
            if r.status_code == 403 and "secondary rate limit" in r.text.lower():
                await asyncio.sleep(60)
                continue
            return r
        except Exception as e:
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
    return httpx.AsyncClient(base_url=API, headers=HEADERS, timeout=30, follow_redirects=True)

# ============================================================================
# 𝐒𝐜𝐚𝐧𝐧𝐢𝐧𝐠 𝐅𝐮𝐧𝐜𝐭𝐢𝐨𝐧𝐬
# ============================================================================
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
        r = await gh_get(client, f"/repos/{repo_full_name}/contents/{quote(path)}", {"ref": ref})
        if r.status_code != 200:
            return None
        data = r.json()
        if isinstance(data, dict) and data.get("content"):
            return base64.b64decode(data["content"]).decode("utf-8", "ignore")[:MAX_FILE_BYTES]
    except:
        return None
    return None

async def hunt_env_files(client, target, repos):
    results = []
    seen = set()
    
    if GH_TOKEN:
        for q in ENV_SEARCH_QUERIES:
            try:
                r = await gh_get(client, "/search/code", {"q": f"{q} user:{target}", "per_page": 50})
                if r.status_code != 200:
                    continue
                for item in r.json().get("items", []):
                    key = (item["repository"]["full_name"], item["path"])
                    if key in seen:
                        continue
                    seen.add(key)
                    raw = await gh_get(client, item["url"], {"Accept": "application/vnd.github.raw"})
                    if raw.status_code != 200:
                        continue
                    content = raw.text[:MAX_FILE_BYTES]
                    results.append({
                        "repo": key[0], "path": key[1],
                        "url": f"https://github.com/{key[0]}/blob/HEAD/{quote(key[1])}",
                        "hits": scan_text(content),
                    })
            except:
                continue
    
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
        scored = sorted(tree, key=lambda e: (0 if JUICY_FILE_RE.search(e.get("path", "")) else 1))
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

async def run_full_scan(target):
    async with mk_client() as client:
        profile, is_org = await get_profile(client, target), False
        if not profile:
            return {"error": f"'{target}' not found"}
        
        profile_data = await get_profile(client, target)
        is_org = profile_data.get("type") == "Organization" if profile_data else False
        repos = await list_repos(client, target, is_org)
        
        env_results = await hunt_env_files(client, target, repos)
        findings = await scan_repo_contents(client, repos)
        emails = await harvest_emails(client, repos)
        
        return {
            "target": target,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "profile": profile_data,
            "repo_count": len(repos),
            "repos": [
                {
                    "name": r["full_name"],
                    "stars": r["stargazers_count"],
                    "language": r.get("language"),
                    "url": r["html_url"],
                    "description": r.get("description")
                }
                for r in repos[:50]
            ],
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

# ============================================================================
# 𝐅𝐥𝐚𝐬𝐤 𝐑𝐨𝐮𝐭𝐞𝐬
# ============================================================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scan', methods=['POST'])
def scan():
    data = request.json
    target = data.get('target', '').strip()
    scan_type = data.get('type', 'full')
    
    if not target:
        return jsonify({"error": "𝐏𝐥𝐞𝐚𝐬𝐞 𝐩𝐫𝐨𝐯𝐢𝐝𝐞 𝐚 𝐭𝐚𝐫𝐠𝐞𝐭"}), 400
    
    # 𝐑𝐮𝐧 𝐬𝐜𝐚𝐧 𝐢𝐧 𝐚 𝐬𝐞𝐩𝐚𝐫𝐚𝐭𝐞 𝐭𝐡𝐫𝐞𝐚𝐝
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run_full_scan(target))
        loop.close()
        
        if "error" in result:
            return jsonify(result), 404
        
        # 𝐆𝐞𝐧𝐞𝐫𝐚𝐭𝐞 𝐉𝐒𝐎𝐍 𝐫𝐞𝐩𝐨𝐫𝐭
        if scan_type == "report":
            buf = io.BytesIO(json.dumps(result, indent=2, default=str).encode())
            buf.seek(0)
            return send_file(
                buf,
                as_attachment=True,
                download_name=f"github_scan_{target}.json",
                mimetype="application/json"
            )
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health')
def health():
    return jsonify({
        "status": "𝐀𝐜𝐭𝐢𝐯𝐞",
        "timestamp": datetime.now().isoformat(),
        "github_token": "✅ 𝐒𝐞𝐭" if GH_TOKEN else "❌ 𝐍𝐨𝐭 𝐬𝐞𝐭"
    })

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "𝐑𝐨𝐮𝐭𝐞 𝐧𝐨𝐭 𝐟𝐨𝐮𝐧𝐝"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "𝐈𝐧𝐭𝐞𝐫𝐧𝐚𝐥 𝐬𝐞𝐫𝐯𝐞𝐫 𝐞𝐫𝐫𝐨𝐫"}), 500

# ============================================================================
# 𝐌𝐚𝐢𝐧
# ============================================================================
if __name__ == '__main__':
    print("🚀 𝐆𝐢𝐭𝐇𝐮𝐛 𝐒𝐜𝐫𝐚𝐩𝐞𝐫 𝐖𝐞𝐛 𝐀𝐩𝐩")
    print(f"📡 𝐒𝐞𝐫𝐯𝐞𝐫: http://localhost:{PORT}")
    print(f"🔑 𝐆𝐢𝐭𝐇𝐮𝐛 𝐓𝐨𝐤𝐞𝐧: {'✅' if GH_TOKEN else '❌'}")
    print("-" * 50)
    app.run(host='0.0.0.0', port=PORT, debug=True)
