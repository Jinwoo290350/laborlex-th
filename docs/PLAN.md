# PLAN.md — แผนงาน LaborLex-TH

> วันที่ในแผนนี้สมมติว่าได้ข้อมูลครบภายใน **1 ต.ค. 2569** ถ้าข้อมูลมาช้า ให้เลื่อนทั้งแผนตามวันที่ได้ข้อมูลจริง (สัญญาข้อ 3.4)
> ทุกเย็นวันอาทิตย์ส่งอัปเดตสั้น ๆ ให้ลูกค้าใน Discord (ทำอะไรไป / ตัวเลขล่าสุด / ต้องการอะไร)
> (คุยกับอาจารย์ = กลุ่ม LINE · อัปเดตลูกค้า = Discord)

## ภาพรวม

| ช่วง | วันที่ (โดยประมาณ) | เป้าหมาย | Milestone |
|---|---|---|---|
| Week 0 | 30 ก.ย.–1 ต.ค. | เตรียมข้อมูล + repo | ข้อมูลครบใน `data/raw/` |
| Week 1 | 2–8 ต.ค. | Data layer + retrieval | ค้นตัวบทได้ถูกวรรค, วัด Recall@10 ได้ |
| Week 2 | 9–15 ต.ค. | Agent flow + DecisionModel + eval | PASS dev100 รอบแรก + bake-off |
| Week 3 | 16–19 ต.ค. | ปรับแม่นยำ + UI + deploy | **ส่งมอบเฟส 1** (19 ต.ค.) |
| อาจารย์ทดสอบ | 20 ต.ค.–~9 พ.ย. | แก้ตาม feedback ≤ 2 รอบ | **รับเงินงวด 1** |
| เฟส 2 | +7 วันหลังได้ test160 | รัน 160 + อธิบายระบบ | **รับเงินงวด 2** |
| หลังประเมิน | +21 วันรอผล, +14 วันแก้ | PASS ≥ 90% | ปิดโปรเจกต์ |

---

## Week 0 — เตรียมการ (30 ก.ย.–1 ต.ค.)

- [ ] สร้าง GitHub repo **private** `laborlex-th` (บัญชี Jinwoo290350) + วาง CLAUDE.md, PLAN.md — *git init local แล้ว (30 ก.ย.) รอ push*
- [ ] ล็อกอินบัญชีโครงการ (Chrome profile แยก) → แชร์ 4 โฟลเดอร์ Drive มาบัญชีตัวเองแบบ Viewer หรือดาวน์โหลด — *Drive ที่เชื่อมกับ Claude มองไม่เห็นโฟลเดอร์ (30 ก.ย.)*
- [ ] สร้าง Gemini API key ชื่อ `laborlex-frank` → `.env` · ตั้ง budget alert
- [ ] สมัคร iApp API key (OpenThai-SystemOne) · ลองขอสิทธิ์ Jev
- [ ] ขอจากลูกค้า: `deliverable.zip`, โค้ดคนเก่า, ข้อมูลฎีกา, dev100 + คะแนนรายข้อ, เข้ากลุ่ม LINE
- [ ] ส่งสัญญาให้ลูกค้าเซ็น

**Done เมื่อ:** ไฟล์ทั้งหมดอยู่ใน `data/raw/` + `MANIFEST.csv` (`make manifest`) และ repo ขึ้น GitHub

---

## Week 1 — Data layer + Retrieval (2–8 ต.ค.)

### Day 1 (2 ต.ค.) — Setup + สำรวจข้อมูล
- [x] `uv init`, Makefile, docker-compose (Postgres+pgvector), `schema.sql`, `.env.example`, pre-commit — *เสร็จ 30 ก.ย.*
- [ ] อ่านโค้ดเดิม + โค้ดคนเก่า → จด `docs/legacy_review.md` (ใช้อะไรต่อได้ / ปัญหาที่เจอ)
- [ ] สำรวจไฟล์กฎหมาย: ชนิดไฟล์, เป็นข้อความหรือสแกน, จำนวนฉบับ → ตัดสินใจเรื่อง OCR
- [ ] แปลง dev100 → `data/eval/dev100.csv` ตาม schema
**Output:** DB รันได้, รายงานสำรวจข้อมูล 1 หน้า

### Day 2–3 (3–4 ต.ค.) — Parser ตัวบท ⭐ งานสำคัญที่สุด
- [x] normalize (เลขไทย, whitespace, header/footer) — *30 ก.ย.*
- [x] parse หมวด → มาตรา → วรรค → อนุมาตรา + citation_key — *30 ก.ย., ทดสอบกับข้อความสังเคราะห์*
- [ ] golden tests 20 มาตรา (ม.17, 17/1, 118, 119, 61–63, …) — *harness พร้อม, รอกรอกจำนวนวรรค/อนุมาตราจากไฟล์จริง*
- [ ] OCR + ตรวจเลขมาตรา (ถ้าเป็นไฟล์สแกน)
**Done เมื่อ:** golden tests ผ่าน 100% และทุก provision มี citation_key ไม่ซ้ำ

