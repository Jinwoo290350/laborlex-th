CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS laws (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    short_name    TEXT NOT NULL UNIQUE,            -- e.g. LPA2541
    type          TEXT NOT NULL CHECK (type IN ('act','decree','ministerial_reg','announcement')),
    level         SMALLINT NOT NULL CHECK (level BETWEEN 1 AND 4),
    enacted_date  DATE,
    source_file   TEXT,
    parent_law_id INT REFERENCES laws(id),
    quality       TEXT,                            -- krisdika_pdf | docx | docx_ocr
    note          TEXT
);

CREATE TABLE IF NOT EXISTS provisions (
    id           SERIAL PRIMARY KEY,
    law_id       INT NOT NULL REFERENCES laws(id),
    chapter      TEXT,
    chapter_title TEXT,
    section_no   TEXT NOT NULL,                    -- "118", "17/1", "ข้อ 3"
    paragraph_no INT NOT NULL DEFAULT 1,
    sub_no       TEXT,                             -- "(1)" or NULL
    text         TEXT NOT NULL,
    valid_from   DATE,
    valid_to     DATE,                             -- NULL = still in force
    amended_by   INT REFERENCES laws(id),
    repealed     BOOLEAN NOT NULL DEFAULT FALSE,
    amendment_notes TEXT[] NOT NULL DEFAULT '{}',  -- krisdika footnotes, e.g. "… เพิ่มโดย … (ฉบับที่ 7) พ.ศ. 2562"
    citation_key TEXT NOT NULL,
    embedding    vector(1024),
    -- same citation_key may exist in several versions; one row per version
    UNIQUE (citation_key, valid_from)
);
CREATE INDEX IF NOT EXISTS provisions_section_idx ON provisions (law_id, section_no);

CREATE TABLE IF NOT EXISTS links (
    from_id  INT NOT NULL REFERENCES provisions(id),
    to_id    INT NOT NULL REFERENCES provisions(id),
    type     TEXT NOT NULL CHECK (type IN ('ISSUED_UNDER','REFERS_TO','AMENDED_BY','REPEALED_BY')),
    evidence TEXT,
    PRIMARY KEY (from_id, to_id, type)
);

CREATE TABLE IF NOT EXISTS cases (
    id         SERIAL PRIMARY KEY,
    deka_no    TEXT NOT NULL UNIQUE,              -- case number as the court prints it
    court      TEXT NOT NULL,                     -- ศาลฎีกา | ศาลอุทธรณ์คดีชำนัญพิเศษ | …
    doc_type   TEXT,                              -- คำพิพากษา | คำวินิจฉัย | คำสั่ง
    year       INT,
    facts      TEXT,
    holding    TEXT,                              -- headnote / ย่อสั้น
    full_text  TEXT,
    source     TEXT,                              -- dataset it came from
    source_url TEXT,
    embedding  vector(1024)
);

CREATE TABLE IF NOT EXISTS case_links (
    case_id      INT REFERENCES cases(id),
    provision_id INT REFERENCES provisions(id),
    PRIMARY KEY (case_id, provision_id)
);

CREATE TABLE IF NOT EXISTS issues (
    id          SERIAL PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    description TEXT,
    elements    JSONB NOT NULL DEFAULT '[]',
    formula_key TEXT,
    reviewed_by TEXT
);

CREATE TABLE IF NOT EXISTS issue_links (
    issue_id     INT REFERENCES issues(id),
    provision_id INT REFERENCES provisions(id),
    PRIMARY KEY (issue_id, provision_id)
);

CREATE TABLE IF NOT EXISTS examples (
    id          SERIAL PRIMARY KEY,
    source      TEXT NOT NULL,
    question    TEXT NOT NULL,
    answer_json JSONB,
    issues      TEXT[],
    verified    BOOLEAN NOT NULL DEFAULT FALSE,
    embedding   vector(1024)
);

CREATE TABLE IF NOT EXISTS runs (
    id          SERIAL PRIMARY KEY,
    question_id TEXT,
    config      JSONB,
    trace       JSONB,
    answer_json JSONB,
    cost_usd    NUMERIC(10,6),
    tokens      INT,
    latency_ms  INT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
