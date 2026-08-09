CREATE TABLE IF NOT EXISTS market_theme_return_prediction_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, target_date TEXT NOT NULL, data_cutoff_date TEXT NOT NULL,
    data_cutoff_at TEXT, prediction_stage TEXT NOT NULL DEFAULT 'PREMARKET',
    prediction_horizon TEXT NOT NULL DEFAULT 'NEXT_SELECTED_DATE', official_method TEXT NOT NULL DEFAULT 'RULE',
    status TEXT NOT NULL DEFAULT 'DRAFT', revision_count INTEGER NOT NULL DEFAULT 1, rule_version TEXT NOT NULL,
    model_version TEXT, first_predicted_at TEXT NOT NULL, last_predicted_at TEXT NOT NULL, evaluated_at TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE(target_date, prediction_stage, prediction_horizon)
);
CREATE TABLE IF NOT EXISTS market_theme_return_prediction_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL, theme_id INTEGER NOT NULL,
    prediction_method TEXT NOT NULL DEFAULT 'RULE', is_official INTEGER NOT NULL DEFAULT 1,
    base_change_rate REAL, predicted_change_rate REAL, prediction_score REAL, predicted_rank INTEGER,
    price_score REAL, flow_score REAL, breadth_score REAL, alignment_score REAL, liquidity_score REAL,
    market_environment_score REAL, penalty_score REAL NOT NULL DEFAULT 0, data_coverage_rate REAL NOT NULL DEFAULT 0,
    actual_change_rate REAL, actual_rank INTEGER, signed_gap REAL, absolute_gap REAL, rank_gap INTEGER,
    direction_hit INTEGER, baseline_absolute_error REAL, prediction_effect REAL,
    evaluation_status TEXT NOT NULL DEFAULT 'NOT_EVALUATED', evaluated_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE(run_id, theme_id, prediction_method),
    FOREIGN KEY (run_id) REFERENCES market_theme_return_prediction_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (theme_id) REFERENCES market_themes(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS market_theme_return_prediction_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL UNIQUE, theme_count INTEGER NOT NULL,
    evaluable_theme_count INTEGER NOT NULL, return_mae REAL, return_rmse REAL, mean_signed_gap REAL,
    mean_rank_error REAL, top1_hit REAL, precision_at_3 REAL, precision_at_5 REAL, precision_at_10 REAL,
    direction_accuracy REAL, spearman_rank_correlation REAL, ndcg_at_5 REAL, baseline_mae REAL,
    mae_improvement REAL, baseline_precision_at_5 REAL, improved_theme_count INTEGER NOT NULL DEFAULT 0,
    evaluation_status TEXT NOT NULL, evaluated_at TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES market_theme_return_prediction_runs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS market_theme_return_prediction_rule_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT, rule_version TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE', is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS market_theme_return_prediction_rule_parameters (
    id INTEGER PRIMARY KEY AUTOINCREMENT, rule_set_id INTEGER NOT NULL, parameter_code TEXT NOT NULL,
    parameter_value REAL NOT NULL, description TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE(rule_set_id, parameter_code), FOREIGN KEY (rule_set_id) REFERENCES market_theme_return_prediction_rule_sets(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_theme_prediction_runs_cutoff ON market_theme_return_prediction_runs(data_cutoff_date, status);
CREATE INDEX IF NOT EXISTS idx_theme_prediction_items_run_rank ON market_theme_return_prediction_items(run_id, predicted_rank);
INSERT OR IGNORE INTO market_theme_return_prediction_rule_sets
(rule_version,name,status,is_active,created_at,updated_at)
VALUES ('RULE_V1','규칙 기반 테마등락예측 V1','ACTIVE',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP);
INSERT OR IGNORE INTO market_theme_return_prediction_rule_parameters
(rule_set_id,parameter_code,parameter_value,description,created_at,updated_at)
SELECT id,'PRICE_WEIGHT',0.25,'가격 모멘텀 가중치',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP FROM market_theme_return_prediction_rule_sets WHERE rule_version='RULE_V1';
INSERT OR IGNORE INTO market_theme_return_prediction_rule_parameters
(rule_set_id,parameter_code,parameter_value,description,created_at,updated_at)
SELECT id,'FLOW_WEIGHT',0.25,'수급 강도 가중치',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP FROM market_theme_return_prediction_rule_sets WHERE rule_version='RULE_V1';
INSERT OR IGNORE INTO market_theme_return_prediction_rule_parameters
(rule_set_id,parameter_code,parameter_value,description,created_at,updated_at)
SELECT id,'BREADTH_WEIGHT',0.15,'연결 종목 확산도 가중치',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP FROM market_theme_return_prediction_rule_sets WHERE rule_version='RULE_V1';
INSERT OR IGNORE INTO market_theme_return_prediction_rule_parameters
(rule_set_id,parameter_code,parameter_value,description,created_at,updated_at)
SELECT id,'ALIGNMENT_WEIGHT',0.15,'가격·수급 결합 가중치',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP FROM market_theme_return_prediction_rule_sets WHERE rule_version='RULE_V1';
INSERT OR IGNORE INTO market_theme_return_prediction_rule_parameters
(rule_set_id,parameter_code,parameter_value,description,created_at,updated_at)
SELECT id,'LIQUIDITY_WEIGHT',0.10,'거래대금 가중치',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP FROM market_theme_return_prediction_rule_sets WHERE rule_version='RULE_V1';
INSERT OR IGNORE INTO market_theme_return_prediction_rule_parameters
(rule_set_id,parameter_code,parameter_value,description,created_at,updated_at)
SELECT id,'MARKET_ENVIRONMENT_WEIGHT',0.10,'시장환경 가중치',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP FROM market_theme_return_prediction_rule_sets WHERE rule_version='RULE_V1';
INSERT OR IGNORE INTO market_theme_return_prediction_rule_parameters
(rule_set_id,parameter_code,parameter_value,description,created_at,updated_at)
SELECT id,'OVERHEAT_PENALTY_MAX',15.0,'최근 급등 과열 최대 감점',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP FROM market_theme_return_prediction_rule_sets WHERE rule_version='RULE_V1';
INSERT OR IGNORE INTO market_theme_return_prediction_rule_parameters
(rule_set_id,parameter_code,parameter_value,description,created_at,updated_at)
SELECT id,'CONCENTRATION_PENALTY_MAX',10.0,'단일 종목 집중 최대 감점',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP FROM market_theme_return_prediction_rule_sets WHERE rule_version='RULE_V1';
INSERT OR IGNORE INTO market_theme_return_prediction_rule_parameters
(rule_set_id,parameter_code,parameter_value,description,created_at,updated_at)
SELECT id,'LOW_COVERAGE_PENALTY_MAX',20.0,'낮은 수집률 최대 감점',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP FROM market_theme_return_prediction_rule_sets WHERE rule_version='RULE_V1';
INSERT OR IGNORE INTO market_theme_return_prediction_rule_parameters
(rule_set_id,parameter_code,parameter_value,description,created_at,updated_at)
SELECT id,'FLOW_DIVERGENCE_PENALTY_MAX',10.0,'가격·수급 이탈 최대 감점',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP FROM market_theme_return_prediction_rule_sets WHERE rule_version='RULE_V1';
INSERT OR IGNORE INTO market_theme_return_prediction_rule_parameters
(rule_set_id,parameter_code,parameter_value,description,created_at,updated_at)
SELECT id,'MIN_DATA_COVERAGE',0.70,'공식 순위 최소 데이터 수집률',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP FROM market_theme_return_prediction_rule_sets WHERE rule_version='RULE_V1';
INSERT OR IGNORE INTO market_theme_return_prediction_rule_parameters
(rule_set_id,parameter_code,parameter_value,description,created_at,updated_at)
SELECT id,'PREDICTION_SCALE',1.0,'예상 등락률 변동성 배율',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP FROM market_theme_return_prediction_rule_sets WHERE rule_version='RULE_V1';
INSERT OR IGNORE INTO market_theme_return_prediction_rule_parameters
(rule_set_id,parameter_code,parameter_value,description,created_at,updated_at)
SELECT id,'PREDICTION_BIAS',0.0,'예상 등락률 편향 보정',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP FROM market_theme_return_prediction_rule_sets WHERE rule_version='RULE_V1';
INSERT OR IGNORE INTO market_theme_return_prediction_rule_parameters
(rule_set_id,parameter_code,parameter_value,description,created_at,updated_at)
SELECT id,'PREDICTION_MIN',-20.0,'예상 등락률 하한',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP FROM market_theme_return_prediction_rule_sets WHERE rule_version='RULE_V1';
INSERT OR IGNORE INTO market_theme_return_prediction_rule_parameters
(rule_set_id,parameter_code,parameter_value,description,created_at,updated_at)
SELECT id,'PREDICTION_MAX',20.0,'예상 등락률 상한',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP FROM market_theme_return_prediction_rule_sets WHERE rule_version='RULE_V1';
INSERT OR IGNORE INTO market_theme_return_prediction_rule_parameters
(rule_set_id,parameter_code,parameter_value,description,created_at,updated_at)
SELECT id,'DIRECTION_NEUTRAL_BAND',0.5,'방향 평가 중립 구간',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP FROM market_theme_return_prediction_rule_sets WHERE rule_version='RULE_V1';
