CREATE TABLE IF NOT EXISTS classification_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_group TEXT NOT NULL,
    target_type TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    keywords TEXT NOT NULL,
    output_field TEXT NOT NULL,
    output_value TEXT NOT NULL,
    score_delta INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 100,
    is_active INTEGER DEFAULT 1,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_classification_rules_target
ON classification_rules(target_type, rule_group, is_active);

CREATE INDEX IF NOT EXISTS idx_classification_rules_priority
ON classification_rules(priority);

INSERT OR IGNORE INTO classification_rules (
    rule_group, target_type, rule_name, keywords, output_field, output_value, score_delta, priority, is_active, description, created_at, updated_at
) VALUES
('tag','news','뉴스_반도체','반도체,hbm,d램,낸드,파운드리,메모리','ai_tags','반도체',10,10,1,'반도체 관련 뉴스 태그',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('tag','news','뉴스_AI','ai,인공지능,데이터센터,gpu,npu','ai_tags','AI',10,20,1,'AI 관련 뉴스 태그',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('tag','news','뉴스_실적','실적,영업이익,매출,어닝,흑자,적자','ai_tags','실적',20,30,1,'실적 관련 뉴스 태그',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('tag','news','뉴스_수주','수주,계약,공급,납품','ai_tags','수주',20,40,1,'수주/계약 뉴스 태그',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('tag','news','뉴스_투자','투자,증설,공장,캠퍼스,라인,설비','ai_tags','투자',15,50,1,'투자/증설 뉴스 태그',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('tag','news','뉴스_신제품','출시,선보였다,앱,서비스,제품','ai_tags','신제품',5,60,1,'신제품 뉴스 태그',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('tag','news','뉴스_지정학','전쟁,중동,호르무즈,중국,미국,관세','ai_tags','지정학',10,70,1,'지정학 이슈 태그',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('tag','news','뉴스_리스크','위기,불확실,우려,하락,부진,차질','ai_tags','리스크',10,80,1,'리스크 뉴스 태그',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('sentiment','news','뉴스_긍정','호조,증가,개선,성장,확대,수주,흑자,상회,기대,강세,상승','ai_sentiment','positive',0,20,1,'긍정 감성 규칙',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('sentiment','news','뉴스_부정','하락,감소,부진,적자,차질,위기,리스크,우려,소송,제재,규제,손실,악화','ai_sentiment','negative',0,20,1,'부정 감성 규칙',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_event_type','disclosure','공시_지분변동','주식등의대량보유상황보고서,임원,주요주주,특정증권,소유상황,최대주주,주식변동,소유주식변동,소유주식변동신고서','ai_event_type','지분변동',10,30,1,'지분변동 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_event_type','disclosure','공시_실적','잠정실적,영업실적,매출액,손익구조,실적','ai_event_type','실적',20,20,1,'실적 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_event_type','disclosure','공시_계약','단일판매,공급계약,수주,계약체결','ai_event_type','계약',20,20,1,'계약 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_event_type','disclosure','공시_투자','신규시설투자,타법인출자,투자판단,시설투자','ai_event_type','투자',15,25,1,'투자 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_event_type','disclosure','공시_소송','소송,분쟁,판결,중재','ai_event_type','소송',25,10,1,'소송 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_event_type','disclosure','공시_자본','유상증자,무상증자,전환사채,신주인수권,사채','ai_event_type','자본',20,15,1,'자본 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_event_type','disclosure','공시_배당','배당,현금배당,주당배당금,결산배당,중간배당','ai_event_type','배당',10,35,1,'배당 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_event_type','disclosure','공시_자사주','자기주식,자사주,자기주식취득,자기주식처분,자사주신탁','ai_event_type','자사주',10,35,1,'자사주 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_event_type','disclosure','공시_주주총회','주주총회,정기주주총회,임시주주총회,의결권','ai_event_type','주주총회',5,40,1,'주주총회 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_risk_level','disclosure','공시_고위험','소송,제재,불성실공시,상장폐지,감사의견,관리종목,횡령,배임','ai_risk_level','high',20,10,1,'고위험 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_risk_level','disclosure','공시_중위험','유상증자,전환사채,대규모 투자,주요 계약 해지,지분변동','ai_risk_level','medium',10,20,1,'중위험 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('disclosure_risk_level','disclosure','공시_저위험','배당,자사주,주주총회,임원 보유','ai_risk_level','low',0,30,1,'저위험 공시 분류',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP);
