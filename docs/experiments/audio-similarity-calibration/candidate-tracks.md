# Candidate tracks — calibration cohort v1

## 상태와 선정 기준

목표는 50곡이다. 이전에 확인한 34곡, manifest-only 재검증에서 PASS한 15곡, 마지막 대체 후보 1곡을 합쳐 정식 PASS 후보 50곡을 확정했다. 출처별 정식 후보는 Incompetech 2곡, 새 FMA 전체곡 20곡, Wikimedia Commons 22곡, ccMixter 6곡이다. HOLD 1곡은 검토 이력에만 남기고 PASS cohort와 manifest에서 제외했다. Audio는 다운로드하지 않았고, manifest의 파일별 decode 정보와 SHA-256은 모두 미측정 상태다. 후보 선정은 완료됐지만 Audio 취득 및 calibration 검증은 완료되지 않았다.

확정 기준은 완곡인 실제 음악 녹음, 공식 개별 페이지의 60초 이상 길이, 식별 가능한 제목/artist/source, 연구·개발 목적 로컬 분석을 허용하는 명시적 라이선스, attribution 조건 확인이다. Wikimedia Commons에서 `License review needed` 표기가 있는 파일은 제외했다. 수록된 수록 페이지에는 그런 경고가 없었다. 페이지 metadata는 실제 취득 후 decode 검증을 대체하지 않는다.

고정된 기존 Incompetech 2곡은 유지한다. 두 곡 모두 Kevin MacLeod이므로 해당 artist의 허용치 2곡을 채웠으며 추가하지 않는다. 기존 FMA-small/30초 Historical 자료와 Phase A 6곡은 제외한다. MUSAN은 이번 cohort에서 제외한다. FMA에서는 FMA-small이 만들어진 2017년 이후 개별 공개된 전체 트랙만 선택했다. 오래된 FMA 항목은 FMA-small 겹침 여부를 안전하게 배제할 수 없어 후보로 세지 않았다.

## 기존 확정 20곡 — 이번 확장 시작 시점 기준

`source_catalog_duration`은 각 공식 track/file page의 표기 길이를 초 단위로 옮긴 값이다. 이는 실제 decoder 측정값이 아니다. genre/mood는 제공자 또는 Commons 파일 설명의 source metadata만 기록하고, 별도 manual label은 아직 만들지 않았다. schema에 없는 acoustic/electronic, tempo 필드는 추가하지 않았다.