### Day 4 (5 ต.ค.) — กฎหมายลูก + version
- [ ] parse พ.ร.ก. / กฎกระทรวง / ประกาศ (`parse(text, unit="ข้อ")` รองรับแล้ว)
- [ ] ISSUED_UNDER ด้วย regex → LLM ช่วยเฉพาะที่เหลือ → `docs/review/links_review.csv`
- [ ] valid_from / valid_to / amended_by
**Done เมื่อ:** สุ่มตรวจ 20 ลิงก์ถูก ≥ 19

### Day 5 (6 ต.ค.) — ฎีกา
- [ ] โหลดฎีกาที่มี → กรองเฉพาะแรงงาน
- [ ] สกัด holding (หลักที่ศาลวาง) + เลขมาตราที่อ้าง → case_links
**Done เมื่อ:** ค้นฎีกาด้วยเลขมาตราได้

### Day 6 (7 ต.ค.) — Retrieval
- [ ] embed bge-m3, BM25 (pythainlp), RRF, reranker, filter ตามวันที่
- [ ] tools: search_provisions, expand, get_provision, search_cases
- [ ] ติด gold_citations ใน dev100 (จากเฉลย) → วัด Recall@10
**Done เมื่อ:** Recall@10 วัดได้และบันทึกผล (เป้า ≥ 0.9)

### Day 7 (8 ต.ค.) — Taxonomy + Calculator
- [ ] ติดแท็กประเด็น dev100 ทุกข้อ → `issues.yaml` 20–40 ประเด็น + elements
- [ ] **ส่ง taxonomy + elements ให้อาจารย์ตรวจในกลุ่ม LINE**
- [ ] `calc/labor.py` + unit tests (อ่านอัตราจาก DB) — *โครงเสร็จ 30 ก.ย. (RateBook + verify), รอกรอก `rates.yaml` หลัง ingest*
**Done เมื่อ:** calc tests ผ่าน, ส่ง taxonomy ให้อาจารย์แล้ว

📨 **อัปเดตลูกค้า (อาทิตย์ 4 ต.ค.):** repo + parser พร้อม, รอข้อมูลอะไรบ้าง
📨 **อัปเดตลูกค้า (อาทิตย์ 11 ต.ค.):** Legal Index เสร็จ + Recall@10 + PASS รอบแรก + ผล bake-off

---

## Week 2 — Agent + Eval (9–15 ต.ค.)

### Day 8–9 (9–10 ต.ค.) — LangGraph flow ①–⑩
- [ ] state.py, nodes ทั้ง 10, render.py (JSON → markdown ตาม template)
- [ ] trace ลง `runs`, retry/fallback
- [ ] e2e test 5 ข้อจาก dev100
**Done เมื่อ:** ตอบ dev100 ได้ครบ 100 ข้อโดยไม่ crash และ citation hallucination = 0

### Day 10 (11 ต.ค.) — DecisionModel bake-off
- [ ] backends: openthai, jev, gemini
- [ ] รันที่ ⑤ ⑨ บน dev100 → accuracy, ECE, cost, latency → เลือก default
**Done เมื่อ:** ตารางเทียบ 3 ตัวใน `docs/results/`

### Day 11 (12 ต.ค.) — Few-shot + Judge + Eval รอบแรก
- [ ] คลัง few-shot + leave-one-out
- [ ] judge.py + calibrate กับคะแนนอาจารย์ baseline (κ ต่อเกณฑ์)
- [ ] `make eval-dev` รอบแรก
**Done เมื่อ:** มีตัวเลข PASS รอบแรก + judge κ

### Day 12–15 (13–16 ต.ค.) — Error analysis loop
ทุกวัน: รัน eval → ติดป้ายสาเหตุข้อที่ไม่ PASS → แก้กลุ่มใหญ่สุด → รันใหม่ → บันทึก
- ลำดับที่น่าจะเจอ: retrieval → elements → calc → drafting/contradiction → format
- [ ] ทดสอบกับข้อสอบเนติฯ (ที่ไม่ซ้ำ test160) เพื่อกัน overfit dev100
- [ ] ablation อย่างน้อย 3 config เก็บไว้
**เป้า:** PASS บน dev100 (leave-one-out) ≥ 85% ก่อนส่งอาจารย์

---

## Week 3 — UI + Deploy + ส่งมอบเฟส 1 (16–19 ต.ค.)

