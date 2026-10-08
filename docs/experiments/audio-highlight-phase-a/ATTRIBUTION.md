# Phase A 출처와 권리 확인

**공식 곡·CC BY 4.0 및 로컬 MP3의 공식 사이트 직접 다운로드: 6곡 모두 confirmed_by_user. Phase A 종합 verification_status=verified, rights_cleared=true. 공식 서버 파일과 SHA-256 바이너리 비교는 not_performed.**

## 확인 근거와 상태 구분

2026-10-08 후속 사용자 확인: Phase A 6곡 모두 Incompetech 공식 곡 페이지에서 Creative Commons Attribution 4.0 International (CC BY 4.0)을 확인했다고 통보했다. 이 기록의 공식 라이선스 확인 근거는 사용자 확인이며, 도구로 6곡 상세 페이지를 모두 직접 재검증했다고 표시하지 않는다. 공식 title/ISRC는 [Incompetech 전체 목록](https://incompetech.com/music/royalty-free/full_list.php)과 대조했다. 추가로 사용자는 현재 Phase A 원본 MP3 6곡을 모두 Incompetech 공식 사이트에서 직접 다운로드했다고 확인했다. 이 취득 경위 확인을 아래 기존 source SHA-256으로 식별되는 파일에 연결한다.

| 항목 | 상태 | 근거/범위 |
|---|---|---|
| 공식 곡 라이선스 | confirmed_by_user | 공식 페이지에서 CC BY 4.0을 확인한 사용자 통보 |
| 로컬 원본 MP3 취득 출처 | confirmed_by_user | 사용자가 현재 원본 6곡을 Incompetech 공식 사이트에서 직접 다운로드했다고 확인 |
| 공식 서버 파일과 SHA-256 비교 | not_performed | 공식 서버 파일을 별도 취득하여 비교하지 않음 |
| 종합 verification_status | verified | 공식 라이선스와 사용자 직접 다운로드 확인을 근거로 한 Phase A 내부 판정 |
| Dataset rights_cleared | true | Phase A 로컬 MSCLAP 기술 검증용 Dataset의 출처·라이선스 확인 완료 |
| Phase A 기술 검사 | 기존 6/6 통과 | 별도 decode·frame·PCM·재현성 결과; 권리 증명이 아님 |

공통 라이선스 이름: **Creative Commons Attribution 4.0 International (CC BY 4.0)**. 공식 [라이선스 URL](https://creativecommons.org/licenses/by/4.0/)과 [법률 원문](https://creativecommons.org/licenses/by/4.0/legalcode.en)을 참조한다.

## 공식 곡 정보와 로컬 원본 연결

아래 공식 URL은 곡 정보 페이지다. 실제 로컬 MP3 다운로드 URL이나 취득 증거로 표현하지 않는다. source SHA-256은 로컬 파일을 특정하며, 그 파일의 공식 취득 경로를 증명하지 않는다. manifest의 local_source_verification.source_sha256은 source.sha256과 동일하게 유지한다.

| 곡 | 공식 ISRC / 곡 정보 URL | 로컬 Source SHA-256 | 로컬 출처 상태 |
|---|---|---|---|
| The Britons | [USUAN2600004](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN2600004) | `00e766ef7a2635b1e7c116bfff794cb3485c17730ec26c114a9b3fb21d7a837d` | confirmed_by_user |
| Dentaneosuchus Hunt | [USUAN2500003](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN2500003) | `9db6b36ce1f47769a4f3b5c36c4a06981dea0e7a8fa9d44d7d30ddf180760ace` | confirmed_by_user |
| Cretaceous Dawn | [USUAN2500001](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN2500001) | `a3f7bc1b0e0947d9b2a00c4faaeec55c73458b13b97d7fcb5d20e830da6e9226` | confirmed_by_user |
| That Zen Moment | [USUAN2400001](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN2400001) | `d796b819607ebb2b9c04a5b5a838d0e167ed66b765ecacf9423fb6c0953853dc` | confirmed_by_user |
| Boogie Party | [USUAN2200002](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN2200002) | `738c7cf5b142bca6f249f731d1f7c5a5025d17b7a05ba649319b0c512c229643` | confirmed_by_user |
| All This | [USUAN1300001](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1300001) | `15aa40f76bf114748e23452e4659fed30cfb88745efa5d13c7279ea2fc370f12` | confirmed_by_user |

## 저작자 표시와 실제 변경 고지

모든 곡의 저작자는 **Kevin MacLeod (incompetech.com)**로 표시한다. 아래 attribution은 확인된 공식 곡의 라이선스와 실제 편집 사실을 기록하며, Phase A 범위의 출처·라이선스 확인에 적용하며, 공식 서버 바이너리 동일성이나 향후 모든 용도의 권리 검토 완료를 뜻하지 않는다. manifest와 같은 문구를 사용한다.

- "The Britons" Kevin MacLeod (incompetech.com). Licensed under Creative Commons Attribution 4.0 International (CC BY 4.0): https://creativecommons.org/licenses/by/4.0/ Changes: excerpt [0, 60) seconds (60 seconds); converted from MP3 to float32 WAV; source sample rate and stereo preserved.
- "Dentaneosuchus Hunt" Kevin MacLeod (incompetech.com). Licensed under Creative Commons Attribution 4.0 International (CC BY 4.0): https://creativecommons.org/licenses/by/4.0/ Changes: excerpt [120, 180) seconds (60 seconds); converted from MP3 to float32 WAV; source sample rate and stereo preserved.
- "Cretaceous Dawn" Kevin MacLeod (incompetech.com). Licensed under Creative Commons Attribution 4.0 International (CC BY 4.0): https://creativecommons.org/licenses/by/4.0/ Changes: excerpt [60, 120) seconds (60 seconds); converted from MP3 to float32 WAV; source sample rate and stereo preserved.
- "That Zen Moment" Kevin MacLeod (incompetech.com). Licensed under Creative Commons Attribution 4.0 International (CC BY 4.0): https://creativecommons.org/licenses/by/4.0/ Changes: excerpt [270, 330) seconds (60 seconds); converted from MP3 to float32 WAV; source sample rate and stereo preserved.
- "Boogie Party" Kevin MacLeod (incompetech.com). Licensed under Creative Commons Attribution 4.0 International (CC BY 4.0): https://creativecommons.org/licenses/by/4.0/ Changes: excerpt [90, 150) seconds (60 seconds); converted from MP3 to float32 WAV; source sample rate and stereo preserved.
- "All This" Kevin MacLeod (incompetech.com). Licensed under Creative Commons Attribution 4.0 International (CC BY 4.0): https://creativecommons.org/licenses/by/4.0/ Changes: excerpt [90, 150) seconds (60 seconds); converted from MP3 to float32 WAV; source sample rate and stereo preserved.

원본 sample rate와 stereo를 유지했다. 반복/padding, resampling, downmix, 음량 정규화는 적용하지 않았다. 지정 구간은 시작 포함·끝 제외이며 모든 Highlight는 정확히 60초다.

## 로컬 출처 검증 판단과 적용 범위

사용자가 현재 사용 중인 원본 MP3 6곡을 Incompetech 공식 사이트에서 직접 다운로드했다고 확인하여, 취득 출처는 confirmed_by_user로 기록한다. 각 파일은 기존 source SHA-256으로 식별한다. 공식 정보 URL은 곡 정보 페이지이며 실제 MP3 다운로드 주소가 아니다. 다운로드 주소·날짜를 임의로 만들지 않는다.

이전 ID3v2.2 title/artist 대조는 보조 근거다. 로컬 ISRC/copyright 태그가 없다는 관측은 유지하되 사용자 취득 확인을 미확인으로 표시하지 않는다. 공식 서버 파일을 별도로 취득하여 SHA-256을 비교하지 않았으므로 official_binary_verification=not_performed다.

**rights_cleared=true는 Phase A의 로컬 MSCLAP 기술 검증에 사용할 Dataset의 출처·라이선스 확인이 완료됐다는 의미다.** 공식 서버 파일과의 바이너리 동일성 검증이나 모든 향후 서비스/배포 용도에 대한 포괄적인 권리 검토가 완료됐다는 의미가 아니다. 실제 MSCLAP Embedding 평가도 아직 수행하지 않았다.

## 이전 조사와 후속 확인

이전 조사에서는 일부 공식 상세 페이지가 동적 Loading 상태로 반환되어 곡별 정보 전체를 확인하지 못했고 license/license_url을 null로 보존했다. 이번 사용자 확인을 후속 근거로 추가하여 현재 manifest의 공식 라이선스 필드를 채웠다. 과거 기술 실행 결과 JSON과 당시 권리 상태는 소급 수정하지 않았다.

## 후속 검토 범위

- 공식 서버 파일과의 SHA-256 비교는 수행하지 않았으며 별도 검증 항목이다.
- 실제 MP3/WAV는 Git 배포하지 않는다.
- 향후 서비스/배포 용도가 정해지면 제공된 고지의 보존, attribution 표시 위치, 기타 권리 조건과 이용 범위를 해당 범위에서 검토한다.
- 기존 실행 결과의 rights_cleared=false는 당시 기록으로 유지하며 현재 상태는 새 검증 결과로 확인한다.
