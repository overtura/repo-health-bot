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
python -m unittest discover -s tests
python repo_health_bot.py .
python repo_health_bot.py . --json
```

PowerShell 검증 스크립트도 사용할 수 있습니다.

```powershell
.\.codex\self-improve\run-checks.ps1
```
