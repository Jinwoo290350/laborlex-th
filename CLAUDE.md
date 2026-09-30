# CLAUDE.md — LaborLex-TH (Thai Labor Law Legal Agent)

> คู่มือโปรเจกต์สำหรับ Claude Code และผู้พัฒนา **อ่านให้ครบก่อนเขียนโค้ดทุกครั้งที่เริ่ม session**
> Owner: Frank (วีรพงษ์ ฮะภูริวัฒน์) · Client: Bosolo12 และทีม · Repo: `laborlex-th` (private)
> แผนงานรายวันและ checklist อยู่ที่ `docs/PLAN.md` · อัปเดตล่าสุด 2026-09-30 (scaffold เริ่มแล้ว)

---

## 0. TL;DR สำหรับ Claude Code

- เรากำลังสร้าง **ระบบตอบคำถามกฎหมายแรงงานไทย** ที่ **ระบบเป็นผู้คุมลำดับการคิด** (LangGraph state machine) ไม่ใช่ปล่อยให้ LLM คิดรวดเดียว
- ความแม่นยำมาจาก 4 อย่าง ตามลำดับความสำคัญ: **ค้นตัวบทให้ถูก (Legal Index) > คำนวณด้วยโค้ด > ตรวจองค์ประกอบ > ตรวจคำตอบก่อนส่ง**
- ตัววัดเดียวที่สำคัญคือ **PASS rate** (ได้ 2 คะแนนครบทั้ง 6 เกณฑ์) บนชุด 160 ข้อที่อาจารย์ประเมิน เป้า ≥ 90% (baseline Gemini = 64%)
- **ห้าม:** แตะ `test160`, เขียนตัวเลขกฎหมายจากความจำ, commit secrets, สร้าง citation ที่ไม่มีใน DB
- ทุกการเปลี่ยนแปลงที่กระทบคำตอบ → รัน `make eval-dev` แล้วบันทึกผลใน `docs/results/`

---

## 1. เป้าหมายและบริบท

ระบบ Agentic AI ตอบคำถามกฎหมายแรงงานไทยได้แม่นและละเอียดกว่าโมเดลทั่วไป เพื่อ**ตีพิมพ์งานวิจัย**
ลูกค้าต้องการ "กระบวนการที่มีเหตุผล ใช้หลักวิทยาการคอมพิวเตอร์ ต้นทุนต่ำ วิธีใหม่ และแม่นยำ"

| | |
|---|---|
| LLM หลัก | Gemini 3.5 Flash (ลูกค้ากำหนด) — model id `gemini-3.5-flash` (ตรวจด้วย `client.models.list()` 2026-09-30) |
| เป้าหมาย | PASS ≥ 90% บน test160 (อาจารย์กฎหมายเป็นผู้ประเมิน) |
| Baseline (dev100) | Gemini PASS 64 · ChatGPT 34 · Claude 31 |
| Baseline รายเกณฑ์ (Gemini, % ได้ 2) | A1 100 · B0 97 · B1 81 · B3 78 · B2 78 · **A2 75** |
| คำพูดลูกค้า | "AI ตอบคำถามสั้นได้ แต่พอต้องวิเคราะห์ + คำนวณ มักตายและอ้างมาตราผิด" |

