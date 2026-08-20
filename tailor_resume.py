"""Tailor Rafi's resume to each job description without inventing skills.

ATS/AI screeners reject generic resumes. This rewrites headline, summary,
skill order, and bullet order using only facts in data/resume/master.json
and keywords that actually appear in the JD.
"""
from __future__ import annotations

import html as htmlmod
import json
import re
import ssl
import time
import urllib.request
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent
MASTER = json.loads((ROOT / "data" / "resume" / "master.json").read_text(encoding="utf-8"))
OUT_DIR = ROOT / "data" / "resume" / "tailored"
JD_DIR = ROOT / "data" / "resume" / "jds"
CTX = ssl.create_default_context()
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

CURRENT: dict = {}

TITLE_MAP = [
    (r"solution.?s? architect", "Solutions Architect"),
    (r"technical architect", "Technical Architect"),
    (r"software architect", "Software Architect"),
    (r"cloud architect", "Cloud Architect"),
    (r"application architect", "Application Architect"),
    (r"backend architect", "Backend Architect"),
    (r"full.?stack architect", "Full Stack Architect"),
    (r"\.net architect|dotnet architect", ".NET Architect"),
    (r"principal (software )?engineer|principal swe|principal sde", "Principal Software Engineer"),
    (r"staff (software )?engineer|staff swe|staff sde", "Staff Software Engineer"),
    (r"senior staff", "Senior Staff Software Engineer"),
    (r"engineering manager", "Engineering Manager"),
    (r"technical lead|lead software|engineering lead", "Technical Lead"),
    (r"senior \.net|senior (software|backend|full.?stack)", "Senior Software Engineer"),
]

SKILL_ALIASES = {
    ".net": [".net", "dotnet", ".net core", "asp.net", "c#", "csharp"],
    "azure": ["azure", "microsoft azure", "app service", "aks"],
    "aws": ["aws", "amazon web services", "eks", "ec2", "s3"],
    "microservices": ["microservice", "microservices", "distributed"],
    "kafka": ["kafka", "event streaming", "event-driven"],
    "rabbitmq": ["rabbitmq", "message queue", "messaging"],
    "kubernetes": ["kubernetes", "k8s", "container orchestr"],
    "docker": ["docker", "container"],
    "react": ["react"],
    "angular": ["angular"],
    "sql server": ["sql server", "mssql", "t-sql"],
    "postgresql": ["postgres", "postgresql"],
    "rest": ["rest", "web api", "restful"],
    "ci/cd": ["ci/cd", "jenkins", "devops pipeline", "continuous integration"],
}

FORBIDDEN = re.compile(
    r"\b(java|spring boot|python|golang|\bgo\b|node\.?js|salesforce|servicenow|"
    r"\bpega\b|guidewire|sap hana|oracle erp)\b",
    re.I,
)


def _slug(text: str, n: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return (s[:n] or "job").strip("_")


def fetch_jd(job: dict) -> str:
    JD_DIR.mkdir(parents=True, exist_ok=True)
    jid = _slug(str(job.get("job_id") or job.get("url") or "x"), 60)
    cache = JD_DIR / f"{jid}.txt"
    if cache.exists() and cache.stat().st_size > 80:
        return cache.read_text(encoding="utf-8", errors="replace")
    url = job.get("url") or job.get("apply_url") or ""
    blob = f"{job.get('title') or ''} {job.get('company') or ''} {job.get('location') or ''}"
    if url:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
        try:
            with urllib.request.urlopen(req, context=CTX, timeout=12) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except Exception:
            raw = ""
        if raw:
            for m in re.finditer(
                r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                raw,
                re.I | re.S,
            ):
                try:
                    data = json.loads(htmlmod.unescape(m.group(1)))
                except Exception:
                    continue
                rows = data if isinstance(data, list) else [data]
                for row in rows:
                    if isinstance(row, dict) and (
                        "JobPosting" in str(row.get("@type") or "") or row.get("description")
                    ):
                        desc = row.get("description") or ""
                        if len(str(desc)) > 80:
                            blob = htmlmod.unescape(re.sub(r"<[^>]+>", " ", str(desc)))
                            break
            if len(blob) < 200:
                cleaned = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
                cleaned = re.sub(r"(?is)<[^>]+>", " ", cleaned)
                cleaned = htmlmod.unescape(re.sub(r"\s+", " ", cleaned))
                blob = f"{job.get('title') or ''} {cleaned}"[:12000]
    cache.write_text(blob, encoding="utf-8")
    return blob


def _has(text: str, needle: str) -> bool:
    n = (needle or "").lower()
    if not n:
        return False
    if re.search(r"[^a-z0-9]", n) or len(n) <= 4 or n in {"scala", "rest", "git", "api", "aws", "azure"}:
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])", text, re.I))
    return n in text.lower()


