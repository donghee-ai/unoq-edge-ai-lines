# 2026-06-27 — PowerShell Rename-Item이 빈 폴더 `unoq-mediapipe-pose;C` 잔류

## 증상
`Rename-Item -Path "C:\Project\unoq-mediapipe-pose" -NewName "unoq-pose"` 실행 후 `Get-ChildItem`으로 확인:

```
unoq-mediapipe-pose;C   d-----
unoq-pose               d-----
```

`unoq-mediapipe-pose;C` 라는 이름의 **빈 폴더**가 추가로 생성됨. 컨텐츠는 `unoq-pose`로 정상 이동.

## 원인 추정
- 첫 호출 시 폴더가 다른 프로세스(VSCode/탐색기 등)에 점유되어 atomic rename이 부분만 처리됐을 가능성
- 또는 PowerShell -NewName 인자 처리 중 NTFS alternate data stream 표기(`;C` = filename:stream:type)가 잘못 작성됐을 가능성

원인 확정보단 **즉시 정리**가 우선.

## 해결
빈 폴더 단순 삭제 (안전 — 컨텐츠 없음 확인 완료):

```powershell
Remove-Item -Path "C:\Project\unoq-mediapipe-pose;C" -Force
```

## 재발 방지
- 폴더 rename 직전 VSCode/탐색기에서 해당 폴더 닫기 (workspace 종료)
- rename 후 `Get-ChildItem -Force`로 정확한 상태 확인 (`;C`, `:` 같은 NTFS stream 표기 점검)
- 빈 폴더 발견 시 컨텐츠 확인 후 즉시 정리

## 영향
- 본 작업(폴더 rename) 자체는 성공 — `unoq-pose`에 컨텐츠 그대로 이동
- 시간 손실: 진단 + 정리 약 1 분