### Requirements ของลูกค้า (ห้ามละเมิด)
1. ตอบภายใต้กฎหมายแรงงานไทย อิงเอกสารใน Google Drive เป็นหลัก
2. แม่นกว่าโมเดลปัจจุบัน ทั้งคำตอบและการอ้างมาตรา
3. มีฐานฎีกา (เฟสนี้ใช้ที่มีอยู่ การ scrape เป็นงานแยก)
4. ทุกคำตอบมี citation ตรวจย้อนได้ **ห้ามสร้างมาตรา/ฎีกาที่ไม่มีจริง**
5. เก็บ version และช่วงเวลาที่กฎหมายมีผล ไม่อ้างผิดฉบับ
6. แยกขั้น: ข้อเท็จจริง → ประเด็น → มาตรา → ฎีกา → ปรับบท → สรุป
7. ข้อมูลไม่พอ → ตอบแบบมีเงื่อนไข + ถามเพิ่ม **ห้ามเดา**
8. ตรวจคำตอบก่อนส่ง (เลขมาตรา หลักกฎหมาย ฎีกา)
9. ใช้ RAG / Agentic / CoT / ML / Hybrid Search / Reranking ได้
10. **Core logic ต้องควบคุมโดยระบบเรา ไม่พึ่ง reasoning ของ LLM อย่างเดียว**
11. มี novelty มากกว่า chatbot + RAG
12. อ้างกฎหมายแม่และลูกคู่กัน และรู้ลำดับชั้น (พ.ร.บ. > พ.ร.ก. > กฎกระทรวง > ประกาศ/ข้อบังคับ)
    ตัวอย่างลูกค้า: พ.ร.บ. กำหนดไม่เกิน 500 แต่ข้อบังคับกำหนด 300 → ต้องเห็นทั้งคู่ และระบุว่าใช้ตัวไหนเพราะอะไร

---

## 2. ขอบเขตตามสัญญา (9,000 บาท)

| เฟส | งาน | เงื่อนไขรับเงิน |
|---|---|---|
| **1** (4,500) | ระบบครบ flow + Legal Index + UI deploy ให้อาจารย์ทดสอบ 30 วัน | อาจารย์ลองแล้วโดยรวมโอเค (แก้ได้ 2 รอบ รอบละ ≤ 7 วัน, ไม่ตอบใน 7 วัน = ผ่าน) |
| **2** (4,500) | รัน test160 ส่งผล + อธิบาย flow (ประชุม ≤ 2 ชม.) + ไดอะแกรม flow + README | ส่งผลและอธิบายเสร็จ (ไม่ผูกกับ %) |
| หลังประเมิน | PASS < 90% → แก้ฟรี 2 รอบภายใน 14 วัน | — |

- **Timeline:** เฟส 1 ภายใน 18 วันหลังได้ข้อมูลครบ · เฟส 2 ภายใน 7 วันหลังได้ test160
- **ไม่รวม (จ้างแยก):** scrape ฎีกา, ทดสอบวิเคราะห์ฎีกา, ไดอะแกรมอื่น, รายงานวิจัยฉบับเต็ม, fine-tune, production ถาวร, UI แบบ NotebookLM (mind map)
- คำขอนอกขอบเขต → บันทึก `docs/change_requests.md` แล้วแจ้ง Frank ก่อนทำ

---

## 3. เกณฑ์การให้คะแนน (Rubric)

| เกณฑ์ | ส่วน | ประเมินอะไร | 2 / 1 / 0 |
|---|---|---|---|
| A1 | สรุป | ตอบตรงคำถามครบทุกประเด็น (ไม่ดูว่าถูกไหม) | ครบ / บางส่วน / ไม่ตอบ |
| A2 | สรุป | คำตอบถูกต้องตามกฎหมาย | ถูกทั้งหมด / ผิดบางส่วน / ผิดทั้งหมด |
| B0 | ประเด็น | เห็นประเด็นที่ต้องพิจารณาครบ | ครบและเกี่ยวข้อง / ไม่ครบหรือเกิน / ผิด |
| B1 | วางหลัก | เลือกมาตราและอธิบายหลักกฎหมายครบถูก | ถูกครบ / ผิดบางส่วน / ผิดทุกส่วน |
| B2 | ปรับบท | นำกฎหมายมาปรับกับข้อเท็จจริงถูก | ถูกครบ / ผิดบางส่วน / ไม่ปรับบท |
| B3 | สรุป | สรุปของประเด็นถูก | ถูกทั้งหมด / ผิดบางส่วน / ผิดทั้งหมด |

**PASS = ทั้ง 6 เกณฑ์ได้ 2** → เกณฑ์ใดเกณฑ์หนึ่งพลาด = ข้อนั้นไม่ผ่าน
**ผลที่ตามมา:** อย่าเพิ่มประเด็นเกินจำเป็น (B0 โดนหักเมื่อ "มีประเด็นเกิน") และอย่าปฏิเสธไม่ตอบ (A1 = 0)

---

## 4. ข้อมูล

