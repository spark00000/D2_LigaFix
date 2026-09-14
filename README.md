# D2 LigaFix

한글 문맥에서 프로그래밍 ligature(결합 문자)가 표시되지 않는 문제를 해결하는 Obsidian 플러그인입니다.

D2Coding에서는 `->`, `=>`, `!=`, `<=`, `>=` 같은 programming ligature가 지원됩니다. 하지만 Obsidian 기본 설정에서는 일부 헤딩에서 이 ligature가 표시되지 않습니다. 그 원인은 테마가 헤딩에 적용하는 `letter-spacing` 때문입니다. Chromium 렌더러는 `letter-spacing`이 0이 아닌 요소에서 OpenType ligature(feature `liga`)를 비활성화하기 때문입니다.

이 플러그인은 헤딩의 `letter-spacing`을 `normal`로 되돌려 헤딩에서도 ligature가 정상 렌더링되도록 하는 **CSS-only** 플러그인입니다.

## 기능

- 헤딩(H1–H6)의 `letter-spacing`을 `normal`로 보정하여 ligature가 비활성화되는 문제(`LIGA-CSS-001`)를 해결합니다.
- 본문은 테마 설정대로 유지되므로 나머지 스타일에는 영향을 주지 않습니다.
- JavaScript 런타임 로직이 없는 CSS-only 플러그인입니다.

## 설치

### 1. 플러그인 설치

Obsidian → Settings → Community plugins → Browse → **D2 LigaFix** 검색 → Install → Enable.

> 수동 설치는 `manifest.json`, `main.js`, `styles.css`를 `.obsidian/plugins/dcoding-ligafix/` 폴더에 복사하고 플러그인을 활성화합니다.

### 2. 폰트 설치 (필수)

이 플러그인은 폰트 파일을 포함하지 않으며 파생 폰트를 직접 배포하지 않습니다. NAVER 원본(D2Coding)에서 다운로드한 뒤 converter로 `D2_LigaFix` 파생 폰트를 만들어 설치합니다. 폰트가 설치되어 있어야 ligature가 표시됩니다.

1. [NAVER D2Coding 1.3.3](https://github.com/naver/d2-coding-font/releases/tag/VER1.3.3)에서 공식 릴리스 ZIP을 다운로드합니다.
   - 파일: `D2Coding-Ver1.3.3-*.zip`
2. 이 저장소의 `converter/` 폴더에서 아래 명령을 실행해 파생 폰트를 생성합니다 (Python 3.10+ 필요).
   ```bash
   pip install fonttools
   python converter/build_d2_ligafix.py --archive <다운로드한 ZIP 경로>
   ```
   - 생성 파일: `out/D2_LigaFix-Regular.ttf`, `out/D2_LigaFix-Bold.ttf`
   - converter는 공식 아카이브의 SHA-256과 업스트림 폰트의 Git blob 해시를 검증하고, 핵심 테이블(`glyf/loca/hmtx/cmap`)이 원본과 동일함을 확인한 뒤에만 폰트를 내보냅니다.
3. 생성한 TTF를 설치합니다. Windows: 더블클릭 → **설치**. macOS: Font Book에서 추가.
4. Obsidian → Settings → Appearance → **Fonts**에서 **Monospace** 폰트를 **D2_LigaFix**로 지정합니다.

### 3. 동작 확인

아래를 그대로 입력해 보세요. 모든 줄이 ligature(결합된 화살표 등)로 보여야 합니다.

```text
한 -> 한
한 1 -> 한
한 _ -> 한
a -> a
x => y
a != b
```

## 이 저장소와 converter

이 저장소는 Obsidian 플러그인과 함께 D2Coding ligature 폰트를 만드는 converter도 포함하고 있습니다.

- **converter** (`converter/`): D2Coding ligature 폰트에 `DFLT/dflt` `liga` route를 추가해 `D2_LigaFix-*.ttf`를 만드는 Python-only converter.
- **verify** (`converter/verify_structure.py`): 폰트 구조·해시를 검증하는 도구.

converter 사용 방법은 위 폰트 설치 가이드를 참고하세요. 플러그인 자체는 위의 설치 방법만으로 동작합니다.

## 라이선스

- 플러그인 코드: MIT — [LICENSE](LICENSE)
- 폰트(D2Coding 자체 및 D2_LigaFix 파생 폰트): SIL OFL 1.1 (D2Coding 원 저작자의 라이선스에 따름).
- Reserved Font Name(`D2Coding`)과의 충돌을 피하기 위해 파생 폰트는 `D2_LigaFix` family name을 사용합니다.