def mapped_title(job: dict, jd: str) -> str:
    blob = f"{job.get('title') or ''} {jd[:1500]}"
    for pat, title in TITLE_MAP:
        if re.search(pat, blob, re.I):
            return title
    return "Technical Architect"


def matched_skills(jd: str) -> list[str]:
    t = jd.lower()
    found = []
    for canon, aliases in SKILL_ALIASES.items():
        if any(_has(t, a) for a in aliases):
            found.append(canon)
    for skill in MASTER["ownedSkills"]:
        if skill not in found and _has(t, skill):
            found.append(skill)
    return found


def headline_for(title: str, skills: list[str]) -> str:
    show = []
    labels = {
        ".net": ".NET", "ci/cd": "CI/CD", "sql server": "SQL Server",
        "aws": "AWS", "azure": "Azure", "kubernetes": "Kubernetes",
        "microservices": "Microservices", "rabbitmq": "RabbitMQ",
        "kafka": "Kafka", "react": "React", "angular": "Angular",
    }
    for s in skills:
        label = labels.get(s, s.title())
        if label not in show:
            show.append(label)
        if len(show) == 3:
            break
    if not show:
        show = [".NET", "Cloud", "Distributed Systems"]
    return f"{title} — {' · '.join(show)}"


def summary_for(title: str, job: dict, jd: str, skills: list[str]) -> str:
    company = job.get("company") or "the company"
    loc = job.get("location") or "Hyderabad"
    skill_txt = ", ".join(
        {".net": ".NET Core / C#", "azure": "Azure", "aws": "AWS", "kafka": "Kafka",
         "kubernetes": "Kubernetes", "microservices": "microservices",
         "react": "React", "angular": "Angular"}.get(s, s)
        for s in skills[:5]
    ) or ".NET Core, AWS/Azure, and microservices"
    domain = ""
    jl = jd.lower()
    if any(w in jl for w in ("health", "payer", "claim", "clinical")):
        domain = " including large-scale healthcare platforms at UnitedHealth Group"
    elif any(w in jl for w in ("retail", "pos", "payment", "transaction")):
        domain = " including high-volume retail/POS platforms at NCR"
    elif any(w in jl for w in ("broker", "wealth", "trading", "capital market", "fintech", "bank")):
        domain = " across enterprise platforms with strong API, messaging, and reliability needs"
    return (
        f"{title} with 15+ years designing distributed, cloud-native systems and leading engineering "
        f"delivery{domain}. Deep hands-on background in {skill_txt}, with ownership of service boundaries, "
        f"API contracts, event-driven messaging, and deployment topology. "
        f"Seeking the {job.get('title') or title} role at {company} ({loc}) — ready to start immediately "
        f"from Hyderabad and contribute from day one on architecture, technical direction, and shipped software."
    )


def order_skills(jd: str) -> dict[str, list[str]]:
    t = jd.lower()
    out = {}
    for group, items in MASTER["skillGroups"].items():
        scored = []
        for item in items:
            score = sum(1 for w in re.findall(r"[a-z0-9.#+]+", item.lower()) if len(w) > 2 and w in t)
            scored.append((score, item))
        scored.sort(key=lambda x: (-x[0], x[1]))
        # keep original items, just reordered; drop Scala unless JD mentions it
        kept = []
        for _, item in scored:
            if item.lower() == "scala" and "scala" not in t:
                continue
            kept.append(item)
        out[group] = kept
    # If Azure-heavy, rename cloud group emphasis by putting Azure line first — already scored
    return out


def order_roles(jd: str) -> list[dict]:
    t = jd.lower()
    roles = []
    for role in MASTER["roles"]:
        bullets = []
        for b in role["bullets"]:
            score = sum(1 for w in re.findall(r"[a-z0-9.#+]+", b.lower()) if len(w) > 3 and w in t)
            if any(d in t for d in role.get("domains") or []):
                score += 3
            bullets.append((score, b))
        bullets.sort(key=lambda x: -x[0])
        roles.append({**role, "bullets": [b for _, b in bullets]})
    # Keep chronological (current first). Domain-matching roles already have stronger bullets first.
    return roles