### 4.1 กฎหมาย (Google Drive บัญชีโครงการของลูกค้า)
| ประเภท | Folder ID | ปลายทาง |
|---|---|---|
| พ.ร.บ.คุ้มครองแรงงาน 2541 + แรงงานสัมพันธ์ 2518 | `1DwdMPYK8TOvBXw-EfY2LiSl3RGI08w5j` | `data/raw/laws/act/` |
| ป.พ.พ. ลักษณะจ้างแรงงาน (**ยังไม่มีในโฟลเดอร์ลูกค้า** — ตัวอย่างคำตอบลูกค้าอ้าง ม.577) | — | `data/raw/laws/act/` |
| พ.ร.ก. | `1hCl0G7qT7AdLYJPzKktekZTYUSfEQlk2` | `data/raw/laws/decree/` |
| กฎกระทรวง | `1Akeh92GBAnAsBmc1kPhvdbF3IR59qCBX` | `data/raw/laws/ministerial/` |
| ประกาศ | `1byE2ikDpNeKeafDmUGnlkGGhsmUzQ8eL` | `data/raw/laws/announcement/` |

- **ห้ามแก้ไฟล์ใน `data/raw/`** · บันทึก `data/raw/MANIFEST.csv` (ไฟล์, ประเภท, วันที่ดาวน์โหลด, sha256)
- PDF สแกน → OCR ภาษาไทย (Typhoon OCR หรือ iApp OCR) → `data/interim/` แล้ว**ตรวจเลขมาตรากับต้นฉบับ**
- ตัวบทฉบับรวมแก้ไขล่าสุดควรเทียบกับ krisdika.go.th เมื่อสงสัย

### 4.2 ฎีกา
- เฟสนี้: ข้อมูลที่คนเก่าดึงจาก deka.supremecourt.or.th (ขอจากลูกค้า) → `data/raw/cases/`
- อนาคต (งานแยก): api.slegaltools.digital, openlawdatathailand.org (HF, **CC BY-SA 4.0**), legal.labour.go.th, area6.labour.go.th, lbudtc.coj.go.th, ops.mol.go.th
- scraper (ถ้าได้รับจ้าง) ต้อง: ≥ 1 วินาที/request, เคารพ robots.txt, cache, เก็บ URL ต้นทาง

### 4.3 ชุดคำถาม
| ชุด | ใช้ทำอะไร | ไฟล์ |
|---|---|---|
| dev100 (Google Sheet ลูกค้า แท็บ `Sheet2`, split=DEV) → `make dev100` · `gold_answer` = คอลัมน์ H "มาตราและคำตอบที่ถูกสั้นๆ" (คอลัมน์ G = `ref_answer` อาจผิด) · คะแนน baseline รายข้อ **ยังไม่ได้** | พัฒนา, few-shot, error analysis, calibrate judge | `data/eval/dev100.csv` |
| ข้อสอบเนติฯ แรงงาน 2524–2563 | ทดสอบเพิ่ม (ตรวจซ้ำกับ test160 ก่อนใช้) | `data/eval/bar_labor.csv` |
| **test160** | **ประเมินจริงโดยอาจารย์เท่านั้น** | `data/eval/test160.csv` |

**Schema ของไฟล์ eval:** `id, question, gold_answer, gold_issues, gold_citations, event_date, source, notes` (+ `category, question_type, difficulty, ref_answer` สำหรับ dev100)

> ⚠️ แท็บ `Sheet1` ของชีต dev มีแถวที่ split ไม่ใช่ DEV (สูตรเสีย) อาจเป็นข้อ test → **ห้ามเปิด/ใช้** importer อ่านเฉพาะ `Sheet2` split=DEV

> 🚫 **กฎเหล็ก data leakage**
> - test160 ห้ามใช้เป็น few-shot, ห้ามจูน prompt/threshold, ห้ามเปิดดูระหว่างพัฒนา
> - วัด dev100 แบบ leave-one-out (ตัดข้อที่กำลังทดสอบออกจากคลัง few-shot)
> - ข้อสอบเนติฯ ที่ซ้ำกับ test160 → ตัดออก (เทียบด้วย embedding similarity > 0.9 + ตาหาคน)

