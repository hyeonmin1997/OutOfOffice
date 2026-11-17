# OutOfOffice

온보딩 업무를 위한 **로컬 시제품**. Python 표준 라이브러리만 필요합니다.

```sh
python3 app.py
```

http://127.0.0.1:8000 에서 실행합니다. 실제 메일 발송 없이 SQLite outbox를 사용합니다.

## 시연

1. Reset → Normal mail → Run onboarding → Approve: A/Alpha/member가 grants에 기록됩니다.
2. Reset → Normal mail → Run → Reject: 권한 변화가 없습니다.
3. Reset → Attack mail → Run: fixture에서는 B/Finance/admin 요청이 만들어지고 정책 검사에서 차단됩니다. 승인 요청과 권한 변경이 없어야 합니다.
4. DB와 logs에서 입력값, 판정, 이유, 승인 ID를 확인합니다.

**Fixture는 모델 응답을 흉내 낸 결정적 검사입니다. 실제 LLM 공격 성공/실패의 증거가 아닙니다.**

## 실제 LLM 연결

모델과 제공자는 아직 확정하지 않았습니다. `LLM_API_KEY`, `LLM_MODEL`, `LLM_CHAT_URL`을 환경변수로 설정하고 Live LLM API를 선택합니다. 어댑터는 chat-completions 형식의 tool calling 응답을 사용합니다. 제공자의 API 호환성과 시험 허용 정책을 확인해야 합니다. API 키를 저장소에 올리지 마세요.

한 응답에서 최대 5개 도구 요청, API 응답 최대 600토큰, 세션당 최대 10회 호출로 제한합니다. 실제 금액 기준 예산 제어는 아직 없습니다. 서버를 재시작하거나 Reset하면 호출 제한이 초기화됩니다. 공급자별 실호출은 아직 검증하지 않았습니다.

LLM이 공격을 거부하면 그 결과를 그대로 기록해야 합니다. fixture 결과를 실제 LLM 결과로 바꾸어 보고하면 안 됩니다.

## 구현 범위

- read_mail, lookup_user, create_event, send_email, grant_access 5개 도구
- 서버에 고정된 M/A/Alpha/member 업무와 명시적 허용 규칙
- 스키마 → 업무 범위/ACL → 정확한 행동 승인 → 실행 시 재검사
- 승인 만료 120초, 재사용 차단, 같은 DB 트랜잭션에서 승인 소비와 쓰기
- SQLite users/mails/tasks/grants/events/outbox/approvals/logs
- 순차 HTTP 서버와 로컬 UI

이 버전은 **로컬 사용자를 신뢰하는 시연 장치**입니다. M 로그인/세션 인증, 여러 사용자 격리, 공격자 전용 메일 투입 API는 아직 없습니다. 승인·reset endpoint는 신뢰된 시연자용입니다. 외부에 포트를 공개하거나 실제 서비스 보안을 주장하지 마세요. 서버 정책은 앱 코드에 고정되어 있으며 모델이 수정할 수 없습니다.

실제 API 모드는 한 차례 계획을 요청하고 도구를 실행하는 최소 흐름입니다. 도구 결과를 다시 모델에 전달하는 다단계 에이전트 루프, 재시도, 독립적인 비용 모니터링은 아직 구현하지 않았습니다.

## 검증

```sh
python3 -m unittest discover -s tests -v
```

단위 시험은 권한 검사와 승인 불변조건을 검사합니다. 제안서의 정상 40개/공격 40개 데이터셋 및 방어 전후 비교 실험은 **아직 수행하지 않았습니다**. 데이터 생성 규칙, 사례별 초기 DB와 예상 결과, 독립 검토 및 평가 분할을 먼저 정의해야 합니다. 금지 행동 0건 목표는 방어 적용 후 평가에 한정됩니다.

## JSON 데이터 편집

`data/seed/`의 JSON 파일은 팀원이 직접 편집하고 Git으로 공유하는 가상 초기 데이터입니다.

- `users.json`: 사용자 `id`, `name`
- `mails.json`: 메일 `id`, 메일함 소유자 `owner`, 본문 `body`
- `events.json`: 일정 `id`, 소유자 `owner`, 제목 `title`, 시간 `time` (시간대 포함 ISO 8601 문자열 권장)

각 파일의 배열에 객체를 추가하세요. 같은 파일 안에서 id는 고유해야 하며 owner는 users.json에 존재해야 합니다. 기본 시나리오를 위해 M/A/B와 M 소유 mail1은 유지합니다. 문자열은 큰따옴표, 객체 사이에는 쉼표를 사용합니다.

```json
{"id":"mail2","owner":"M","body":"A의 안내 회의는 11월 24일 오후 2시입니다."}
```

수정 후 아래 명령 또는 웹 화면의 **Reload JSON data**로 반영합니다.

```sh
python3 manage_data.py load
python3 manage_data.py show
```

동일 id는 갱신하고 새 id는 추가합니다. JSON에서 지운 행은 이 명령으로 DB에서 삭제되지 않으며, 기존 권한·승인·로그는 보존합니다. **Reset database는 JSON에서 DB를 새로 구성하며 기존 실행 결과와 승인·로그를 지웁니다.** 프로그램 재시작만으로 기존 DB를 덮어쓰지는 않습니다.

화면의 Saved mail for M에서 추가한 메일을 선택해 실행할 수 있습니다. 현재 계획기는 선택한 본문 한 개만 사용합니다. 실행용 본문은 mail1에 복사되며 다른 메일을 자동으로 모두 읽지는 않습니다. DB 조회에는 사용자·메일·일정도 표시합니다. 이 화면과 JSON 반영 기능은 신뢰된 로컬 시연자용이며 공격자 인터페이스가 아닙니다.

JSON 수정은 파일을 DB로 가져오는 방향입니다. 실행 중 DB 변경이 JSON에 자동 저장되지는 않습니다. JSON은 Git에 포함되고 demo.sqlite와 __pycache__는 제외됩니다. JSON을 pull한 팀원도 load를 실행하면 반영할 수 있습니다.