| sample_id | title | artist | provider | catalog duration | license | source/rights evidence | diversity metadata |
|---|---|---|---|---:|---|---|---|
| cal-incompetech-mandeville | Mandeville | Kevin MacLeod | Incompetech | 217 s | CC BY 4.0 | [공식 track page](https://music.kevin.macleod.incompetech.com/music/royalty-free/index.html?Search=Search&isrc=USUAN1100809), attribution 필요 | Reggae; Dark/Grooving (provider metadata) |
| cal-incompetech-lasting-hope | Lasting Hope | Kevin MacLeod | Incompetech | 143 s | CC BY 4.0 | [공식 track page](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100178), attribution 필요 | Soundtrack; Dark/Eerie/Mystical/Relaxed/Intense/Somber (provider metadata) |
| cal-fma-pc-iii-walking-the-wall | Walking The Wall | P C III | Free Music Archive | 1,200 s | CC BY 4.0 | [개별 FMA track page](https://freemusicarchive.org/music/P_C_III/music-for-a-weary-world-vol-3/walking-the-wall/), 2023-02-24 공개, AI generated 표시 No; 기존 FMA-small 기간 밖 | Ambient Electronic/Ambient Instrumental (FMA metadata) |
| cal-fma-hotham-get-free | Get Free | Hotham | Free Music Archive | 113 s | CC BY 4.0 | [개별 FMA track page](https://freemusicarchive.org/music/hotham/single/get-free/), 2023-12-22 공개, AI generated 표시 No; 기존 FMA-small 기간 밖 | Electronic/Dance/Chill-out, Instrumental (FMA metadata) |
| cal-commons-alexander-countdown | Countdown | Alexander Nakarada | Wikimedia Commons | 254.3445 s | CC BY 4.0 | [개별 Commons file page](https://commons.wikimedia.org/wiki/File:Alexander_Nakarada_-_Countdown_%28cc-by%29_%28filmmusic%29.mp3), Filmmusic.io source/artist 및 attribution 확인 | Cinematic/ambient, suspenseful/intense (file description/categories) |
| cal-commons-alexander-jolly-good-captain | Jolly Good, Captain | Alexander Nakarada | Wikimedia Commons | 124.7608 s | CC BY 4.0 | [개별 Commons file page](https://commons.wikimedia.org/wiki/File:Alexander_Nakarada_-_Jolly_Good%2C_Captain_%28cc-by%29_%28filmmusic.io%29.mp3), Filmmusic.io source/artist 및 attribution 확인 | Cinematic/adventure (file categories); cheerful pirate-music description |
| cal-commons-audionautix-intense-suspense | Intense Suspense | Jason Shaw | Wikimedia Commons | 93 s | CC BY 3.0 | [개별 Commons file page](https://commons.wikimedia.org/wiki/File:Audionautix-com-ccby-intensesuspense.mp3), audionautix.com source; required credit “music by audionautix.com” | Soundtrack; Suspenseful/Intense/Driving; Medium tempo (source metadata) |
| cal-commons-sascha-ende-i-feel-it | I Feel It (instrumental) | Sascha Ende | Wikimedia Commons | 331 s | CC BY 4.0 | [개별 Commons file page](https://commons.wikimedia.org/wiki/File:Sascha_Ende_-_I_Feel_It_%28instrumental%29_%28cc-by%29_%28filmmusic%29.ogg), Filmmusic.io source/artist; attribution 필요 | Happy/Uplifting/Relaxed/Atmospheric/Festive/Summertime (file description); instrumental (title) |
| cal-commons-musiclfiles-warm-sunset | Warm Sunset | MusicLFiles | Wikimedia Commons | 224 s | CC BY 4.0 | [개별 Commons file page](https://commons.wikimedia.org/wiki/File:Warm_Sunset_by_MusicLFiles.ogg), Filmmusic.io source/artist; attribution 필요 | Acoustic folk; nostalgic/peaceful; instrumental (file description) |
| cal-commons-zero-project-moon-waltz | Moon waltz | zero-project | Wikimedia Commons | 241 s | CC BY 3.0 | [개별 Commons file page](https://commons.wikimedia.org/wiki/File:Zero-project_-_02_-_Moon_waltz.ogg), artist site source and license/credit statement; attribution to zero-project and website | Genre/mood and vocal status not separately asserted |
| cal-commons-paul-de-bra-vivaldi-spring | Vivaldi’s Spring, RV 269 — I. Allegro (Accordion Orchestra) | Paul De Bra | Wikimedia Commons | 190.92898 s | CC BY 4.0 | [개별 Commons file page](https://commons.wikimedia.org/wiki/File:Paul_De_Bra_-_Vivaldi%27s_Spring,_RV_269_-_I._Allegro_%28Accordion_Orchestra%29.ogg), recording author/source and file license shown on page | Classical; accordion orchestra (file title/metadata); vocal status unknown |
| cal-commons-scott-buckley-aurora | Aurora | Scott Buckley | Wikimedia Commons | 499 s | CC BY 4.0 | [개별 Commons file page](https://commons.wikimedia.org/wiki/File:Scott_Buckley_-_Aurora.mp3), author’s official library/source and explicit commercial-use-with-credit statement | Ambient; slow-moving synth and string orchestra (file description) |
| cal-fma-bfcmusic-luna-de-fuego | Luna de Fuego | BFCMUSIC | Free Music Archive | 111 s | CC BY 4.0 | [개별 FMA track page](https://freemusicarchive.org/music/bfcmusic/single/luna-de-fuego/), 2025-09-28 공개, CC BY 4.0 및 아티스트 credit 안내 | Flamenco/Latin (FMA metadata); `Instrumental: No`, vocal classification unknown |
| cal-commons-zero-project-missing | Missing | zero-project | Wikimedia Commons | 292 s | CC BY 4.0 | [개별 Commons file page](https://commons.wikimedia.org/wiki/File:Zero-project_-_Missing_(music).ogg) 및 [아티스트 공식 곡 페이지](https://zero-project.gr/music/tracks/missing/), 전체 길이와 CC BY 4.0 확인 | Soundtrack/piano (artist metadata); vocal status unknown |
| cal-ccmixter-orrisroot-alice-in-the-city | Alice In the City | Orrisroot | ccMixter | 210 s | CC BY 3.0 | [개별 ccMixter track page](https://ccmixter.org/files/orrisroot/43309), 완곡 길이·저작자·개별 라이선스 표시, 별도 source dependency 없음 | vocal/acappella (ccMixter tags) |
| cal-ccmixter-pitx-long-winter | Long Winter | Pitx | ccMixter | 101 s | CC BY 3.0 | [개별 ccMixter track page](https://ccmixter.org/files/Pitx/19388), 저작자가 acoustic guitar 연주 및 배경음을 설명, 개별 라이선스 표시, 별도 source dependency 없음 | acoustic/ambient/instrumental (ccMixter tags) |
| cal-ccmixter-aussensiter-guitars-bass-a-minor | Guitars & Bass in A-Minor (Instrumental) | Aussens@iter | ccMixter | 83 s | CC BY 3.0 | [개별 ccMixter track page](https://ccmixter.org/files/tobias_weber/49850), 저작자가 기타·베이스 연주와 장비를 명시, 개별 라이선스 표시, 별도 source dependency 없음 | acoustic/experimental/downtempo/instrumental (ccMixter tags) |
| cal-ccmixter-robbero-summer-house | Robbero - Summer house | Robbero | ccMixter | 198 s | CC BY 3.0 | [개별 ccMixter track page](https://ccmixter.org/files/Robbero/46630), 완곡 길이·저작자·개별 라이선스와 오디오 파일 형식 표시, 별도 source dependency 없음 | disco (ccMixter tag); vocal status unknown |
| cal-ccmixter-mark-neumann-summer-trip | Summer Trip | Mark Neumann (Tigoolio) | ccMixter | 303 s | CC BY 3.0 | [개별 ccMixter track page](https://ccmixter.org/files/Tigoolio/46263), 완곡 길이·저작자·개별 라이선스 및 MP3/audio 표시, `Uses samples from` source dependency 없음 | trip-hop/electronic/ambient/downtempo/instrumental (ccMixter tags) |
| cal-ccmixter-unreal-dm-free-music-and-free-beer | Free Music and Free Beer? | unreal_dm (feat. Admiral Bob, SackJo22) | ccMixter | 173 s | CC BY 3.0 | [개별 ccMixter track page](https://ccmixter.org/files/unreal_dm/38156), remix source 2곡의 개별 CC BY 3.0 페이지도 확인 | blues/jump blues; male/female vocals (ccMixter description/tags) |

ccMixter 후보 attribution은 트랙 제목·페이지상의 저작자명·개별 track URL·CC BY 3.0 license URL 및 중앙 60초 구간 준비 시 변경 사실을 포함한다. ccMixter 약관은 업로더가 권리 보유 또는 게시·라이선스 권한을 보증한다고 명시하지만, 플랫폼은 제3자 권리 침해 부재를 보증하지 않는다. 이번 채택 후보 4곡은 track page에 `Uses samples from` source가 없고, 가능한 경우 저작자의 직접 연주 설명도 확인했다. 따라서 권리 근거는 각 개별 페이지의 표시와 업로더 권리 진술에 한정한다. 실제 파일은 취득하지 않았으며 다운로드·decode/hash는 미수행이다.

## 출처별 현황과 부족분 — 이번 확장 전 baseline

| 출처 | 후보 수 | 목표 상한 | 비고 |
|---|---:|---:|---|
| 기존 Incompetech | 2 | 기존 확정 2 | Kevin MacLeod 상한 도달, 추가 불가 |
| 새 FMA 전체 트랙 | 3 | 최대 24 | 개별 전체 트랙 페이지에서 길이·license 확인. 신규 곡은 2025년 공개되어 기존 FMA-small 기간과 겹치지 않음 |
| Wikimedia Commons | 9 | 최대 24 | 개별 파일 길이·저작자·출처·license/attribution 확인, license-review 경고 페이지 제외 |
| ccMixter | 6 | 별도 상한 없음 | track별 CC BY 3.0, 60초 이상, 검토 가능한 source dependency/license chain 조건 충족 |
| 합계 | 20/50 | — | 위 표 작성 당시 30곡 부족; 이후 확장 batch에서 14곡을 추가 채택 |

## ccMixter 검토 batch

아래 10곡을 track page 기준으로 조사했다. `채택` 4곡만 manifest 후보 수에 포함한다. 페이지에 `preview` 또는 `sample` 성격이 있거나, sample/remix source chain·NC 제한이 확인된 곡은 후보에 추가하지 않았다. 전체 길이·오디오 링크는 사이트 metadata이며 실제 파일 decode 결과가 아니다.

| 제목 / 아티스트 | track URL | 길이 / 개별 라이선스 | attribution / remix·source | 완곡·권리 확인 | 결과 |
|---|---|---|---|---|---|
| Alice In the City / Orrisroot | [track](https://ccmixter.org/files/orrisroot/43309) | 3:30 / CC BY 3.0 | 페이지의 Attribution 3.0 및 credit 안내; `acappella` 표시, `Uses samples from` 없음 | 3:30 오디오 트랙으로 제공. source 의존 표시는 없으나, 플랫폼 약관상 업로더 권리 진술에 근거 | **채택** — 60초 이상, 개별 BY, 별도 source chain 없음 |
| Long Winter / Pitx | [track](https://ccmixter.org/files/Pitx/19388) | 1:41 / CC BY 3.0 | 페이지의 Attribution 3.0 및 credit 안내; 설명은 저작자의 acoustic guitar 연주와 kitchen sounds를 언급, `Uses samples from` 없음 | MP3/오디오 링크와 길이 표시. 사용된 source 트랙 표시 없음 | **채택** — 독립 트랙으로 제공되고 권리 진술/개별 BY 확인 |
| Guitars & Bass in A-Minor (Instrumental) / Aussens@iter | [track](https://ccmixter.org/files/tobias_weber/49850) | 1:23 / CC BY 3.0 | 페이지가 transform 및 상업적 이용을 credit 조건으로 허용한다고 설명; 저작자가 직접 연주한 악기 설명, `Uses samples from` 없음 | MP3/오디오 링크, full track 길이; source dependency 없음 | **채택** — 직접 연주 설명과 개별 BY가 명확 |
| Robbero - Summer house / Robbero | [track](https://ccmixter.org/files/Robbero/46630) | 3:18 / CC BY 3.0 | 페이지의 Attribution 3.0 및 credit 안내; `Uses samples from` 없음 | MP3/오디오 링크와 길이 표시; 업로더 트랙과 개별 license 확인 | **채택** — source dependency 표시가 없고 BY 조건 확인 |
| Lisa’s Lullaby / Radioontheshelf feat. Lisa DeBenedictis | [track](https://ccmixter.org/files/Radioontheshelf/66469) | 5:02 / CC BY 3.0 | attribution 조건 표시; `Traveling Lights` sample 사용 | source 곡/녹음의 권리 연결을 이번 검토에서 확정하지 못함 | **보류** — source dependency 권리 확인 필요 |
| Summer Dance / Pitx | [track](https://ccmixter.org/files/Pitx/21393) | 1:17 / CC BY-NC 3.0 | credit 조건; folk/guitar tag | 완곡 오디오로 표시되나 NC 조건 | **보류** — 프로젝트의 향후 사용 범위와 NC 양립성 확인 필요 |
| Not too quiet / zikweb | [track](https://ccmixter.org/files/zikweb/17624) | 6:31 / CC BY 3.0 | attribution 표시; `too quiet (piano)` sample 사용 | sample 페이지는 oldDog가 narva9 곡에서 만든 piano track이라고 설명하여 추가 권리 chain이 있음 | **제외** — 원 녹음물까지 권리 chain 확인 불충분 |
| Her Silence / @nop | [track](https://ccmixter.org/files/Lancefield/63833) | 3:49 / CC BY-NC 3.0 | credit 조건; 여러 ccMixter 연주자 cello 및 source sample을 결합한 remix | sample 출처 다수, NC 조건 | **제외** — 복수 source 권리 확인과 NC 범위 불확실 |
| Bluenotation / Ezra Skull feat. airtone | [track](https://ccmixter.org/files/Haskel/64588) | 3:49 / CC BY 3.0 | attribution 표시; `bluenotes` by airtone sample | upstream sample 권리는 별도 확인이 필요 | **제외** — source track 권리 연결 미검증 |
| All The Same Patterns / Apoxode feat. spinningmerkaba 외 | [track](https://ccmixter.org/files/Apoxode/67882) | 4:25 / CC BY 4.0 | attribution 표시; 5명의 contributor/sample source 명시 | full track이나 여러 source/stem의 권리·attribution chain이 복잡함 | **제외** — source chain 복잡, cohort별 권리 검토 부담 큼 |

ccMixter 약관은 track별 라이선스 확인과 attribution을 요구하고, 권리 없는 곡을 올릴 수 없다고 규정한다. 동시에 ccMixter는 각 자료의 제3자 권리 비침해를 보증하지 않는다. 그러므로 위 채택은 페이지의 권리 표시와 source dependency 공개 상태를 확인한 후보 선정이며, 원본 파일 취득·배포 권리의 법률 의견이나 decode 검증을 뜻하지 않는다.

## 주요 탈락 및 보류 사유

- 기존 FMA-small/30초 Historical 자료와 동일할 가능성을 개별 track ID로 배제하지 못한 오래된 FMA 곡은 후보에 넣지 않았다. 기존 30초 자료 자체와 Phase A 6곡도 사용하지 않았다.
- Wikimedia Commons에서 `License review needed (audio)`가 표시된 FMA 미러 및 Scott Buckley 파일, author/source 권리 근거가 불명확한 파일, 합성 MIDI 렌더링은 제외했다. 예: Meydän/Insomnia, Zeu/Rain, Scott Buckley/Sleep는 페이지에 license review 경고가 있어 이번 선정 수에 넣지 않았다.
- FMA의 개별 권리/길이를 현재 공식 페이지에서 함께 검증하지 못한 후보, NonCommercial 제한 또는 full-track 여부가 명확하지 않은 항목도 추가하지 않았다.
- 50곡 목표를 맞추려고 같은 artist를 더 넣거나 license/duration 근거가 약한 트랙을 추정해 추가하지 않았다.

## 후보 선정 당시 다음 검증 — Historical

1. 당시에는 개별 공식 track/file page에서 full-track 길이·녹음물 license·source/artist/attribution을 확인할 수 있는 추가 후보만 선정할 계획이었다. 현재 후보 선정은 완료됐으며 이 항목은 과거 절차 기록이다. ccMixter는 source dependency가 없는 독립 트랙을 우선하고 FMA는 FMA-small 중복을 track identity 기준으로 배제하도록 했다.
2. 승인된 취득 절차가 시작된 뒤 원본 SHA-256, decoder duration, sample rate, channel, codec을 실제 파일에서 측정한다. catalog duration을 decoded duration으로 간주하지 않는다.
3. 이 후보 기록에는 제공자 metadata만 사용했고 manual mood/tempo label은 만들지 않았다. Manifest schema는 genre/mood 값과 source provenance를 지원하지만 tempo·acoustic/electronic field는 정의하지 않는다. 향후 label을 추가할 경우 제공자 metadata와 manual label을 구분해 기록한다.
4. 해당 batch 기록 당시의 후보 수는 34/50으로, 그 시점에서는 candidate selection이 미완료였다. 이후 manifest-only 재검증과 마지막 대체 후보 검토를 거쳐 앞부분의 현재 상태와 아래 최종 집계에 기록한 PASS 50곡을 확정했다.

## ccMixter 검토 batch 2

이전 batch의 10곡은 다시 검토하지 않았다. 아래 10곡의 개별 페이지와, remix의 경우 페이지가 연결한 source 페이지를 확인했다. 채택은 2곡이며, 그 외에는 source 권리 chain 미확인 또는 완곡/독립 트랙 여부가 충분히 분명하지 않아 manifest에 넣지 않았다. 길이는 페이지 표기값이며 실제 파일 decode 값이 아니다.

| 제목 / 아티스트 | track URL | 길이 / license / attribution | full track 및 source 확인 | 결과와 이유 |
|---|---|---|---|---|
| Summer Trip / Mark Neumann (Tigoolio) | [track](https://ccmixter.org/files/Tigoolio/46263) | 5:03 / CC BY 3.0 / ccMixter attribution 안내와 저작자·track URL·license 링크를 기록 | 페이지에 MP3/audio와 전체 길이가 있고 `Uses samples from`은 없다. `sample` tag와 downstream `Samples are used in`은 있으나 업스트림 source dependency 표시는 없다. 완성된 instrumental 트랙으로 제공 | **채택** — full-length audio와 개별 BY license 확인. sample tag는 있으므로 실제 취득 후 파일이 preview/sample 조각이 아닌지 재확인 |
| Free Music and Free Beer? / unreal_dm feat. Admiral Bob, SackJo22 | [track](https://ccmixter.org/files/unreal_dm/38156) | 2:53 / CC BY 3.0 / 3명의 기여자, track URL, CC BY link를 attribution에 포함 | 페이지가 두 source를 연결한다: [Free Music Free Beer Background Vocals — SackJo22](https://ccmixter.org/files/SackJo22/38099), 0:24 stem, CC BY 3.0; [Free Music and Free Beer — Admiral Bob](https://ccmixter.org/files/admiralbob77/38104), 2:48, CC BY 3.0. 최종 페이지도 CC BY 3.0이고 full MP3/audio로 제공 | **채택** — source chain과 양립 가능한 CC BY 3.0 표시 확인; attribution에 원 기여자 포함 |
| Mr. Wozzie / Robbero | [track](https://ccmixter.org/files/Robbero/51883) | 3:29 / CC BY 3.0 / 개별 attribution 표기 | `Uses samples from`에 Mysterium 및 Nocturnal이 표시됨. Mysterium 페이지는 CC BY 3.0이나 washing-machine sample과 별도 vocal을 포함하고, 두 번째 source의 권리 chain을 이번 검토에서 완결하지 못함. 기존 cohort의 Robbero는 이미 1곡 | **제외** — 복수 upstream/source chain 미완결 |
| Mellow / Darkroom feat. Admiral Bob | [track](https://ccmixter.org/files/mactonite/14897) | 4:27 / CC BY 3.0 / 페이지 attribution 표기 | `Uses samples from`에 TF Mellow Groovi... by Admiral Bob. source 상세 페이지/license를 확인하지 못함 | **보류** — source license와 사용 조건 추가 확인 필요 |
| Homework / gurdonark | [track](https://ccmixter.org/files/gurdonark/29021) | 2:55 / CC BY 3.0 / 페이지 attribution 표기 | `Uses samples from`에 drum beats 20101015 by Nickleus. source license 확인을 완료하지 못함 | **제외** — upstream 녹음 권리 미확인 |
| Eternal Loop of Glue - Instrumental / Wired Ant | [track](https://ccmixter.org/files/Wired_Ant/39945) | 3:22 / CC BY 3.0 / 페이지 attribution 표기 | `sample`, `loops` tags와 loop/sample 목적 설명이 있고 upstream dependency 섹션은 없음 | **제외** — 독립된 완곡보다 sample/loop asset으로 분류될 가능성이 있어 full-track 성격 불충분 |
| Outside / Admiral Bob | [track](https://ccmixter.org/files/admiralbob77/61421) | 3:44 / CC BY 3.0 / 페이지 attribution 표기 | audio/MP3와 stems ZIP이 있으나 명시적으로 `preview` tag가 표시됨. source dependency 섹션은 없음 | **보류** — 별도 full master와 preview의 관계를 확인하기 전 사용하지 않음 |
| From Gurd To Nark / Siobhan Dakay feat. Gurdonark | [track](https://ccmixter.org/files/SiobhanD/64324) | 5:19 / CC BY 3.0 / 페이지 attribution 표기 | Onyx Inertia Intro, Onyx inertia more..., Eyes Open 및 별도 Freesound bird recording을 사용했다고 명시; 다중 source chain | **제외** — source recordings와 attribution 관계가 복잡하고 전체 권리 chain을 이 batch에서 닫지 못함 |
| Longing for Tumbleweeds / Admiral Bob feat. Snowflake | [track](https://ccmixter.org/files/admiralbob77/33347) | 1:55 / CC BY 3.0 / 페이지 attribution 표기 | `Uses samples from`에 Longing by Madam Snowflake가 표시됨. 이번 검토 범위에서 원 source 조건을 완결하지 못함 | **제외** — upstream source license 검증 불충분 |
| Harmony / wellman feat. Snowflake, Pitx | [track](https://ccmixter.org/files/wellman/24847) | 3:49 / CC BY 3.0 / 페이지 attribution 표기 | 설명상 Snowflake acappella와 Pitx 기타를 사용하고 `Uses samples from`에 Harmony by Madam Snowflake가 표시됨. 이 source 녹음의 권리 chain을 완결하지 못함 | **제외** — upstream source 권리 미완결 |

ccMixter 페이지의 track license는 개별 업로더의 표시 및 권리 진술을 근거로 기록했다. ccMixter 자체도 업로더 권리 진술과 별개로 제3자 권리 비침해를 보증하지 않으므로, 후보 채택은 독립적인 법률 검토를 뜻하지 않는다. 다운로드·decode·SHA-256은 하지 않았다.
## 후보 확장 batch — Wikimedia Commons, FMA, ccMixter

이번 batch에서 기존 20곡과 중복되지 않는 개별 페이지 27개를 검토했다. Wikimedia Commons 11곡과 FMA 3곡을 추가 채택했고, FMA 후보 3곡과 ccMixter 10곡은 채택하지 않았다. 해당 batch 직후 당시 cohort는 34/50으로 16곡이 부족했다. source_catalog_duration은 제공자 페이지의 표기값으로 실제 decoder 측정값이 아니다. 모든 채택 곡은 아직 다운로드·decode·SHA-256 측정을 하지 않았다.

### 추가 채택

| sample_id | 제목 / artist | 개별 source page | 길이 / license / attribution | 확인 내용 |
|---|---|---|---|---|
| cal-commons-rafael-krux-lights-creepy-ambient-suspense | Lights - Creepy Ambient Suspense / Rafael Krux | [Commons file](https://commons.wikimedia.org/wiki/File:Rafael_Krux_-_Lights_-_Creepy_Ambient_Suspense_(cc-by)_(filmmusic).mp3) | 2:12 / CC BY 4.0 / Rafael Krux·곡·license URL 표시 | Filmmusic.io source/author, mysterious and spooky 설명, 전체 MP3 |
| cal-commons-rafael-krux-epic-trailer | Epic Trailer / Rafael Krux | [Commons file](https://commons.wikimedia.org/wiki/File:Epic_Trailer_by_Rafael_Krux.ogg) | 2:09 / CC BY 4.0 / Rafael Krux·곡·license URL 표시 | Filmmusic.io source/author, 전체 Ogg |
| cal-commons-luca-fraula-darkness | Darkness / Luca Fraula | [Commons file](https://commons.wikimedia.org/wiki/File:Luca_Fraula_-_Darkness_(cc-by)_(filmmusic.io).ogg) | 2:29 / CC BY 4.0 / Luca Fraula·곡·license URL 표시 | Filmmusic.io source/author, 전체 Ogg; 설명란이 비어 있어 mood는 unknown |
| cal-commons-dj-striden-level-three | Level Three / DJ Striden | [Commons file](https://commons.wikimedia.org/wiki/File:DJ_Striden_-_Level_Three.ogg), [원출처](https://www.newgrounds.com/audio/listen/645415) | 원본 파일 3:36, 페이지 duration 3:37 / CC BY 4.0 / DJ Striden | Newgrounds 원출처와 저작자 확인. 페이지는 2025년 저작자의 CC BY 변경을 명시하며 1초 길이 표기 차이는 60초 기준에 영향 없음 |
| cal-commons-thomasbrunkard-broken-hands-improvisation | Broken Hands Improvisation / Thomasbrunkard | [Commons file](https://commons.wikimedia.org/wiki/File:Broken_Hands_Improvisation.ogg) | 2:43 / CC BY 4.0 / uploader 권리자 attribution | own work, 2014 Guitarviol 즉흥 연주 녹음이라고 명시된 실제 연주물 |
| cal-commons-frank-schroeter-1984 | 1984 / Frank Schröter (page author spelling: Frank Schroeter) | [Commons file](https://commons.wikimedia.org/wiki/File:1984_by_Frank_Schroeter.ogg) | 3:20 / CC BY 4.0 / Frank Schroeter·license URL 표시 | Filmmusic.io source/author, 설명과 category에 synthwave |
| cal-commons-frank-schroeter-medieval-dream | Medieval Dream / Frank Schröter | [Commons file](https://commons.wikimedia.org/wiki/File:Medieval_Dream_by_Frank_Schr%C3%B6ter.ogg) | 2:21 / CC BY 4.0 / Frank Schröter·license URL 표시 | Filmmusic.io source/author, 설명에 quiet medieval music |
| cal-commons-phat-sounds-slipping-into-madness | Slipping Into Madness / Phat Sounds | [Commons file](https://commons.wikimedia.org/wiki/File:Slipping_Into_Madness_by_Phat_Sounds.ogg) | 2:13 / CC BY 4.0 / Phat Sounds·license URL 표시 | Filmmusic.io file, 설명에 mystery/detective style |
| cal-commons-jason-shaw-autumn-sunset | Autumn Sunset / Jason Shaw | [Commons file](https://commons.wikimedia.org/wiki/File:Audionautix-com-ccby-autumnsunset.mp3) | 96.3215초 / CC BY 3.0 / 필수 credit: “music by audionautix.com” | Audionautix source, Jason Shaw author, acoustic·slow·calming·relaxing metadata 및 signed release form 안내. 기존 Jason Shaw 1곡과 합계 2곡 |
| cal-commons-musiclfiles-march-final-battle | The March Of The Final Battle / MusicLFiles | [Commons file](https://commons.wikimedia.org/wiki/File:The_March_Of_The_Final_Battle_by_MusicLFiles.ogg) | 2:15 / CC BY 4.0 / MusicLFiles·license URL 표시 | 전체 Ogg; 설명에서 orchestral instrumental classical cinematic music라고 명시. 기존 MusicLFiles 1곡과 합계 2곡 |
| cal-commons-sascha-ende-the-big-adventure | The Big Adventure / Sascha Ende | [Commons file](https://commons.wikimedia.org/wiki/File:Sascha_Ende_-_The_Big_Adventure_(cc-by)_(filmmusic).ogg) | 3:04 / CC BY 4.0 / Sascha Ende·license URL 표시 | Filmmusic.io source/author, 전체 Ogg. 기존 Sascha Ende 1곡과 합계 2곡 |
| cal-fma-doctor-turtle-are-you-there-invisible-woman | Are You There, Invisible Woman? / Doctor Turtle | [FMA track](https://freemusicarchive.org/music/Doctor_Turtle/are-you-there-invisible-woman/are-you-there-invisible-woman/) | 3:26 / CC BY 4.0 / 개별 track page | 저작자가 기타 instrumentals LP의 58곡 중 개별 다운로드 가능 곡이라고 설명. Folk/Instrumental/Acoustic, Instrumental Yes, AI generated No, 2023 공개 |
| cal-fma-1000-handz-kyoto | Kyoto / 1000 Handz | [FMA track](https://freemusicarchive.org/index.php/music/1000-handz/cc-by-free-to-use-melodic-rap-instrumentals/kyoto-2/) | 2:36 / CC BY 4.0 / “Please credit 1000 Handz” | 개별 track page에서 license, 길이, artist, genre, Instrumental Yes, AI generated No 확인; 2025 공개 |
| cal-fma-jmhbm-christmas-morning-hs23 | Christmas Morning (HS23) / JMHBM (Johnathon M. Horner / Beat Mekanik) | [FMA track](https://freemusicarchive.org/music/beat-mekanik/fma-christmas-2023/christmas-morning-hs23/) | 2:33 / CC BY 4.0 / track credit에 Horner·Beat Mekanik | 개별 track page에서 길이·license·원 창작물·instrumental·AI generated No 확인; FMA creator 표기는 JMHBM, 2023 공개 |

위 추가곡의 genre/mood 및 instrumental 표시는 source page에 적힌 값만 기록했다. 페이지에 근거가 없는 vocal/mood/tempo는 unknown으로 두었고, 별도의 manual listening label은 만들지 않았다. Commons의 녹음물 license 표시를 확인했으며 작곡물의 Public Domain만을 녹음물 권리 근거로 삼지 않았다. CC BY의 attribution은 manifest에 곡·저작자·source·license URL을 기록하고, 취득 후 중앙 60초 발췌 변경 사실을 표시하도록 작성했다.

### 검토했으나 추가하지 않은 후보

| 제목 / artist | 개별 페이지 | 길이 / 표시 license / attribution | 판정 |
|---|---|---|---|
| Potential / 1000 Handz | [FMA track](https://freemusicarchive.org/music/1000-handz/cc-by-free-to-use-ambientbackground-scores/potential/) | 9:35 / CC BY 4.0 / 1000 Handz 및 곡명 credit | **미채택** — 개별 track 조건은 충족하지만 Kyoto와 같은 신규 artist여서 이번 확장에서는 artist 다양성을 우선 |
| Contact / 1000 Handz | [FMA track](https://freemusicarchive.org/music/1000-handz/cc-by-free-to-use-electronicgaming-instrumentals/contact-2/) | 3:24 / CC BY 4.0 / 1000 Handz credit | **미채택** — 개별 track 조건은 충족하지만 같은 artist의 후보를 늘리기보다 새 artist를 우선 |
| Water Music from the Handel Show / The United States Army Old Guard Fife and Drum Corps | [FMA track](https://freemusicarchive.org/music/The_United_States_Army_Old_Guard_Fife_and_Drum_Corps/Celebrating_50_Years/13_1793) | 1:48 / Public Domain Mark 1.0 표기 | **보류** — 군악대가 녹음한 상용 CD compilation의 개별 페이지는 찾았으나 실제 녹음물에 대한 권리 허가 근거가 페이지에서 명확하지 않다. Handel 작곡의 지위와 녹음물 권리를 동일시하지 않음 |
| Can't Not See 140 / Apoxode | [ccMixter track](https://ccmixter.org/files/Apoxode/59592) | 4:22 / CC BY-NC-SA 3.0 / attribution 표기 | **보류** — CC BY-NC-SA 제한과 다수 sample dependency; 이번 cohort 확정 후보에는 넣지 않음 |
| Dream On This Side (instrumental) / Ivan Chew | [ccMixter track](https://ccmixter.org/files/ramblinglibrarian/35789) | 5:18 / CC BY 3.0 / attribution 표기 | **제외** — 여러 upstream track을 사용하며 원 source 권리 chain을 완결하지 못함 |
| Chords For David / Pitx | [ccMixter track](https://ccmixter.org/files/pitx/30638) | 1:37 / CC BY 3.0 / attribution 표기 | **제외** — spinningmerkaba source track의 license 연결 미검증 |
| Somebody Help Me / CSoul | [ccMixter track](https://ccmixter.org/files/CSoul/32913) | 7:04 / CC BY 3.0 / attribution 표기 | **제외** — Admiral Bob 및 Down With Ben source 권리 연결 미완결 |
| Time Has Come / SackJo22 | [ccMixter track](https://ccmixter.org/files/sackjo22/29673) | 3:22 / CC BY 3.0 / attribution 표기 | **제외** — unreal_dm source track의 관계와 조건을 완결하지 못함 |
| Longing for Tumbleweeds / Admiral Bob | [ccMixter track](https://ccmixter.org/files/admiralbob77/33347) | 1:55 / CC BY 3.0 / attribution 표기 | **제외** — Madam Snowflake source recording license 검증 미완결 |
| Secret Beers (Andy's PT Punch Mix) / Andrew Wainwright | [ccMixter track](https://ccmixter.org/files/andrewwainwright/55972) | 3:53 / CC BY 3.0 / attribution 표기 | **제외** — Thespinwires source track 권리 chain 확인 부족 |
| Memory loss / robwalkerpoet | [ccMixter track](https://ccmixter.org/files/robwalkerpoet/38593) | 4:03 / CC BY 3.0 / attribution 표기 | **제외** — Gurdonark 및 TheDICE sample의 source 권리 미확인 |
| Kaleidoscopic Visions Dubby Mix / coruscate | [ccMixter track](https://ccmixter.org/files/Coruscate/41032) | 3:06 / CC BY 3.0 / attribution 표기 | **제외** — 여러 source dependency의 권리·attribution chain 미완결 |
| Guerilla Gardening / Fex | [ccMixter track](https://ccmixter.org/files/Fex/62023) | 4:55 / CC BY-NC 3.0 / attribution 표기 | **보류** — CC BY-NC 제한과 다수 source dependency; 이번 cohort 확정 후보에는 넣지 않음 |

ccMixter는 위 10개를 조사했으나 이번 batch의 새 채택은 0곡이다. 페이지가 표시하는 최종 track license만으로 source recording 권리 chain을 대신하지 않았다. FMA의 Potential과 Contact는 적격한 개별 페이지를 확인했지만 artist당 1곡 우선 원칙에 따라 미채택했다. Water Music은 녹음물 권리 근거가 불명확해 보류했고, CC BY-NC 계열 ccMixter 2곡도 사용자 기준에 따라 보류했다. ccMixter 나머지 8곡은 source chain 또는 완곡성 근거 부족으로 제외했다. 보류·미채택·제외 곡은 manifest에 넣지 않았다.

기존 FMA-small/30초 Historical 자료와 Phase A 6곡은 이번에도 사용하지 않았다. Audio 취득, decode, SHA-256, prepared segment, MSCLAP, cosine, listening evaluation은 수행하지 않았다.

## manifest-only 16곡 source page 재검증

이 batch는 이미 manifest에 있으나 앞선 후보 검토 목록에는 없던 16곡만 재검토했다. 아래 판정은 각 개별 FMA track page 또는 Wikimedia Commons recording file page의 현재 표시를 기준으로 한다. FMA page 직접 열기는 HTTP 403으로 차단되어, 정확히 같은 개별 페이지의 검색 색인에 표시된 원문 metadata를 확인했다. 페이지 표기 길이는 실제 파일 decode 결과가 아니다. Audio 다운로드·decode·SHA-256은 수행하지 않았다.

### PASS — 정식 후보 반영 (15곡)

| sample_id | 제목 / artist | 개별 source page | 표기 길이 / license / attribution | 검증 근거 및 metadata 메모 |
|---|---|---|---|---|
| cal-fma-shane-ivers-sailor-vee | Sailor Vee / Shane Ivers | [FMA track](https://freemusicarchive.org/music/shane-ivers/single/sailor-vee/) | 3:54 / CC BY 4.0 / 페이지가 곡·artist credit을 안내 | 개별 track, 2026-04-12 공개, 여성 vocal 설명. Shane Ivers 총 2곡 |
| cal-fma-shane-ivers-woah | WOAH / Shane Ivers | [FMA track](https://freemusicarchive.org/music/shane-ivers/single/woah-3/) | 3:14 / CC BY 4.0 / “Music: WOAH by Shane Ivers” credit 안내 | 개별 track, 2026-04-12 공개, AI generated No. robotic vocal sample 설명은 있으나 page의 Instrumental Yes와 함께 표시되어 vocal은 단정하지 않음. Shane Ivers 총 2곡 |
| cal-fma-1st-contact-wohin | Wohin / 1st Contact | [FMA track](https://freemusicarchive.org/music/1st-contact/single/wohin/) | 4:32 / CC BY 4.0 / 개별 track 및 creator 식별 | 개별 track, 2022-10-02 공개, 가사와 track 정보 표시 |
| cal-fma-maarten-schellekens-little-match-girl-2025-remix | The Little Match Girl (WITH LYRICS - 2025 Remix) / Maarten Schellekens | [FMA track](https://freemusicarchive.org/music/maarten-schellekens/christmas-2/the-little-match-girl-with-lyrics-2025-remix/) | 3:22 / CC BY 4.0 / 작가가 곡명과 본인 credit을 요청 | 작가 설명은 본인의 2021년 곡 remake이며 새 vocal/편곡이라고 밝힘. 제3자 source 의존 표시 없음 |
| cal-fma-serat-this-is-all | This Is All / Serat | [FMA track](https://freemusicarchive.org/music/serat/single/this-is-all/) | 4:31 / CC BY 4.0 / 개별 track 및 creator 식별 | 2021-06-10 공개, AI generated No. vocal/instrumental 장르 tag가 섞여 있어 vocal 분류는 unknown 유지 |
| cal-fma-anthem-of-rain-adaptation | Adaptation / Anthem of Rain | [FMA track](https://freemusicarchive.org/music/anthem-of-rain/freedom/adaptation/) | 3:27 / CC BY 4.0 / 개별 track 및 creator 식별 | 2021-06-18 공개, AI generated No. 페이지의 전체 장르 metadata 및 Instrumental No 표기를 확인했다. Anthem of Rain 총 2곡 |
| cal-fma-anthem-of-rain-i-got-to-go-now | I Got To Go Now / Anthem of Rain | [FMA track](https://freemusicarchive.org/music/anthem-of-rain/freedom/i-got-to-go-now/) | 2:56 / CC BY 4.0 / 개별 track 및 creator 식별 | 2021-06-12 공개, vocal 장르 tag와 Instrumental No, AI generated No. Anthem of Rain 총 2곡 |
| cal-fma-nexto-pretend | Pretend - Nexto.mp3 / Nexto | [FMA track](https://freemusicarchive.org/music/nexto-3/single/pretend-nextomp3/) | 2:33 / CC BY 4.0 / 개별 track 및 creator 식별 | 2023-02-17 공개, 설명과 가사에서 vocal song임을 확인, AI generated No |
| cal-fma-lee-rosevere-the-long-journey | The Long Journey / Lee Rosevere | [FMA track](https://freemusicarchive.org/music/lee-rosevere/music-for-podcasts-serious/the-long-journey/) | 1:39 / CC BY 4.0 / 개별 track 및 creator 식별 | 2024-03-24 공개, AI generated No. Instrumental No 표기와 Instrumental 장르 tag가 충돌하므로 vocal 분류 unknown 유지 |
| cal-fma-gagmesharkoff-tertiary | Tertiary / Gagmesharkoff | [FMA track](https://freemusicarchive.org/music/gagmesharkoff/single/tertiary/) | 3:16 / CC BY 4.0 / 개별 track 및 creator 식별 | 2023-03-20 공개, Instrumental Yes, AI generated No |
| cal-fma-aurosonmusic-hip-hop-street-motion | Hip Hop - Street Motion / AurosonMusic | [FMA track](https://freemusicarchive.org/music/aurosonmusic/single/hip-hop-street-motion/) | 2:34 / CC BY 4.0 / 개별 track 및 creator 식별 | 2026-08-04 공개, page는 instrumental style·Instrumental Yes·AI generated No 표시 |
| cal-fma-joseph-sacco-cloud-image | Cloud Image / Joseph Sacco | [FMA track](https://freemusicarchive.org/music/joseph-sacco/retro-active/cloud-image/) | 2:41 / CC BY 4.0 / 개별 track 및 creator 식별 | 2026-03-16 공개, AI generated No. FMA가 Instrumental No로 표시하지만 명시 vocal 근거가 없어 분류 unknown 유지 |
| cal-fma-xennial-compliance | Compliance / Xennial | [FMA track](https://freemusicarchive.org/music/xennial/jazz-x/compliance-2/) | 3:45 / CC BY 4.0 / 개별 track 및 creator 식별 | 2025-08-06 공개, page는 Instrumental 장르 tag와 Instrumental No를 함께 표시해 vocal 분류 unknown 유지 |
| cal-commons-scott-buckley-eyes-in-the-void | Eyes In The Void / Scott Buckley | [Commons file](https://commons.wikimedia.org/wiki/File:Scott_Buckley_-_Eyes_In_The_Void.oga) 및 [작가 공식 페이지](https://www.scottbuckley.com.au/library/eyes-in-the-void/) | 4:24 / CC BY 4.0 / 저작자·license·변경 표시 요구 확인 | 실제 Ogg FLAC 녹음 파일, 원출처 및 작곡자 Scott Buckley 확인, license-review 경고 없음. 기존 Scott Buckley와 합계 2곡 |
| cal-commons-migfus20-background-music | 609562 migfus20 background-music / Migfus20 | [Commons file](https://commons.wikimedia.org/wiki/File:609562_migfus20_background-music.ogg) 및 [Freesound 원출처](https://freesound.org/people/Migfus20/sounds/609562/) | 3:48 / CC BY 4.0 / “Migfus20 on Freesound.org”, license link, 변경 표시 요구 확인 | Commons page가 Freesound user Migfus20을 작곡자로 식별하고 개별 녹음 파일 및 license를 표시. license-review 경고 없음 |

모든 PASS 항목은 개별 page의 CC BY 조건으로 attribution을 유지하면서 비상업 제한이나 ND 없이 로컬 분석에 사용할 수 있는 후보로 판정했다. 이는 실제 다운로드·decode나 별도의 법률 의견을 뜻하지 않는다.

### 이전 재검증 당시 HOLD — 추가 확인 전 정식 후보 아님 (1곡)

| sample_id | 제목 / page author | 개별 source page | 표기 길이 / license / attribution | 보류 이유 |
|---|---|---|---|---|
| cal-commons-peakfiddler-wind-shakes-barley | The Wind that Shakes the Barley / YouTube user peakfiddler | [Commons file](https://commons.wikimedia.org/wiki/File:The_Wind_that_Shakes_the_Barley.ogg) | 1:08 / CC BY 3.0 / YouTube user `peakfiddler` attribution 명시 | 파일 페이지에서 제목·길이·license는 확인되지만 author는 uploader 계정만 표시되고 실제 performer/recording creator가 식별되지 않는다. full recording인지 단편인지도 현재 page 정보만으로 확정하지 않아 HOLD. |

재검증 당시 HOLD 1곡은 실제 performer/recording creator, recording rights 관계 및 완곡 여부가 충분히 확인되지 않았다. 따라서 정식 cohort에서 제외했다. 이 검토 이력은 보존하며, HOLD 파일은 최종 PASS manifest에 포함하지 않는다.

## 마지막 대체 후보 검증 — PASS (1곡)

| sample_id | 제목 / artist | 개별 source page | 표기 길이 / license / attribution | 검증 근거 |
|---|---|---|---|---|
| cal-fma-matthew-c-wright-housemaster-dormitory-3 | Lusurious Royalty Free Piano - “Housemaster of Dormitory 3” / Matthew C. Wright | [FMA 개별 track](https://freemusicarchive.org/index.php/music/matthew-c-wright/elegant-royalty-free-piano-artistry-in-motion/lusurious-royalty-free-piano-housemaster-of-dormitory-3/) | 3:00 / CC BY 4.0 / “Housemaster of Dormitory 3” by Matthew C. Wright (www.matthewcwright.com), Listen: https://ffm.to/artistry-in-motion | 개별 track page가 3:00 길이, artist, Instrumental Yes, AI generated? No를 표시한다. page의 권리 안내는 composition과 recordings 모두 CC BY 4.0이며 personal/commercial use 허용 및 credit을 명시한다. 기존 후보에 없는 artist다. Audio 취득·decode는 하지 않았다. |

이 대체 후보를 PASS로 추가하여 정식 후보는 50곡(Incompetech 2, 새 FMA 전체곡 20, Wikimedia Commons 22, ccMixter 6)이 되었다. HOLD 항목은 candidate review history에만 남기고 manifest에서 제거했다. manifest에는 PASS 50곡만 있으며 cohort 후보 선정은 완료됐다. Audio 취득·decode·prepared segment 생성 및 calibration 실험은 아직 완료되지 않았다.