### 4.4 กฎหมายตามเวลา (สำคัญมากกับข้อสอบเก่า)
- ถ้าคำถามระบุวันเกิดเหตุ → ใช้ตัวบทที่มีผล ณ วันนั้น
- ถ้าไม่ระบุ → ใช้ฉบับปัจจุบัน และ**ถ้ามาตราที่ใช้เคยถูกแก้ไข ให้แจ้งในคำตอบ** ("กรณีเกิดก่อน พ.ศ. … ใช้หลักเดิมคือ …")
- ข้อสอบเนติฯ ปีเก่าอาจเฉลยตามกฎหมายเดิม → บันทึกใน `notes` ของข้อนั้น อย่าจูนระบบให้ตอบตามกฎหมายที่ถูกยกเลิกแล้ว

### 4.5 รูปแบบคำตอบ
Template ของลูกค้าอยู่ที่ `prompts/answer_template.md` (จาก screenshot ลูกค้า 2026-09-30) · schema `src/agent/answer.py` · renderer `src/agent/render.py` โครงสร้าง:
คำตอบเบื้องต้น → ประเด็นทางกฎหมาย → [ต่อประเด็น: สิ่งที่ต้องพิจารณา / กฎหมายที่เกี่ยวข้อง (อธิบายสั้น + **หัวข้อตัวหนา**) / การปรับบท (bullet ข้อเท็จจริง → ผล) / การคำนวณ (ถ้ามี) / ข้อสรุป] → ตารางความเห็นทางกฎหมาย → ข้อเท็จจริงที่ต้องถามเพิ่ม (เฉพาะเมื่อจำเป็น)

**ปรับจาก template เดิม:** "ฟันธง" ได้เมื่อมีตัวบทรองรับเท่านั้น · ระบบสร้างคำตอบเป็น **JSON ก่อน** แล้ว render เป็น markdown (เพื่อให้ตรวจ citation และ eval ได้)

---

## 5. สถาปัตยกรรม

```
                ┌──────────── Google Drive / cases ────────────┐
                ▼                                              │
  ingest (parse → link → version) ──► PostgreSQL + pgvector ◄──┘
                                             ▲
  User ─► FastAPI ─► LangGraph flow ①–⑩ ─────┤ tools (search/expand/get/calc)
             │            │                  │
             │            ├─ Gemini (System 2: extract, draft)
             │            └─ DecisionModel (System 1: select, verify)
             └─► UI (chat + sources panel + clickable citations)
```

### 5.1 Data layer: Structured Legal Index (PostgreSQL 16 + pgvector)
graph สร้างจาก **โครงสร้างตัวบทจริง** ไม่ใช่ให้ LLM เดา entity (ต่างจาก GraphRAG)

```sql
laws(id, name, short_name, type, level, enacted_date, source_file, parent_law_id)
  -- type: act | decree | ministerial_reg | announcement ; level 1(act)..4(announcement)
provisions(id, law_id, chapter, section_no, paragraph_no, sub_no, text,
           valid_from, valid_to, amended_by, citation_key,  -- UNIQUE(citation_key, valid_from): 1 แถวต่อ 1 version
           embedding vector(1024))
  -- citation_key: "<LAW>:<section>:<paragraph>[:<sub>]" เช่น "LPA2541:118:1" (ทั้งวรรค), "LPA2541:118:1:(1)" (อนุมาตรา)
links(from_id, to_id, type, evidence)   -- ISSUED_UNDER | REFERS_TO | AMENDED_BY | REPEALED_BY
cases(id, deka_no UNIQUE, year, facts, holding, full_text, source_url, embedding)
case_links(case_id, provision_id)
issues(id, code, name, description, elements jsonb, formula_key, reviewed_by)
issue_links(issue_id, provision_id)
examples(id, source, question, answer_json, issues text[], verified bool, embedding)
runs(id, question_id, config jsonb, trace jsonb, answer_json, cost_usd, tokens, latency_ms, created_at)
```

