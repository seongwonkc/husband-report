# 남편은 오늘 뭐 했어?

`D:/GitHub` 아래 모든 저장소의 그날 커밋을 긁어서, **기술을 전혀 모르는 사람이 읽을 수 있는
한국어 하루 요약 웹페이지**로 만듭니다. GitHub Pages 로 그대로 배포됩니다.

---

**사이트 주소 — https://seongwonkc.github.io/husband-report/**

## ⚠️ 이 저장소는 Public 입니다

`days/` 에 쓰는 글은 **전부 인터넷에 공개**되고 검색에도 잡힙니다.
숫자를 하나 적을 때마다 그게 공개돼도 괜찮은지 한 번씩 생각하고 쓰세요.
지금도 사용자 수·이탈률·가격 같은 게 들어가 있습니다 (2026-08-13 에 그대로 두기로 결정).

`raw/` 폴더(커밋 원문 그대로)만 `.gitignore` 로 제외돼 있습니다.

Private 으로 바꾸고 싶어지면 GitHub Pro($4/월)가 필요합니다 — 무료 플랜은
Public 저장소에서만 Pages 를 켤 수 있습니다.

---

## 매일 하는 일

```bash
cd d:/GitHub/husband-report

python report.py collect      # 1. 오늘 커밋 긁어오기 → raw/2026-08-13.json
                              # 2. Claude 에게 "오늘 것 정리해줘" → days/2026-08-13.json 작성
python report.py build        # 3. 사이트 데이터 만들기 → docs/data.js

git add -A && git commit -m "2026-08-13" && git push
```

특정 날짜를 다시 만들려면 `python report.py collect 2026-08-11` 처럼 날짜를 붙입니다.

### Claude 에게 시킬 때

> 오늘 작업 정리해서 `days/` 에 넣어줘

Claude 가 `raw/<날짜>.json` 을 읽고 한국어 설명을 써서 `days/<날짜>.json` 을 만듭니다.

---

## 폴더 구조

```
report.py            수집기 + 빌더 (표준 라이브러리만 사용, 설치할 것 없음)
repos.json           저장소 → 아내가 읽을 한국어 이름
raw/<날짜>.json      ① 자동 수집된 원본 (숫자·시각·커밋 원문)   ※ git 제외
days/<날짜>.json     ② 사람이 쓴 한국어 설명만
docs/index.html      ③ 사이트 본체
docs/img/            치비 캐릭터 5종(일한 양에 따라 바뀜) + 왕관 + 공주
docs/data.js         ①+② 를 합친 결과. build 가 만듭니다
```

### 커밋으로 안 남는 일도 셉니다

git 저장소가 아닌 폴더(`math_pipeline`, `reports_mt16`, `lecture_materials` …)에서
그날 수정된 파일을 찾아 **"코드 밖의 일"** 카드로 보여 줍니다. 문제집 제작, 학생 리포트,
자료 정리처럼 커밋이 안 남는 일이 하루의 절반을 차지하기 때문입니다.
이걸 넣고 나서 8/13 이 6.1시간 → 9.2시간이 되었습니다.

- 중첩된 git 저장소는 건너뜁니다 (커밋으로 이미 세니까 중복 방지)
- 숨김 폴더(`.impeccable` 등)와 `_tmp*` 는 제외
- 🚨 **파일명은 사이트로 내보내지 않습니다.** `DanielLab_MT16_02_Olivia.pdf` 처럼
  학생 실명이 들어가는데 사이트는 공개돼 있습니다. 개수와 확장자만 나갑니다.
  요약 글에도 학생 이름은 절대 쓰지 마세요.

**일한 시간**은 커밋 시각 + 파일 수정 시각을 보고 되짚습니다 (`estimate_effort`). 커밋 간격이 2시간 이내면
한 번 앉은 것으로 묶고, 세션마다 준비 시간 1시간을 더합니다. 기록이 없는 시간은 세지 않으니
부풀려지지 않습니다 — 오히려 실제보다 적게 나옵니다.

**저장소 이름을 바꾸면** `repos.json` 만 고치고 `build` 하면 됩니다. 예전 날짜까지 전부
새 이름으로 바뀌므로 다시 수집할 필요가 없습니다.

**숫자는 손으로 옮겨 적지 않습니다.** `days/` 에는 글만 쓰고, 커밋 수·시각·파일 수는
`build` 가 `raw/` 에서 자동으로 가져옵니다. 그래서 요약과 숫자가 어긋날 일이 없습니다.

### `days/<날짜>.json` 형식

```json
{
  "date": "2026-08-13",
  "headline": "그날 하루를 두세 문장으로. 제일 중요한 것 하나를 앞에.",
  "note": "(선택) 덧붙이고 싶은 한마디",
  "projects": {
    "seneca_maro": {
      "summary": "이 프로젝트에서 뭘 했고 그게 왜 중요한지, 사람 말로.",
      "bullets": ["짧게 끊어 읽을 항목", "없어도 됩니다"]
    }
  }
}
```

`projects` 의 열쇠(`seneca_maro`)는 `raw/` 파일에 있는 `repo` 값과 같아야 합니다.
설명을 빠뜨린 프로젝트가 있으면 `build` 가 경고해 주고, 사이트에는 커밋 원문이 그대로 보입니다.

---

## 처음 한 번만 하는 설정

```bash
cd d:/GitHub/husband-report
git init -b main
git add -A
git commit -m "첫 커밋"
gh repo create husband-report --private --source=. --push
```

그다음 GitHub 저장소에서 **Settings → Pages → Source: `main` 브랜치의 `/docs` 폴더** 로 지정합니다.
1~2분 뒤 `https://<아이디>.github.io/husband-report/` 에서 열립니다.

---

## 동작 방식에서 알아 둘 것

- **남편 커밋만 셉니다.** `report.py` 의 `AUTHOR_EMAILS` 에 있는 이메일
  (`seongwonkc@gmail.com`) 만 집계합니다. Sungwon 등 다른 사람 커밋은 빠집니다.
- **같은 저장소를 여러 번 세지 않습니다.** `seneca_maro-aptitude` 나
  `daniellabsat-main-audit` 같은 워크트리는 부모 저장소와 하나로 묶입니다.
- **브랜치가 갈라져도 한 번만 셉니다.** `main` 과 `demo` 양쪽에 같은 작업이 올라가 있으면
  (daniellabsat 이 그렇습니다) 제목+시각으로 묶어 한 건으로 봅니다.
- **stash 는 작업이 아닙니다.** `refs/stash` 는 제외합니다.
- **GitHub 에 안 올린 커밋도 표시됩니다.** 로컬에만 있는 커밋은 `아직 안 올림` 으로 나옵니다.
- **git 저장소가 아닌 폴더는 안 잡힙니다.** `D:/GitHub/ForgeSAT` 처럼 `.git` 이 없는 폴더의
  작업은 기록에 남지 않습니다.
- 사이트는 인터넷 연결 없이도 열립니다. `docs/index.html` 을 그냥 더블클릭해도 됩니다.

## 저장소 이름 바꾸기

`repos.json` 의 `names` 를 고치면 됩니다. 몇 개는 추측으로 채워 넣었으니 확인해 주세요.
`_exclude` 에 넣은 것(남의 코드)은 아예 집계에서 빠집니다.
