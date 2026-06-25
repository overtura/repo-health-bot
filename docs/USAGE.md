# repo-health-bot 사용법

이 문서는 `repo-health-bot`을 처음 쓰는 사람을 위한 실행 가이드입니다.

## 1. 설치

저장소 루트에서 실행합니다.

```bash
python -m pip install -e .
```

설치하지 않고도 Python 파일을 직접 실행할 수 있습니다.

```bash
python repo_health_bot.py .
```

## 2. 현재 저장소 점검

```bash
python repo_health_bot.py .
```

설치 후에는 콘솔 명령도 사용할 수 있습니다.

```bash
repo-health-bot .
```

## 3. 다른 저장소 점검

먼저 대상 저장소를 clone합니다.

```bash
git clone https://github.com/OWNER/REPO.git checked-repo
```

그 다음 경로를 넘깁니다.

```bash
python repo_health_bot.py checked-repo
```

Windows PowerShell에서도 같은 방식으로 실행합니다.

```powershell
python repo_health_bot.py C:\path\to\checked-repo
```

## 4. JSON 출력

자동화나 스크립트에서 쓰려면 JSON 출력이 편합니다.

```bash
python repo_health_bot.py . --json
```

JSON에는 다음 필드가 들어 있습니다.

- `root`: 점검한 저장소 경로
- `file_count`: 전체 파일 수
- `text_file_count`: 텍스트로 읽은 파일 수
- `line_count`: 텍스트 파일 라인 수
- `metadata_files`: 감지한 메타데이터 파일 목록
- `todo_hits`: TODO/FIXME 위치 목록

## 5. 결과 해석

`TODO/FIXME hits`가 많다고 바로 나쁜 repo라는 뜻은 아닙니다. 다만 오래된 TODO가 방치되어 있거나, 실제 이슈로 옮겨야 할 작업이 코드에 묻혀 있을 수 있습니다.

`Metadata files`가 비어 있다면 README, 라이선스, 패키지 설정이 부족한지 확인하세요.

`Text files`가 예상보다 적으면 아직 repo-health-bot이 해당 확장자를 텍스트로 보지 않는 상태일 수 있습니다. 예를 들어 현재 기본 버전은 PowerShell 확장자 `.ps1`, `.psm1`, `.psd1`을 별도 지원하지 않습니다.

## 6. 로컬 검증

변경 후에는 다음 명령을 실행합니다.

```bash
git diff --check
python -m unittest discover -s tests
python repo_health_bot.py .
python repo_health_bot.py . --json
```

PowerShell 검증 스크립트도 사용할 수 있습니다.

```powershell
.\.codex\self-improve\run-checks.ps1
```

각 명령은 다음을 확인합니다.

- `git diff --check`: trailing whitespace나 잘못된 공백 변경이 없는지 확인합니다.
- `python -m unittest discover -s tests`: 기존 단위 테스트가 통과하는지 확인합니다.
- `python repo_health_bot.py .`: Markdown 리포트가 정상 생성되는지 확인합니다.
- `python repo_health_bot.py . --json`: 자동화에서 쓰는 JSON 출력이 정상 생성되는지 확인합니다.

로컬에서 문제가 나면 먼저 다음 항목을 확인하세요.

- `python` 명령이 Python 3.10 이상을 가리키는지 확인합니다. Windows에서 여러 Python이 설치되어 있으면 `py -3.10`처럼 버전을 지정해 실행할 수 있습니다.
- `ModuleNotFoundError`가 나면 저장소 루트에서 명령을 실행 중인지 확인하고, 필요하면 `python -m pip install -e .`로 다시 설치합니다.
- PowerShell 스크립트 실행이 차단되면 현재 터미널에서만 `Set-ExecutionPolicy -Scope Process Bypass`를 실행한 뒤 다시 시도합니다.
- 테스트가 임시 파일 경로 문제로 실패하면 `TEMP`와 `TMP`가 쓰기 가능한 로컬 폴더를 가리키는지 확인합니다.