**Parser ตัวบท (`src/ingest/parse_statute.py`)** — งานที่ยากที่สุด ทำให้ถูกก่อนทำอย่างอื่น
- ลำดับ: `หมวด` → `ส่วน` (ถ้ามี) → `มาตรา \d+(/\d+)?` → วรรค → อนุมาตรา `(\d+)`
- normalize ก่อน: เลขไทย ๐–๙ → อารบิก, ช่องว่าง/zero-width, ตัดหัวท้ายกระดาษ, "มาตรา ๑๑๘/๑"
- วรรค = ย่อหน้าใหม่ภายในมาตรา · อนุมาตรา = บรรทัดขึ้นต้น `(n)` · อนุมาตราอยู่ภายใต้วรรคที่นำหน้า
- **ห้ามตัด chunk ตามความยาว** chunk = 1 วรรค (มีข้อความทั้งมาตราเก็บไว้ให้ expand)
- เก็บข้อความที่ถูกยกเลิก ("(ยกเลิก)") เป็น provision ที่มี `valid_to`
- **Golden tests:** `tests/golden/provisions.yaml` เลือก 20 มาตราที่รู้โครงสร้าง (ม.17, 17/1, 118, 119, 61–63 ฯลฯ) ตรวจจำนวนวรรค/อนุมาตรา

**ISSUED_UNDER (`src/ingest/link_laws.py`)**
1. regex หา "อาศัยอำนาจตามความในมาตรา …" / "ตามมาตรา …" ในอารัมภบทของกฎหมายลูก
2. จับไม่ได้ → LLM ช่วยเสนอ พร้อมเก็บ `evidence` (ข้อความที่อ้าง)
3. คนตรวจ → `docs/review/links_review.csv` (ส่งอาจารย์ดูได้)

**ลำดับชั้นเมื่อขัดกัน:** กฎหมายลูกกำหนดรายละเอียดภายในกรอบที่แม่ให้ · ถ้าลูกเกินกรอบแม่ → ระบบแจ้งว่าอาจขัด และยึดกฎหมายแม่ (rule ใน `src/agent/rules/hierarchy.py` — ให้อาจารย์ยืนยันหลักนี้)

### 5.2 Retrieval tools (`src/index/tools.py`)
| Tool | หน้าที่ |
|---|---|
| `search_provisions(query, event_date, k=20)` | BM25 (ตัดคำ pythainlp `newmm`) + bge-m3 dense → **Reciprocal Rank Fusion** → bge-reranker-v2-m3 → กรอง `valid_from ≤ event_date < valid_to` (NULL = ไม่จำกัด) |
| `expand(provision_id)` | 1 hop: ทั้งมาตรา, กฎหมายลูก (ISSUED_UNDER), มาตราที่อ้างถึง, มาตราถัดไปในหมวดเดียวกันที่เกี่ยวข้อง |
| `get_provision(citation_key \| law, section, para, date)` | ดึงตรงตัว |
| `search_cases(facts, provision_ids, k=5)` | dense บน facts + boost ถ้า case_links ตรงมาตรา |
| `get_elements(issue_code)` | องค์ประกอบ + formula_key |
| `calc(kind, **params)` | คำนวณ deterministic |

หมายเหตุ: PostgreSQL full-text ตัดคำไทยไม่ได้ → ทำ BM25 ใน Python (`rank_bm25` หรือ `bm25s`) จาก token ที่ตัดด้วย pythainlp และ cache index ไว้ใน `data/processed/`