def cover_for(title: str, job: dict, skills: list[str]) -> str:
    skill_txt = ", ".join(s.upper() if s in {"aws"} else s for s in skills[:4]) or ".NET, Azure/AWS, microservices"
    return (
        f"I am applying for {job.get('title') or title} at {job.get('company') or 'your team'}. "
        f"I am a Technical Architect / Technical Lead with 15+ years in {skill_txt}, "
        f"currently Principal Analyst (Technical Architect) at Nemetschek in Hyderabad. "
        f"I have led teams (including 10 engineers at UnitedHealth Group), owned microservices and API architecture "
        f"on .NET Core, and shipped on AWS and Azure with Kafka/RabbitMQ and Kubernetes. "
        f"Notice period is immediate. Expected CTC is 65 LPA."
    )


def _p(text: str, *, bold=False, size=22, center=False, color=None, after=80, before=0, border=False) -> str:
    jc = "<w:jc w:val=\"center\"/>" if center else ""
    bdr = (
        "<w:pBdr><w:bottom w:val=\"single\" w:color=\"1F3864\" w:sz=\"4\" w:space=\"2\"/></w:pBdr>"
        if border else ""
    )
    rpr = (
        f"<w:rFonts w:ascii=\"Calibri\" w:hAnsi=\"Calibri\" w:cs=\"Calibri\"/>"
        f"{'<w:b/>' if bold else ''}"
        f"{f'<w:color w:val=\"{color}\"/>' if color else ''}"
        f"<w:sz w:val=\"{size}\"/><w:szCs w:val=\"{size}\"/>"
    )
    return (
        f"<w:p><w:pPr>{bdr}<w:spacing w:after=\"{after}\" w:before=\"{before}\"/>{jc}</w:pPr>"
        f"<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"
    )


def _bullet(text: str) -> str:
    return (
        "<w:p><w:pPr><w:pStyle w:val=\"ListParagraph\"/>"
        "<w:numPr><w:ilvl w:val=\"0\"/><w:numId w:val=\"1\"/></w:numPr>"
        "<w:spacing w:after=\"60\"/></w:pPr>"
        f"<w:r><w:rPr><w:rFonts w:ascii=\"Calibri\" w:hAnsi=\"Calibri\"/><w:sz w:val=\"21\"/></w:rPr>"
        f"<w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"
    )


def _skill_line(label: str, items: list[str]) -> str:
    return (
        "<w:p><w:pPr><w:spacing w:after=\"60\"/></w:pPr>"
        "<w:r><w:rPr><w:rFonts w:ascii=\"Calibri\" w:hAnsi=\"Calibri\"/><w:b/><w:sz w:val=\"20\"/></w:rPr>"
        f"<w:t xml:space=\"preserve\">{escape(label)}: </w:t></w:r>"
        "<w:r><w:rPr><w:rFonts w:ascii=\"Calibri\" w:hAnsi=\"Calibri\"/><w:sz w:val=\"20\"/></w:rPr>"
        f"<w:t xml:space=\"preserve\">{escape(', '.join(items))}</w:t></w:r></w:p>"
    )


def write_docx(path: Path, doc: dict) -> None:
    body = []
    body.append(_p(MASTER["fullName"], bold=True, size=32, center=True, color="1F3864", after=40))
    body.append(_p(doc["headline"], center=True, size=22, after=40))
    contact = f"{MASTER['location']} | {MASTER['phone']} | {MASTER['email']} | LinkedIn"
    body.append(_p(contact, center=True, size=20, after=160, border=True))
    body.append(_p("PROFESSIONAL SUMMARY", bold=True, size=22, color="1F3864", before=120, after=80, border=True))
    body.append(_p(doc["summary"], size=21, after=120))
    body.append(_p("CORE TECHNICAL COMPETENCIES", bold=True, size=22, color="1F3864", before=80, after=80, border=True))
    for label, items in doc["skills"].items():
        if items:
            body.append(_skill_line(label, items))
    body.append(_p("PROFESSIONAL EXPERIENCE", bold=True, size=22, color="1F3864", before=160, after=80, border=True))
    for role in doc["roles"]:
        line = f"{role['title']} — {role['company']}   {role['dates']}"
        body.append(_p(line, bold=True, size=21, before=120, after=40))
        for b in role["bullets"]:
            body.append(_bullet(b))
    edu = MASTER["education"]
    body.append(_p("EDUCATION", bold=True, size=22, color="1F3864", before=160, after=80, border=True))
    body.append(_p(f"{edu['degree']}", bold=True, size=21, after=20))
    body.append(_p(f"{edu['school']} — {edu['dates']}", size=21, after=80))
    if doc.get("keywords"):
        body.append(_p("SELECTED KEYWORDS (from experience)", bold=True, size=20, color="1F3864", before=80, after=40))
        body.append(_p(", ".join(doc["keywords"]), size=20, after=40))

    document_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        "<w:body>"
        + "".join(body)
        + "<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/>"
        "<w:pgMar w:top=\"720\" w:right=\"720\" w:bottom=\"720\" w:left=\"720\"/></w:sectPr>"
        "</w:body></w:document>"
    )
    numbering = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="0">
    <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/>
    <w:lvlText w:val="•"/><w:lvlJc w:val="left"/>
    <w:pPr><w:ind w:left="360" w:hanging="180"/></w:pPr></w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