### Day 16–17 (17–18 ต.ค.) — UI + Deploy
- [ ] Streamlit: ช่องถาม, คำตอบ, แผงแหล่งที่มา, คลิก citation ดูตัวบทเต็ม + วันที่มีผล
- [ ] FastAPI endpoint `/ask`
- [ ] VM + Docker Compose + HTTPS + รหัสผ่าน
- [ ] smoke test 10 ข้อบนเครื่องที่ deploy
### Day 18 (19 ต.ค.) — ส่งมอบเฟส 1
- [ ] README (ติดตั้ง, รัน, ตั้งค่า), คู่มือใช้สำหรับอาจารย์ 1 หน้า
- [ ] แจ้งลูกค้า: ลิงก์ + รหัสผ่าน + ผล dev100 ล่าสุด + วันหมดอายุ deploy (30 วัน)

**Done เมื่อ:** อาจารย์เข้าใช้ได้ · เริ่มนับ 7 วันสำหรับ feedback

---

## ช่วงอาจารย์ทดสอบ (20 ต.ค.–~9 พ.ย.)
- [ ] รวบรวม feedback ลง `docs/review/professor_feedback.md` (ข้อ, ปัญหา, สาเหตุ, แก้แล้ว?)
- [ ] รอบแก้ 1 (≤ 7 วัน) → แจ้ง → รอบแก้ 2 (≤ 7 วัน)
- [ ] ขอยืนยันเป็นข้อความว่า "โดยรวมโอเค" → **แจ้งรับเงินงวด 1**

## เฟส 2 (7 วันหลังได้ test160)
- [ ] ตรวจ test160 ซ้ำกับคลัง few-shot/ข้อสอบเนติฯ ไหม (ต้องไม่ซ้ำ)
- [ ] freeze config (tag `v1.0-eval160`) → `make export-160` → xlsx ส่งอาจารย์
- [ ] ไดอะแกรม flow ระบบ + `docs/architecture.md`
- [ ] ประชุมอธิบาย flow และตรรกะ ≤ 2 ชม. (เตรียมสไลด์สั้น/ใช้ไดอะแกรม)
- [ ] **แจ้งรับเงินงวด 2**
- [ ] รอผลคะแนน ≤ 21 วัน → ถ้า < 90% แก้ 2 รอบใน 14 วัน

## ปิดโปรเจกต์
- [ ] ส่งมอบโค้ด (โอนสิทธิ์หลังได้เงินครบ) + ลบ/หมุน API key ที่ Frank สร้าง
- [ ] แนะนำลูกค้าเปลี่ยนรหัสผ่านบัญชีโครงการ · ปิด VM ชั่วคราว
- [ ] เก็บ traces + ablation ไว้สำหรับเปเปอร์ · คุยเรื่องชื่อผู้เขียน / โปรเจกต์ถัดไป (scrape ฎีกา, ไดอะแกรม)

---

## Risk register

| ความเสี่ยง | สัญญาณเตือน | รับมือ |
|---|---|---|
| ไฟล์กฎหมายเป็น PDF สแกน OCR ไม่แม่น | Day 1 สำรวจเจอ | ใช้ฉบับข้อความจาก krisdika เทียบ, ตรวจเลขมาตราด้วย golden tests |
| ข้อมูลฎีกาจากคนเก่าไม่มีโครงสร้าง | Day 5 | ใช้เท่าที่สกัดได้ ที่เหลือเสนอเป็นงาน scrape แยก |
| PASS ติดเพดานต่ำกว่า 85% บน dev100 | Day 13–15 | ดู error label: ถ้า drafting/contradiction มาก → เพิ่ม N ร่าง + verify เข้มขึ้น; ถ้า retrieval → ปรับ chunk/expand |
| Judge ไม่ตรงกับอาจารย์ | κ ต่ำ Day 11 | ปรับ prompt judge, ใช้คะแนนอาจารย์ baseline เป็น few-shot ของ judge |
| Jev ใช้ภาษาไทยไม่ดี | bake-off | ใช้ openthai/gemini (ไม่มีต้นทุนเพิ่ม) |
| ค่า API บาน | budget alert | subset 30 ข้อ, cache, ลด N ร่าง |
| ลูกค้าขอเพิ่มงานกลางทาง | ข้อความใน LINE/Discord | บันทึก change_requests.md + เสนอราคาแยก (สัญญาข้อ 2.3) |
| เวลาเรียน/สอบชน | ปฏิทินมหาลัย | แจ้งลูกค้าล่วงหน้า, ย้ายงาน UI ไปทำคู่ขนานได้ |
| อาจารย์ตรวจช้า | เกิน 7 วัน | สัญญาข้อ 6.3 ถือว่าผ่าน — แจ้งอย่างสุภาพพร้อมอ้างข้อ |