### 5.3 Reasoning flow (LangGraph — ระบบคุม)
```
① extract_facts     Gemini → FactsModel {event_date?, wage, wage_period, tenure, reason, parties, amounts...}
② spot_issues       Gemini เลือกจาก taxonomy เท่านั้น (+ เหตุผลต่อประเด็น)                 → B0
③ retrieve_law      search_provisions + expand ต่อประเด็น                                  → B1
④ retrieve_cases    search_cases ต่อประเด็น                                                 → A2, B1
⑤ select_citations  DecisionModel "บทนี้ใช้กับข้อเท็จจริงนี้ไหม" ต่อ candidate           → B1
⑥ check_elements    ต่อองค์ประกอบ: met / not_met / unknown (+ข้อเท็จจริงที่อ้าง)             → B2
                    unknown → ตอบแบบมีเงื่อนไข + เพิ่มคำถามถามกลับ
⑦ calculate         calc() — LLM ห้ามคิดเลข                                                 → A2
⑧ draft_answers     Gemini ×N (default 2) → AnswerJSON ตาม template + dynamic few-shot 2 ข้อ
⑨ verify_select     DecisionModel ให้คะแนนแต่ละร่าง (supported / consistent / complete)      → B3, A2
                    ต่ำกว่า threshold → revise 1 รอบ พร้อม feedback
⑩ validate_cites    ทุก citation_key/deka_no ต้องมีใน DB และมีผล ณ event_date
                    ไม่ผ่าน → ลบ/แก้ แล้ว re-render (ห้ามส่งคำตอบที่มี citation ผิด)
```
- State: `src/agent/state.py` (Pydantic) · แต่ละ node เป็นฟังก์ชันบริสุทธิ์รับ state คืน partial state
- ทุก node เขียน trace ลง `runs.trace`: input สรุป, output, confidence, tokens, cost, latency
- Timeout/retry: Gemini call retry 3 ครั้ง exponential backoff · node ล้ม → fallback ที่ปลอดภัย (ไม่ใช่ crash)

### 5.4 DecisionModel (System 1) — สลับได้ด้วย `DECIDER`
```python
class DecisionModel(Protocol):
    def decide(self, state: dict, questions: dict[str, QuestionSpec]) -> dict[str, Decision]: ...
# Decision = {p: float, confidence: float, choice: str|None, raw: dict}
```
| Backend | Endpoint / model | ค่าใช้จ่าย | หมายเหตุ |
|---|---|---|---|
| `openthai` | `iapp/OpenThai-SystemOne` (local) หรือ `POST api.iapp.co.th/v3/store/openthai/systemone` | ฟรี (API 1,000/วัน) | Apache 2.0, มีผลทดสอบภาษาไทย, **default** |
| `jev` | TypeSafe API, `jev-1.13.0` | $0.042/1M input, output ฟรี | ภาษาอังกฤษดีสุด ต้องทดสอบไทย, early access |
| `gemini` | Gemini JSON + self-consistency ×3 | ตาม API | fallback, ช้ากว่า |

- state ให้สั้น: facts + candidate 1 ตัว + holding ย่อ (ข้อมูลรก = แม่นน้อยลง)
- ตรวจ request/response format จากเอกสารจริงของแต่ละเจ้าก่อน implement (อย่าเดา endpoint)
- **Bake-off (Day 10):** ทั้ง 3 ตัวที่ ⑤ ⑨ บน dev100 → accuracy, ECE, cost, latency → เลือก default

### 5.5 Calculator (`src/calc/labor.py`)
ทุกฟังก์ชันคืน `CalcResult {amount, steps: list[str], citations: list[citation_key]}`
- ตัวเลขกฎหมายทั้งหมด (อัตรา, ขั้นอายุงาน, ตัวหาร) อยู่ใน `data/processed/rates.yaml` ผูกกับ `citation_key` + ช่วงเวลามีผล และ `RateBook.verify()` ตรวจว่าตัวเลขปรากฏในตัวบทใน DB (ตัวเลขที่เขียนเป็นคำ เช่น "หนึ่งเท่าครึ่ง" จะถูก flag ให้คนตรวจ)
- ค่าชดเชย (ม.118 — **อ่านอัตราและขั้นอายุงานจาก provisions ใน DB** ตาม event_date)
- สินจ้างแทนการบอกกล่าวล่วงหน้า (ม.17, 17/1)
- ค่าล่วงเวลา / ค่าทำงานในวันหยุด / ค่าล่วงเวลาในวันหยุด
- ค่าจ้างวันหยุดพักผ่อนประจำปีที่ไม่ได้ใช้
- ดอกเบี้ยและเงินเพิ่ม (ม.9)
- แปลงค่าจ้าง: รายเดือน ↔ รายวัน ↔ รายชั่วโมง (ระบุสูตรที่ใช้ใน steps)
- unit test ทุกฟังก์ชัน โดยเทียบกับตัวอย่างใน dev100 ที่มีการคำนวณ + ให้อาจารย์ยืนยันอย่างน้อย 3 เคส

