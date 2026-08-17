#!/usr/bin/env python3
"""
남편 업무 리포트 — 수집기 & 빌더

  python report.py collect [YYYY-MM-DD]   D:/GitHub 의 모든 레포에서 그날 커밋을 긁어
                                          raw/YYYY-MM-DD.json 으로 저장 (Claude 가 읽는 파일)
  python report.py build                  days/*.json 을 묶어서 docs/data.js 생성 (사이트가 읽는 파일)
  python report.py status                 레포 목록 / 최근 활동 확인

표준 라이브러리만 사용합니다.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, date

ROOT = os.path.dirname(os.path.abspath(__file__))
SCAN_ROOT = os.environ.get("HR_SCAN_ROOT", os.path.dirname(ROOT))  # 기본: D:/GitHub
RAW_DIR = os.path.join(ROOT, "raw")
DAYS_DIR = os.path.join(ROOT, "days")
DOCS_DIR = os.path.join(ROOT, "docs")
CONFIG = os.path.join(ROOT, "repos.json")

# 이 이메일의 커밋만 집계합니다 (남편 본인 작업만).
AUTHOR_EMAILS = {"seongwonkc@gmail.com"}

MAX_DEPTH = 4
SKIP_DIRS = {"node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next"}

WEEKDAY_KO = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]

FS = "\x1f"  # 필드 구분자
RS = "\x1e"  # 레코드 구분자


def git(repo, *args, check=False):
    try:
        r = subprocess.run(
            ["git", "-C", repo, *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        sys.exit("git 이 설치되어 있지 않거나 PATH 에 없습니다.")
    if check and r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout


def load_config():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def find_repos(root, max_depth=MAX_DEPTH):
    """root 아래에서 .git 을 가진 디렉터리를 전부 찾습니다 (워크트리 포함)."""
    found = []
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath[len(root):].count(os.sep)
        if depth >= max_depth:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if ".git" in dirnames or ".git" in filenames:
            found.append(dirpath)
            dirnames[:] = [d for d in dirnames if d != ".git"]
    return sorted(found)


def normalize_remote(url):
    if not url:
        return None
    url = url.strip()
    url = re.sub(r"^git@([^:]+):", r"https://\1/", url)
    url = re.sub(r"\.git$", "", url)
    return url.rstrip("/").lower()


def resolve_remote(url, depth=0):
    """origin 이 로컬 경로면(예: 다른 폴더를 복제한 테스트용 사본) 그 폴더의 origin 을 따라갑니다.

    이걸 안 하면 `seneca_maro_gate_test` 처럼 로컬 복제본이 별개 레포로 잡혀
    같은 커밋이 두 번 세어집니다.
    """
    if not url:
        return None
    u = url.strip()
    if depth > 3:
        return normalize_remote(u)
    is_url = "://" in u or re.match(r"^[^/\\]+@[^:]+:", u)
    if not is_url:
        p = os.path.abspath(u)
        if os.path.exists(os.path.join(p, ".git")):
            inner = git(p, "remote", "get-url", "origin").strip()
            if inner:
                return resolve_remote(inner, depth + 1)
            return p.replace("\\", "/").lower()
    return normalize_remote(u)


def repo_identity(path):
    """같은 레포(워크트리/복제본)를 하나로 묶기 위한 키와 표시용 이름."""
    remote = resolve_remote(git(path, "remote", "get-url", "origin"))
    common = git(path, "rev-parse", "--git-common-dir").strip()
    if common:
        common = os.path.abspath(os.path.join(path, common)) if not os.path.isabs(common) else common
    key = remote or common or os.path.abspath(path)
    if remote:
        slug = remote.rsplit("/", 1)[-1]
    else:
        slug = os.path.basename(os.path.abspath(path))
    return key, slug


def collect_repo(path, day):
    """하루치 커밋을 뽑습니다. 저자 날짜(로컬) 기준으로 필터링합니다."""
    lo = (day - timedelta(days=2)).isoformat()
    hi = (day + timedelta(days=2)).isoformat()

    # RS 를 앞에 둡니다. 뒤에 두면 --numstat 블록이 레코드 경계 밖으로 밀려나 다음 커밋에 붙습니다.
    fmt = RS + FS.join(["%H", "%ae", "%an", "%aI", "%s", "%b"])
    # --all 대신 --branches/--remotes/--tags: --all 은 refs/stash 까지 끌어와서
    # "index on demo: ..." 같은 stash 항목이 진짜 작업으로 잡힙니다.
    # 머지 커밋도 셉니다 — 브랜치를 합치는 것도 그날 한 일입니다.
    out = git(path, "log", "--branches", "--remotes", "--tags",
              f"--since={lo}", f"--until={hi}",
              f"--pretty=format:{fmt}", "--numstat")
    if not out.strip():
        return []

    # 원격에 올라간 커밋 집합 (푸시 여부 판정용)
    pushed = set(git(path, "rev-list", "--remotes", f"--since={lo}", f"--until={hi}").split())

    commits = []
    for chunk in out.split(RS):
        chunk = chunk.strip("\n ")
        if not chunk:
            continue
        parts = chunk.split(FS)
        if len(parts) < 6:
            continue
        sha, email, name, adate, subject, rest = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]

        try:
            dt = datetime.fromisoformat(adate)
        except ValueError:
            continue
        if dt.date() != day:
            continue
        if email.lower() not in AUTHOR_EMAILS:
            continue

        # rest = 본문 + numstat 블록. numstat 은 "숫자\t숫자\t경로" 줄.
        body_lines, files, add, rem = [], [], 0, 0
        for line in rest.split("\n"):
            line = line.rstrip()
            if not line:
                continue
            m = re.match(r"^(\d+|-)\t(\d+|-)\t(.+)$", line)
            if m:
                a, r_, p = m.groups()
                add += int(a) if a.isdigit() else 0
                rem += int(r_) if r_.isdigit() else 0
                files.append(p)
            else:
                body_lines.append(line)

        commits.append({
            "sha": sha[:8],
            "time": dt.strftime("%H:%M"),
            "iso": dt.isoformat(),
            "author": name,
            "subject": subject.strip(),
            "body": "\n".join(body_lines).strip()[:400],
            "files": files[:12],
            "file_count": len(files),
            "added": add,
            "removed": rem,
            "pushed": sha in pushed,
        })

    commits.sort(key=lambda c: c["iso"])
    return commits


def scan_file_work(day, exclude_names):
    """git 레포가 아닌 폴더의 파일 작업을 훑습니다.

    문제집 제작·리포트·자료 정리처럼 커밋으로 남지 않는 일이 많습니다.
    그런 폴더에서 그날 수정된 파일을 찾아 '작업'으로 셉니다.
    (레포 안은 커밋으로 이미 세므로, 중첩된 git 레포는 건너뜁니다.)
    """
    out = []
    for name in sorted(os.listdir(SCAN_ROOT)):
        path = os.path.join(SCAN_ROOT, name)
        if not os.path.isdir(path) or name in SKIP_DIRS:
            continue
        if name.startswith(".") or name.startswith("_tmp"):
            continue          # 숨김·임시 폴더는 작업이 아닙니다
        if os.path.abspath(path) == ROOT or name in exclude_names:
            continue
        if os.path.exists(os.path.join(path, ".git")):
            continue          # git 레포는 커밋으로 집계

        hits = []
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames
                           if d not in SKIP_DIRS and not d.startswith(".")
                           and not os.path.exists(os.path.join(dirpath, d, ".git"))]
            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                try:
                    mt = os.path.getmtime(fp)
                except OSError:
                    continue
                dt = datetime.fromtimestamp(mt)
                if dt.date() == day:
                    hits.append((dt, os.path.relpath(fp, path).replace("\\", "/")))
        if not hits:
            continue
        hits.sort(key=lambda h: h[0])

        exts = {}
        for _, rel in hits:
            e = (os.path.splitext(rel)[1] or "(없음)").lower()
            exts[e] = exts.get(e, 0) + 1
        out.append({
            "dir": name,
            "count": len(hits),
            "from": hits[0][0].strftime("%H:%M"),
            "to": hits[-1][0].strftime("%H:%M"),
            "iso": [h[0].isoformat() for h in hits],
            "samples": [r for _, r in hits[:10]],
            "types": sorted(exts.items(), key=lambda kv: -kv[1])[:6],
        })
    out.sort(key=lambda x: (-x["count"], x["from"]))
    return out


def cmd_collect(argv):
    day = date.fromisoformat(argv[0]) if argv else date.today()
    cfg = load_config()
    exclude = {e.lower() for e in cfg.get("_exclude", [])}
    names = cfg.get("names", {})

    groups = {}   # key -> {slug, paths[], commits{키: commit}}
    for path in find_repos(SCAN_ROOT):
        if os.path.abspath(path) == ROOT:
            continue
        key, slug = repo_identity(path)
        if slug.lower() in exclude or os.path.basename(path).lower() in exclude:
            continue
        g = groups.setdefault(key, {"slug": slug, "paths": [], "commits": {}})
        g["paths"].append(os.path.relpath(path, SCAN_ROOT).replace("\\", "/"))
        for c in collect_repo(path, day):
            # 같은 작업이 여러 브랜치에 올라가 있으면 SHA 는 다르지만 내용은 같습니다
            # (예: daniellabsat 의 main / demo). 제목+시각으로 한 번 더 묶습니다.
            g["commits"].setdefault((c["subject"], c["iso"]), c)

    projects = []
    for g in groups.values():
        cs = sorted(g["commits"].values(), key=lambda c: c["iso"])
        if not cs:
            continue
        meta = names.get(g["slug"], {})
        projects.append({
            "repo": g["slug"],
            "ko": meta.get("ko", g["slug"]),
            "note": meta.get("note", ""),
            "paths": sorted(g["paths"]),
            "commits": cs,
            "count": len(cs),
            "from": cs[0]["time"],
            "to": cs[-1]["time"],
            "pushed": sum(1 for c in cs if c["pushed"]),
            "unpushed": sum(1 for c in cs if not c["pushed"]),
            "files": sorted({f for c in cs for f in c["files"]}),
            "added": sum(c["added"] for c in cs),
            "removed": sum(c["removed"] for c in cs),
        })
    projects.sort(key=lambda p: (-p["count"], p["from"]))

    # 커밋으로 남지 않는 작업(문제집·리포트·자료 제작)도 함께 봅니다
    repo_dirs = {p.split("/")[0] for g in groups.values() for p in g["paths"]}
    file_work = scan_file_work(day, repo_dirs)

    all_c = [c for p in projects for c in p["commits"]]
    all_c.sort(key=lambda c: c["iso"])
    stamps = sorted([c["iso"] for c in all_c] + [t for f in file_work for t in f["iso"]])
    raw = {
        "date": day.isoformat(),
        "weekday": WEEKDAY_KO[day.weekday()],
        "scanned_root": SCAN_ROOT.replace("\\", "/"),
        "repos_scanned": len(groups),
        "totals": {
            "commits": len(all_c),
            "projects": len(projects) + len(file_work),
            "files": len({f for p in projects for f in p["files"]})
                     + sum(f["count"] for f in file_work),
            "file_work_dirs": len(file_work),
            "added": sum(p["added"] for p in projects),
            "removed": sum(p["removed"] for p in projects),
            "first": stamps[0][11:16] if stamps else None,
            "last": stamps[-1][11:16] if stamps else None,
            "unpushed": sum(p["unpushed"] for p in projects),
        },
        "projects": projects,
        "file_work": file_work,
    }

    os.makedirs(RAW_DIR, exist_ok=True)
    out = os.path.join(RAW_DIR, f"{day.isoformat()}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)

    t = raw["totals"]
    print(f"{day} ({raw['weekday']})  레포 {len(groups)}개 스캔")
    print(f"  커밋 {t['commits']}건 · 프로젝트 {t['projects']}개 · 파일 {t['files']}개"
          + (f" · {t['first']}~{t['last']}" if t["first"] else ""))
    if t["unpushed"]:
        print(f"  ⚠ 아직 GitHub 에 안 올라간 커밋 {t['unpushed']}건")
    for p in projects:
        print(f"    - {p['ko']:<20} {p['count']}건  {p['from']}~{p['to']}  ({p['repo']})")
    for f in file_work:
        ko = names.get(f["dir"], {}).get("ko", f["dir"])
        print(f"    · {ko:<20} 파일 {f['count']}개  {f['from']}~{f['to']}  ({f['dir']})")
    print(f"→ {os.path.relpath(out, ROOT)}")
    return out


# ── 일한 시간 추정 ────────────────────────────────────────────────
# 커밋 시각만 보고 "실제로 몰입한 시간"을 되짚습니다. git-hours 방식과 같습니다.
#   · 커밋 사이 간격이 SESSION_GAP 이하면 같은 작업 묶음(세션)으로 봅니다
#   · 세션의 첫 커밋 앞에도 준비 시간이 있었을 테니 LEAD_IN 을 더합니다
# 어디까지나 추정입니다. 부풀리지 않습니다 — 커밋이 없는 시간은 세지 않습니다.
SESSION_GAP = 120   # 분. 이보다 오래 비면 다른 세션
LEAD_IN = 60        # 분. 세션 첫 커밋 이전에 쓴 시간

EFFORT_LEVELS = [
    (0.01, 0, "쉬는 날",   "오늘은 푹 쉬었어요"),
    (2.0,  1, "살짝",      "짬짬이 조금"),
    (5.0,  2, "열심히",    "제대로 붙잡고"),
    (8.0,  3, "아주 많이",  "하루를 통째로"),
    (99.0, 4, "폭주",      "이건 좀 너무했어요"),
]


def estimate_effort(iso_times):
    """커밋 시각 목록 → (분, 레벨, 이름, 한마디)."""
    def naive(s):
        # 커밋 시각은 +09:00 이 붙어 있고 파일 시각은 안 붙어 있어 그대로는 비교가 안 됩니다.
        # 둘 다 '그 컴퓨터의 벽시계 시각'으로 맞춥니다.
        dt = datetime.fromisoformat(s)
        return dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt

    ts = sorted(naive(t) for t in iso_times)
    if not ts:
        return {"minutes": 0, "hours": 0.0, "level": 0,
                "name": EFFORT_LEVELS[0][2], "blurb": EFFORT_LEVELS[0][3], "sessions": 0}

    total, sessions = 0.0, 1
    start = prev = ts[0]
    for t in ts[1:]:
        gap = (t - prev).total_seconds() / 60
        if gap > SESSION_GAP:
            total += (prev - start).total_seconds() / 60 + LEAD_IN
            sessions += 1
            start = t
        prev = t
    total += (prev - start).total_seconds() / 60 + LEAD_IN

    hours = total / 60
    for cutoff, lvl, name, blurb in EFFORT_LEVELS:
        if hours < cutoff:
            break
    return {"minutes": int(round(total)), "hours": round(hours, 1), "level": lvl,
            "name": name, "blurb": blurb, "sessions": sessions}


def cmd_build(argv):
    """raw/(숫자) + days/(사람이 쓴 한국어 설명) 을 합쳐 docs/data.js 를 만듭니다.

    days/*.json 에는 글만 씁니다. 커밋 수·시간·파일 수 같은 숫자는 전부 raw 에서
    가져오므로 손으로 옮겨 적다가 틀릴 일이 없습니다.
    """
    os.makedirs(DAYS_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)

    # 한국어 이름은 빌드할 때 다시 읽습니다. repos.json 만 고치고 build 하면
    # 예전에 수집해 둔 날짜까지 전부 새 이름으로 바뀝니다 (재수집 불필요).
    names = load_config().get("names", {})

    prose_by_date = {}
    for fn in sorted(os.listdir(DAYS_DIR)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(DAYS_DIR, fn), encoding="utf-8") as f:
            try:
                p = json.load(f)
            except json.JSONDecodeError as e:
                sys.exit(f"days/{fn} 이 올바른 JSON 이 아닙니다: {e}")
        prose_by_date[p.get("date", fn[:-5])] = p

    days, missing = [], []
    for fn in sorted(os.listdir(RAW_DIR) if os.path.isdir(RAW_DIR) else []):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(RAW_DIR, fn), encoding="utf-8") as f:
            raw = json.load(f)
        d = raw["date"]
        prose = prose_by_date.get(d, {})
        pp = prose.get("projects", {})

        projects = []
        for rp in raw["projects"]:
            w = pp.get(rp["repo"], {})
            if not w.get("summary"):
                missing.append(f"{d}/{rp['repo']}")
            meta = names.get(rp["repo"], {})
            projects.append({
                "kind": "git",
                "repo": rp["repo"],
                "ko": meta.get("ko", rp["ko"]),
                "note": meta.get("note", rp["note"]),
                "summary": w.get("summary", ""),
                "bullets": w.get("bullets", []),
                "count": rp["count"],
                "from": rp["from"], "to": rp["to"],
                "files": len(rp["files"]),
                "added": rp["added"], "removed": rp["removed"],
                "unpushed": rp["unpushed"],
                "tech": [{"t": c["time"], "s": c["subject"], "f": c["file_count"],
                          "a": c["added"], "r": c["removed"], "p": c["pushed"]}
                         for c in rp["commits"]],
            })

        # 커밋 없이 파일만 만진 작업도 같은 카드로 보여 줍니다
        for fw in raw.get("file_work", []):
            w = pp.get(fw["dir"], {})
            if not w.get("summary"):
                missing.append(f"{d}/{fw['dir']} (파일 작업)")
            meta = names.get(fw["dir"], {})
            projects.append({
                "kind": "files",
                "repo": fw["dir"],
                "ko": meta.get("ko", fw["dir"]),
                "note": meta.get("note", ""),
                "summary": w.get("summary", ""),
                "bullets": w.get("bullets", []),
                "count": fw["count"],
                "from": fw["from"], "to": fw["to"],
                "files": fw["count"],
                # 🚨 samples 는 절대 사이트로 내보내지 않습니다.
                # 파일명에 학생 실명이 들어갑니다 (DanielLab_MT16_02_Olivia.pdf).
                # 사이트는 공개되어 있으므로 개수와 확장자만 내보냅니다.
                "types": fw["types"],
            })

        if d not in prose_by_date and raw["totals"]["commits"]:
            missing.append(f"{d} (헤드라인 없음)")

        stamps = ([c["iso"] for p in raw["projects"] for c in p["commits"]]
                  + [t for f in raw.get("file_work", []) for t in f["iso"]])
        days.append({
            "date": d,
            "weekday": raw["weekday"],
            "headline": prose.get("headline", ""),
            "note": prose.get("note", ""),
            "stats": raw["totals"],
            "effort": estimate_effort(stamps),
            "times": sorted(s[11:16] for s in stamps),
            "projects": projects,
        })

    days.sort(key=lambda x: x["date"])
    payload = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "days": days,
    }
    out = os.path.join(DOCS_DIR, "data.js")
    with open(out, "w", encoding="utf-8") as f:
        f.write("window.REPORT = ")
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.write(";\n")
    print(f"{len(days)}일치 → {os.path.relpath(out, ROOT)}"
          + (f"  ({days[0]['date']} ~ {days[-1]['date']})" if days else ""))
    if missing:
        print(f"⚠ 한국어 설명이 아직 없는 항목 {len(missing)}개:")
        for m in missing[:15]:
            print(f"    {m}")
    return out


def cmd_status(argv):
    cfg = load_config()
    names = cfg.get("names", {})
    exclude = {e.lower() for e in cfg.get("_exclude", [])}
    groups = {}
    for path in find_repos(SCAN_ROOT):
        if os.path.abspath(path) == ROOT:
            continue
        key, slug = repo_identity(path)
        if slug.lower() in exclude or os.path.basename(path).lower() in exclude:
            continue
        groups.setdefault(key, {"slug": slug, "paths": []})["paths"].append(
            os.path.relpath(path, SCAN_ROOT).replace("\\", "/"))
    print(f"{SCAN_ROOT} — 고유 레포 {len(groups)}개\n")
    for g in sorted(groups.values(), key=lambda g: g["slug"]):
        ko = names.get(g["slug"], {}).get("ko", "— 이름 미지정 —")
        last = git(g["paths"] and os.path.join(SCAN_ROOT, g["paths"][0]),
                   "log", "--all", "-1", "--format=%aI", f"--author={'|'.join(AUTHOR_EMAILS)}",
                   "--perl-regexp").strip()[:10]
        extra = f"  (+워크트리 {len(g['paths']) - 1}개)" if len(g["paths"]) > 1 else ""
        print(f"  {g['slug']:<28} {ko:<22} 마지막 작업 {last or '없음':<10}{extra}")


def main():
    # 윈도우 콘솔에서 한글이 깨지지 않도록
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    cmds = {"collect": cmd_collect, "build": cmd_build, "status": cmd_status}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(__doc__)
        sys.exit(1)
    cmds[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