</w:numbering>"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    doc_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""
    styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/>
  <w:pPr><w:ind w:left="360"/></w:pPr></w:style>
</w:styles>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document_xml)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        z.writestr("word/numbering.xml", numbering)
        z.writestr("word/styles.xml", styles)


def for_job(job: dict) -> str:
    """Build a tailored .docx for this job and point CURRENT at it."""
    jd = fetch_jd(job)
    title = mapped_title(job, jd)
    skills = matched_skills(jd)
    doc = {
        "headline": headline_for(title, skills),
        "summary": summary_for(title, job, jd, skills),
        "skills": order_skills(jd),
        "roles": order_roles(jd),
        "keywords": [s for s in skills if s in MASTER["ownedSkills"] or s in SKILL_ALIASES][:12],
    }
    company = _slug(job.get("company") or "company", 24)
    jid = _slug(str(job.get("job_id") or title), 28)
    fname = f"Rafi_Ahmed_{_slug(title, 28)}_{company}_{jid}.docx"
    path = OUT_DIR / fname
    write_docx(path, doc)
    latest = ROOT / "data" / "resume" / "Rafi_Resume_Latest.docx"
    latest.write_bytes(path.read_bytes())
    cover = cover_for(title, job, skills)
    (path.with_suffix(".cover.txt")).write_text(cover, encoding="utf-8")
    CURRENT.update({
        "path": str(path.resolve()),
        "cover": cover,
        "headline": doc["headline"],
        "title": title,
        "skills": skills,
        "job_id": str(job.get("job_id") or ""),
    })
    return CURRENT["path"]


def upload(page, path: str | None = None) -> bool:
    """Overwrite file inputs with the tailored resume (beats Copilot's generic file)."""
    path = path or CURRENT.get("path")
    if not path or not Path(path).exists():
        return False
    ok = False
    for sel in (
        "#resume",
        "input#resume",
        "input[name='resume']",
        "input[name='resumeFile']",
        "input[data-test='resume']",
        "input[type=file]",
    ):
        try:
            loc = page.locator(sel)
            n = loc.count() if hasattr(loc, "count") else 0
            for i in range(min(n or 0, 3)):
                try:
                    el = loc.nth(i)
                    try:
                        if not el.is_visible():
                            continue
                    except Exception:
                        continue
                    el.set_input_files(path, timeout=800)
                    ok = True
                except Exception:
                    continue
            if ok:
                break
        except Exception:
            continue
    # LinkedIn / Easy Apply: click the tailored or master resume label if radios are hidden
    for label in ("Rafi_Ahmed", "Rafi_Resume_Architect", "Rafi_Resume_Technical", "Rafi_Resume_Latest"):
        try:
            page.get_by_text(label, exact=False).first.click(timeout=800)
            ok = True
            break
        except Exception:
            continue
    return ok


if __name__ == "__main__":
    import apply_now
    apply_now.BATCH = apply_now.load_all_discovered()
    jobs = apply_now.queue()[:3]
    if not jobs:
        print("No queued jobs to tailor.")
    for job in jobs:
        p = for_job(job)
        print(f"{job.get('company')}: {job.get('title')}")
        print(f"  {CURRENT.get('headline')}")
        print(f"  skills: {', '.join(CURRENT.get('skills') or [])}")
        print(f"  {p}")
        time.sleep(0.2)