### 5.6 Taxonomy + Elements (`data/processed/issues.yaml`)
- เริ่มจากประเด็นใน dev100 (ติดแท็กทุกข้อ) → รวมเป็น 20–40 ประเด็น
- แต่ละประเด็น: `code, name, elements[], primary_provisions[], formula_key?, common_pitfalls[]`
- **ส่งอาจารย์ตรวจในกลุ่ม LINE** ก่อนใช้จริง → บันทึก `reviewed_by`

### 5.7 Dynamic few-shot
- คลัง = dev100 ที่ `verified=true` → ดึง 2 ข้อที่ issue overlap สูงสุด (tie-break ด้วย embedding)
- ใช้เป็นแบบ **รูปแบบและวิธีปรับบท** เท่านั้น เนื้อหากฎหมายต้องมาจาก tools
- leave-one-out ตอนวัดผล · ห้ามมี test160

---

## 6. Tech stack

| ส่วน | เลือก |
|---|---|
| ภาษา / env | Python 3.11 + **uv** |
| Orchestration | LangGraph |
| API | FastAPI + Pydantic v2 |
| DB | PostgreSQL 16 + pgvector (Docker) |
| Thai NLP | pythainlp (newmm) |
| Embedding / Rerank | `BAAI/bge-m3` (1024-d) / `BAAI/bge-reranker-v2-m3` |
| LLM | `google-genai` SDK (Gemini 3.5 Flash) |
| UI | Streamlit (เร็วสุด) — แชท + แผงแหล่งที่มา + คลิก citation ดูตัวบทเต็ม |
| Deploy ชั่วคราว | 1 VM (Docker Compose: db + api + ui) เช่น VPS เล็ก / GCP e2-small บนบัญชีลูกค้า + HTTPS (Caddy) + basic auth |
| Quality | ruff, mypy (เฉพาะ src/agent, src/calc), pytest |

### โครงสร้าง repo
```
laborlex-th/
├── CLAUDE.md
├── README.md
├── Makefile
├── pyproject.toml
├── .env.example        # GEMINI_API_KEY, GEMINI_MODEL, IAPP_API_KEY, JEV_API_KEY, DATABASE_URL, DECIDER, APP_PASSWORD
├── docker-compose.yml
├── data/               # gitignored ยกเว้น MANIFEST และ processed/issues.yaml
│   ├── raw/ interim/ processed/ eval/
├── prompts/            # *.md มี version header
├── src/
│   ├── config.py
│   ├── ingest/         # drive_download.py, ocr.py, parse_statute.py, link_laws.py, load_cases.py, pipeline.py
│   ├── index/          # schema.sql, db.py, embed.py, bm25.py, tools.py
│   ├── agent/          # state.py, graph.py, nodes/, rules/, render.py
│   ├── decision/       # base.py, openthai.py, jev.py, gemini.py
│   ├── calc/           # labor.py
│   ├── eval/           # run_eval.py, judge.py, metrics.py, export_for_grading.py
│   ├── api/            # main.py
│   └── ui/             # app.py
├── tests/              # unit/, golden/, e2e/
└── docs/
    ├── PLAN.md  architecture.md  flow_diagram.(png|svg)
    ├── results/  review/  change_requests.md  questions_for_professors.md
```

### คำสั่ง (Makefile)
```bash
make setup        # uv sync + pre-commit
make db           # docker compose up -d db && apply schema
make ingest       # raw → interim → processed → DB
make test         # pytest -q
make eval-dev     # run_eval --set dev100 --leave-one-out → docs/results/
make eval-bar     # ข้อสอบเนติฯ
make serve        # api + ui local
make export-160   # (เฟส 2 เท่านั้น) รัน test160 → xlsx สำหรับอาจารย์ให้คะแนน
```

---

## 7. การวัดผล

