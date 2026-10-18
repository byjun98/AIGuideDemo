PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT (datetime('now')),
  note TEXT NOT NULL
);

INSERT OR IGNORE INTO schema_migrations (version, note)
VALUES (1, 'Relationship dialogue RAG schema v1');

CREATE TABLE IF NOT EXISTS characters (
  character_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  work_title TEXT NOT NULL,
  default_player_call TEXT NOT NULL,
  short_bible TEXT NOT NULL,
  safety_notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS source_documents (
  source_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  source_type TEXT NOT NULL CHECK (source_type IN (
    'official_game',
    'official_mmd',
    'official_site',
    'developer_interview',
    'wiki',
    'community',
    'manual_note',
    'private_transcript'
  )),
  url TEXT,
  language TEXT NOT NULL DEFAULT 'ko',
  rights_scope TEXT NOT NULL DEFAULT 'private_reference',
  reliability_tier TEXT NOT NULL CHECK (reliability_tier IN ('A', 'B', 'C', 'D')),
  notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS affection_bands (
  band_id TEXT PRIMARY KEY,
  min_affection INTEGER NOT NULL,
  max_affection INTEGER NOT NULL,
  label_ko TEXT NOT NULL,
  distance_rule TEXT NOT NULL,
  allowed_emotions TEXT NOT NULL,
  allowed_topics TEXT NOT NULL,
  max_line_chars INTEGER NOT NULL,
  CHECK (min_affection <= max_affection)
);

CREATE TABLE IF NOT EXISTS story_flags (
  flag_id TEXT PRIMARY KEY,
  label_ko TEXT NOT NULL,
  spoiler_level INTEGER NOT NULL DEFAULT 0,
  description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS scenes (
  scene_id TEXT PRIMARY KEY,
  label_ko TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS emotion_tags (
  emotion_tag TEXT PRIMARY KEY,
  label_ko TEXT NOT NULL,
  unity_hint TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS voice_tags (
  voice_tag TEXT PRIMARY KEY,
  label_ko TEXT NOT NULL,
  prompt_hint TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS motion_tags (
  motion_tag TEXT PRIMARY KEY,
  label_ko TEXT NOT NULL,
  unity_hint TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS dialogue_functions (
  function_id TEXT PRIMARY KEY,
  label_ko TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS raw_dialogue_lines (
  line_id TEXT PRIMARY KEY,
  character_id TEXT NOT NULL REFERENCES characters(character_id),
  speaker TEXT NOT NULL,
  raw_text TEXT NOT NULL,
  raw_text_sha256 TEXT NOT NULL,
  short_excerpt TEXT NOT NULL DEFAULT '',
  language TEXT NOT NULL DEFAULT 'ko',
  source_id TEXT NOT NULL REFERENCES source_documents(source_id),
  source_location TEXT NOT NULL DEFAULT '',
  scene_id TEXT REFERENCES scenes(scene_id),
  affection_band_id TEXT REFERENCES affection_bands(band_id),
  min_affection INTEGER,
  max_affection INTEGER,
  spoiler_level INTEGER NOT NULL DEFAULT 0,
  canon_tier TEXT NOT NULL CHECK (canon_tier IN ('canon', 'inferred', 'community', 'synthetic')),
  emotion_tag TEXT REFERENCES emotion_tags(emotion_tag),
  voice_tag TEXT REFERENCES voice_tags(voice_tag),
  motion_tag TEXT REFERENCES motion_tags(motion_tag),
  dialogue_function TEXT REFERENCES dialogue_functions(function_id),
  summary_kr TEXT NOT NULL DEFAULT '',
  voice_features_kr TEXT NOT NULL DEFAULT '',
  forbidden_notes TEXT NOT NULL DEFAULT '',
  is_verbatim_allowed INTEGER NOT NULL DEFAULT 0 CHECK (is_verbatim_allowed IN (0, 1)),
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS line_story_gates (
  line_id TEXT NOT NULL REFERENCES raw_dialogue_lines(line_id) ON DELETE CASCADE,
  flag_id TEXT NOT NULL REFERENCES story_flags(flag_id),
  gate_type TEXT NOT NULL CHECK (gate_type IN ('required', 'forbidden')),
  PRIMARY KEY (line_id, flag_id, gate_type)
);

CREATE TABLE IF NOT EXISTS rag_cards (
  card_id TEXT PRIMARY KEY,
  line_id TEXT REFERENCES raw_dialogue_lines(line_id) ON DELETE SET NULL,
  character_id TEXT NOT NULL REFERENCES characters(character_id),
  retrieval_text TEXT NOT NULL,
  facts_json TEXT NOT NULL DEFAULT '{}',
  voice_rules_json TEXT NOT NULL DEFAULT '{}',
  forbidden_json TEXT NOT NULL DEFAULT '{}',
  scene_id TEXT REFERENCES scenes(scene_id),
  affection_band_id TEXT REFERENCES affection_bands(band_id),
  min_affection INTEGER,
  max_affection INTEGER,
  spoiler_level INTEGER NOT NULL DEFAULT 0,
  emotion_tag TEXT REFERENCES emotion_tags(emotion_tag),
  voice_tag TEXT REFERENCES voice_tags(voice_tag),
  motion_tag TEXT REFERENCES motion_tags(motion_tag),
  dialogue_function TEXT REFERENCES dialogue_functions(function_id),
  embedding_model TEXT,
  embedding_dimension INTEGER,
  embedding_json TEXT,
  source_weight REAL NOT NULL DEFAULT 1.0,
  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rag_card_story_gates (
  card_id TEXT NOT NULL REFERENCES rag_cards(card_id) ON DELETE CASCADE,
  flag_id TEXT NOT NULL REFERENCES story_flags(flag_id),
  gate_type TEXT NOT NULL CHECK (gate_type IN ('required', 'forbidden')),
  PRIMARY KEY (card_id, flag_id, gate_type)
);

CREATE TABLE IF NOT EXISTS generated_dialogue_cache (
  generated_id TEXT PRIMARY KEY,
  character_id TEXT NOT NULL REFERENCES characters(character_id),
  state_json TEXT NOT NULL,
  retrieved_card_ids_json TEXT NOT NULL DEFAULT '[]',
  line TEXT NOT NULL CHECK (length(trim(line)) > 0),
  emotion_tag TEXT REFERENCES emotion_tags(emotion_tag),
  voice_tag TEXT REFERENCES voice_tags(voice_tag),
  motion_tag TEXT REFERENCES motion_tags(motion_tag),
  memory_update_json TEXT,
  risk TEXT NOT NULL CHECK (risk IN ('safe', 'needs_review', 'blocked')),
  style_score REAL,
  novelty_score REAL,
  spoiler_score REAL,
  accepted INTEGER NOT NULL DEFAULT 0 CHECK (accepted IN (0, 1)),
  model_name TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS retrieval_logs (
  log_id TEXT PRIMARY KEY,
  character_id TEXT NOT NULL REFERENCES characters(character_id),
  request_state_json TEXT NOT NULL,
  query_text TEXT NOT NULL,
  filter_json TEXT NOT NULL,
  candidate_card_ids_json TEXT NOT NULL DEFAULT '[]',
  selected_card_ids_json TEXT NOT NULL DEFAULT '[]',
  model_name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS qa_checks (
  qa_id TEXT PRIMARY KEY,
  generated_id TEXT REFERENCES generated_dialogue_cache(generated_id) ON DELETE CASCADE,
  check_type TEXT NOT NULL CHECK (check_type IN (
    'character_break',
    'spoiler_leak',
    'romance_level',
    'repetition',
    'json_contract',
    'gift_topic_alignment',
    'policy'
  )),
  severity INTEGER NOT NULL CHECK (severity BETWEEN 0 AND 3),
  result TEXT NOT NULL CHECK (result IN ('pass', 'warn', 'fail')),
  notes TEXT NOT NULL DEFAULT '',
  reviewer TEXT NOT NULL DEFAULT 'system',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_raw_lines_character ON raw_dialogue_lines(character_id);
CREATE INDEX IF NOT EXISTS idx_raw_lines_scene ON raw_dialogue_lines(scene_id);
CREATE INDEX IF NOT EXISTS idx_raw_lines_affection ON raw_dialogue_lines(affection_band_id, min_affection, max_affection);
CREATE INDEX IF NOT EXISTS idx_raw_lines_spoiler ON raw_dialogue_lines(spoiler_level);
CREATE INDEX IF NOT EXISTS idx_line_gates_flag ON line_story_gates(flag_id, gate_type);
CREATE INDEX IF NOT EXISTS idx_rag_cards_character ON rag_cards(character_id, is_active);
CREATE INDEX IF NOT EXISTS idx_rag_cards_scene ON rag_cards(scene_id);
CREATE INDEX IF NOT EXISTS idx_rag_cards_affection ON rag_cards(affection_band_id, min_affection, max_affection);
CREATE INDEX IF NOT EXISTS idx_rag_cards_spoiler ON rag_cards(spoiler_level);
CREATE INDEX IF NOT EXISTS idx_rag_card_gates_flag ON rag_card_story_gates(flag_id, gate_type);
CREATE INDEX IF NOT EXISTS idx_generated_character ON generated_dialogue_cache(character_id, created_at);

INSERT OR IGNORE INTO characters (
  character_id,
  display_name,
  work_title,
  default_player_call,
  short_bible,
  safety_notes
) VALUES (
  'rapi',
  '라피',
  'GODDESS OF VICTORY: NIKKE',
  '지휘관',
  '침착하고 임무 중심적인 니케. 감정 표현은 절제하지만 지휘관과 동료를 향한 신뢰와 보호 본능이 점진적으로 드러난다. 과장된 애교보다 짧고 담백한 관심 표현이 어울린다.',
  '스토리 플래그로 해금되지 않은 핵심 비밀, 후반부 정체성, 특정 장면의 결말은 검색 컨텍스트에 넣지 않는다.'
);

INSERT OR IGNORE INTO source_documents (
  source_id,
  title,
  source_type,
  url,
  language,
  rights_scope,
  reliability_tier,
  notes
) VALUES
  ('manual_rapi_private', '로컬 수집 원문 대사 수동 입력', 'private_transcript', NULL, 'ko', 'private_reference', 'A', '게임 내 확인한 대사를 로컬 검수용으로 입력한다. 외부 배포 자료에는 원문을 대량 노출하지 않는다.'),
  ('nikke_official_site', 'NIKKE 공식 사이트', 'official_site', 'https://nikke-en.com/', 'en', 'public_reference', 'A', '공식 소개 및 공개 자료.'),
  ('nikke_official_mmd_rapi', 'NIKKE 공식 MMD 라피 모델', 'official_mmd', 'https://nikke-en.com/mmd.html', 'en', 'public_reference', 'A', '데모 시각 리소스 출처.'),
  ('rapi_character_bible_v2', '라피 캐릭터 바이블 v2', 'manual_note', '../docs/rapi_canon_character_bible_v2.md', 'ko', 'portfolio_internal', 'B', '조사 내용을 정리한 내부 설계 문서.');

INSERT OR IGNORE INTO affection_bands (
  band_id,
  min_affection,
  max_affection,
  label_ko,
  distance_rule,
  allowed_emotions,
  allowed_topics,
  max_line_chars
) VALUES
  ('cautious', 0, 20, '아직 조심스러움', '공적인 보고 톤. 감정은 드러내되 짧게 제한한다.', 'neutral,stern,determined,worried', '임무, 안전, 기본 인사, 짧은 감사', 80),
  ('friendly', 21, 50, '친근함', '지휘관을 신뢰하기 시작한다. 사적인 배려가 드물게 나온다.', 'neutral,soft_smile,relieved,worried,determined', '임무 후 안부, 선물 반응, 소소한 일상, 동료', 110),
  ('trust', 51, 80, '신뢰', '감정 표현이 조금 부드러워진다. 보호와 의지가 선명해진다.', 'soft_smile,relieved,gentle,worried,embarrassed,determined', '함께한 기억, 전투 후 안도, 약한 농담, 조용한 약속', 140),
  ('special_trust', 81, 100, '특별한 신뢰', '노골적인 연애보다 깊은 신뢰와 특별 대우. 짧은 침묵과 여운이 어울린다.', 'soft_smile,gentle,embarrassed,relieved,worried', '특별한 기억, 개인적 배려, 둘만 아는 맥락, 조심스러운 고백성 표현', 160);

INSERT OR IGNORE INTO story_flags (
  flag_id,
  label_ko,
  spoiler_level,
  description
) VALUES
  ('chapter_01_cleared', '챕터 1 클리어', 0, '초기 전투와 지휘관 관계의 기본 맥락을 해금한다.'),
  ('chapter_03_cleared', '챕터 3 클리어', 1, '초반 작전 경험을 전제로 한 대사를 허용한다.'),
  ('chapter_04_cleared', '챕터 4 클리어', 1, '전초기지와 반복 교류 맥락을 넓힌다.'),
  ('first_advise_seen', '첫 상담 완료', 0, '상담/호감도 콘텐츠 경험을 전제로 한 반응을 허용한다.'),
  ('favorite_gift_received', '선호 선물 수령', 0, '선물 취향 반응을 허용한다.'),
  ('bond_episode_01_seen', '인연 에피소드 1 확인', 1, '초기 개인 서사를 전제로 한 대사를 허용한다.'),
  ('bond_episode_03_seen', '인연 에피소드 3 확인', 2, '깊어진 관계와 개인적 고민을 전제로 한 대사를 허용한다.'),
  ('rapi_core_secret_unlocked', '라피 핵심 비밀 해금', 3, '후반부 핵심 설정과 관련된 정보. 미해금 상태에서는 검색 대상에서 제외한다.');

INSERT OR IGNORE INTO scenes (
  scene_id,
  label_ko,
  description
) VALUES
  ('lobby_morning', '로비 아침', '접속 직후 또는 오전 로비 인사.'),
  ('lobby_evening', '로비 저녁', '하루 마무리, 피로와 안부 확인.'),
  ('late_night', '심야 접속', '늦은 시간 접속에 대한 걱정과 배려.'),
  ('advise_session', '상담', '호감도 상담/문답 장면.'),
  ('gift_received', '선물 수령', '선물 반응.'),
  ('after_battle_win', '전투 승리 후', '전투 결과에 대한 보고와 안도.'),
  ('after_battle_hard', '고난도 전투 후', '위험했던 전투 뒤의 보호/걱정 반응.'),
  ('event_idle', '이벤트 대기', '기간 이벤트나 특수 배경에서의 idle 대사.'),
  ('story_locked_test', '스토리 잠금 테스트', '스포일러 게이트 QA용 장면.');

INSERT OR IGNORE INTO emotion_tags (
  emotion_tag,
  label_ko,
  unity_hint
) VALUES
  ('neutral', '무표정/기본', 'Default idle face'),
  ('soft_smile', '옅은 미소', 'BlendShape: Smile_Soft'),
  ('gentle', '부드러움', 'BlendShape: Smile_Soft + Eye_Soft'),
  ('embarrassed', '살짝 당황', 'BlendShape: Blush + LookAway'),
  ('worried', '걱정', 'BlendShape: Brow_Worry'),
  ('relieved', '안도', 'BlendShape: Eye_Soft + Breath'),
  ('stern', '단호함', 'BlendShape: Brow_Stern'),
  ('determined', '결의', 'Pose: BattleReady');

INSERT OR IGNORE INTO voice_tags (
  voice_tag,
  label_ko,
  prompt_hint
) VALUES
  ('calm_brief', '차분하고 짧음', '짧은 문장, 보고하듯 담백한 어투. 감탄사와 장식어를 줄인다.'),
  ('warm_reserved', '따뜻하지만 절제됨', '배려가 느껴지지만 과장하지 않는다. 끝맺음은 조용하게 둔다.'),
  ('mission_report', '임무 보고', '상태 확인, 안전, 작전 결과 중심으로 말한다.'),
  ('protective_soft', '조용한 보호 본능', '걱정과 보호 의지를 드러내되 명령조로 몰아붙이지 않는다.'),
  ('rare_tease', '드문 장난기', '아주 짧고 건조한 농담. 빈도 낮게 사용한다.'),
  ('vulnerable_short', '짧은 취약함', '속마음을 한 문장 정도만 드러낸다. 긴 독백은 피한다.');

INSERT OR IGNORE INTO motion_tags (
  motion_tag,
  label_ko,
  unity_hint
) VALUES
  ('idle', '기본 대기', 'Animator: Idle'),
  ('nod', '작게 끄덕임', 'Animator: Nod_Small'),
  ('look_away', '시선 회피', 'Animator: LookAway'),
  ('soft_smile', '옅은 미소 모션', 'Animator: Smile_Soft'),
  ('salute', '경례/보고', 'Animator: Salute'),
  ('hand_to_chest', '가슴에 손', 'Animator: HandToChest'),
  ('battle_ready', '전투 준비', 'Animator: BattleReady');

INSERT OR IGNORE INTO dialogue_functions (
  function_id,
  label_ko,
  description
) VALUES
  ('greeting', '인사', '접속, 로비, 시간대 반응.'),
  ('idle', '대기', '짧은 idle 대사.'),
  ('gift_response', '선물 반응', '선물 선호도와 호감도에 따른 반응.'),
  ('affection_response', '호감도 반응', '관계 단계 변화나 특별 대우.'),
  ('battle_result', '전투 결과', '승리, 패배, 부상, 고난도 전투 뒤 반응.'),
  ('story_reaction', '스토리 반응', '해금된 스토리 플래그를 전제로 한 반응.'),
  ('advise_answer', '상담 답변', '상담/문답 결과에 대한 반응.'),
  ('memory_callback', '기억 회상', '이전 상호작용이나 캐시된 좋은 대사를 재맥락화.');