- **Judge (`src/eval/judge.py`):** Gemini ให้คะแนนตาม rubric §3 → 6 เกณฑ์ + PASS + เหตุผล
  - **Calibrate กับคะแนนอาจารย์ของ baseline** (ขอผลรายข้อ) → รายงาน agreement ต่อเกณฑ์ (Cohen's κ)
  - ถ้า κ ต่ำในเกณฑ์ใด → ปรับ prompt judge ก่อนเชื่อผล
- **Metrics ทุกครั้ง:** PASS rate, % ได้ 2 รายเกณฑ์, retrieval Recall@10 (เทียบ gold_citations), citation hallucination rate (ต้อง = 0), ECE ของ DecisionModel, cost/คำถาม, latency p50/p95
- **Error analysis:** ทุกข้อที่ไม่ PASS ติดป้ายสาเหตุ `retrieval | selection | elements | calc | drafting | contradiction | format` → แก้กลุ่มใหญ่สุดก่อน
- **Ablation (เก็บไว้ใช้ในเปเปอร์):** Gemini เปล่า · +RAG ธรรมดา · +Legal Index · +elements · +calc · +DecisionModel · เต็มระบบ
- บันทึก `docs/results/YYYY-MM-DD_<config-hash>.md` (config, ตัวเลข, 5 ตัวอย่างข้อที่พลาด)
- **Export สำหรับอาจารย์ (`export_for_grading.py`):** xlsx คอลัมน์ `id, question, answer, A1..B3 (ว่าง), เหตุผล` เพื่อให้กรอกคะแนนได้ทันที

---

## 8. กฎการทำงานสำหรับ Claude Code

1. **Secrets:** ใช้ `.env` เท่านั้น · ห้าม print/log key · ห้ามเก็บรหัสผ่านบัญชีลูกค้าในไฟล์ใด ๆ ของ repo
2. **ห้ามเขียนตัวเลขกฎหมาย** (อัตรา, จำนวนวัน, จำนวนเงิน, เลขมาตรา) จากความจำใน prompt หรือโค้ด — ดึงจาก DB พร้อม citation_key
3. ทุก node: input/output เป็น Pydantic model, เขียน trace, มี unit test ≥ 1 เคส
4. Prompt อยู่ใน `prompts/` มี header `version:` · เปลี่ยน prompt = bump version
5. เปลี่ยนสิ่งที่กระทบคำตอบ → `make eval-dev` + บันทึกผล **ก่อน** merge
6. ห้ามเปิด/อ่าน `data/eval/test160.csv` นอกจากคำสั่ง `make export-160` ในเฟส 2
7. Cache embedding และ LLM call (key = hash(prompt+model+params)) · เคารพ rate limit
8. โค้ด/comment ภาษาอังกฤษ · ข้อความที่ผู้ใช้เห็นภาษาไทย
9. ไม่แน่ใจเรื่องกฎหมาย → เขียนคำถามใน `docs/questions_for_professors.md` (Frank จะถามในกลุ่ม LINE) **อย่าเดา**
10. Git: branch `feat/<topic>`, commit เล็กและอธิบายชัด, main ต้อง test ผ่านเสมอ
11. งบ API: ถ้ารัน eval เต็มชุดเกิน 3 ครั้ง/วัน ให้ใช้ subset 30 ข้อ (stratified ตาม difficulty) ก่อน

---

## 9. สถานะ / สิ่งที่รอจากลูกค้า
- [x] สัญญาและราคา (9,000 บาท, 4,500 × 2)
- [x] บัญชีโครงการ Google (ลูกค้าให้ Frank เข้าถึง — ใช้เพื่อสร้าง API key และดาวน์โหลดไฟล์เท่านั้น)
- [ ] ดาวน์โหลดไฟล์กฎหมาย 4 โฟลเดอร์ → `data/raw/laws/`
- [ ] โค้ดเวอร์ชันเดิม (`deliverable.zip`) + โค้ดคนเก่า
- [ ] ข้อมูลฎีกาที่คนเก่าดึงไว้
- [x] dev100 (100 ข้อ DEV) · [ ] คะแนน baseline รายข้อ
- [x] Gemini API key · [ ] budget alert
- [ ] กลุ่ม LINE กับอาจารย์ 3 ท่าน
- [ ] test160 (ก่อนเริ่มเฟส 2)
