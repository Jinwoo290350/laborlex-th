const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType,
  HeadingLevel, AlignmentType, BorderStyle, LevelFormat, Footer, PageNumber,
} = require("docx");

const FONT = "TH Sarabun New";
const PAGE_W = 11906, MARGIN = 1134, W = PAGE_W - 2 * MARGIN;
const border = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
const borders = { top: border, bottom: border, left: border, right: border };
const t = (text, o = {}) => new TextRun({ text, font: FONT, ...o });
const p = (c, o = {}) => new Paragraph({ children: Array.isArray(c) ? c : [t(c)], spacing: { after: 80 }, ...o });
const h1 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t(s)], spacing: { before: 240, after: 100 } });
const h2 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [t(s)], spacing: { before: 160, after: 60 }, keepNext: true });
const li = (s, bold) => new Paragraph({ numbering: { reference: "bul", level: 0 }, spacing: { after: 40 },
  children: bold ? [t(bold, { bold: true }), t(s)] : [t(s)] });
const num = (s, bold) => new Paragraph({ numbering: { reference: "num", level: 0 }, spacing: { after: 40 },
  children: bold ? [t(bold, { bold: true }), t(s)] : [t(s)] });

function table(cols, rows) {
  return new Table({
    width: { size: cols.reduce((a, b) => a + b, 0), type: WidthType.DXA }, columnWidths: cols,
    rows: rows.map((r, i) => new TableRow({ tableHeader: i === 0, cantSplit: true,
      children: r.map((c, j) => new TableCell({
        width: { size: cols[j], type: WidthType.DXA }, borders,
        margins: { top: 50, bottom: 50, left: 90, right: 90 },
        shading: i === 0 ? { fill: "DCE8F5", type: ShadingType.CLEAR, color: "auto" } : undefined,
        children: [p([t(c, { bold: i === 0 })])],
      })) })),
  });
}

const C = [];
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 },
  children: [t("รายงานความคืบหน้า LaborLex-TH", { bold: true, size: 40 })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
  children: [t("ระบบตอบคำถามกฎหมายแรงงานไทย · ฉบับวันที่ 1 ตุลาคม 2569", { size: 30 })] }));

C.push(h1("1. สรุปสั้น"));
C.push(li("ระบบครบทั้ง 10 ขั้น (ข้อเท็จจริง → ประเด็น → ค้นตัวบท → เลือกมาตรา → ตรวจองค์ประกอบ → คำนวณ → ร่าง → ตรวจร่าง → ตรวจ citation) และเริ่มทดสอบกับชุดคำถาม dev แล้ว"));
C.push(li("ทดสอบรอบแรก 11 ข้อ (คละทุกหมวด): ผ่านครบ 6 เกณฑ์ 11/11 ข้อ และคำตอบอ้างมาตราที่เฉลยระบุครบ 24/24 มาตรา (baseline Gemini เดิม 64%)", ""));
C.push(li("ต้นทุนประมาณ 5–6 บาทต่อคำถาม (รวมการให้คะแนนอัตโนมัติ)"));
C.push(li("ตรวจพบข้อผิดพลาดสำคัญในไฟล์กฎหมายที่ได้รับ และแก้โดยใช้ฉบับปรับปรุงล่าสุดจากสำนักงานคณะกรรมการกฤษฎีกา"));
C.push(p([t("หมายเหตุ: ", { bold: true }), t("ผล 11 ข้อยังเป็นการทดสอบขนาดเล็กและให้คะแนนด้วย AI ที่ยังไม่ได้เทียบกับคะแนนอาจารย์ จึงใช้ดูแนวโน้มเท่านั้น ตัวเลขจริงคือผลที่อาจารย์ประเมิน test160")]));

C.push(h1("2. ผลการทดสอบ"));
C.push(table([3800, 2900, 2938], [
  ["ตัววัด", "ผล", "หมายเหตุ"],
  ["PASS (ได้ 2 ครบทั้ง 6 เกณฑ์)", "11/11 ข้อ", "ให้คะแนนโดย AI ตาม rubric"],
  ["รายเกณฑ์ A1 · A2 · B0 · B1 · B2 · B3", "100% ทุกเกณฑ์", "ชุด 11 ข้อ"],
  ["มาตราในเฉลยที่คำตอบอ้างถึง", "24/24 (100%)", "ตรวจตรง ไม่ใช้ AI ให้คะแนน"],
  ["การอ้างมาตรา/ฎีกาที่ไม่มีจริง", "0", "ระบบตัดทิ้งก่อนส่งคำตอบ"],
  ["ค่าชดเชยที่คำนวณ (เช่น 40,000 × 300/30)", "400,000 บาท ตรงเฉลย", "คำนวณด้วยโค้ด ไม่ใช่ AI"],
  ["เวลาตอบ", "ประมาณ 30–70 วินาที/ข้อ", ""],
  ["ต้นทุน", "ประมาณ 5–6 บาท/ข้อ", "Gemini 3.5 Flash"],
]));
C.push(h2("ข้อจำกัดของผลรอบนี้"));
C.push(li("ทดสอบเพียง 11 ข้อ เพื่อประหยัดงบ API"));
C.push(li("รายการประเด็น (taxonomy) ร่างจากชุด dev100 เอง ผลบน dev จึงน่าจะสูงกว่า test160"));
C.push(li("การให้คะแนนอัตโนมัติยังไม่ได้เทียบกับคะแนนอาจารย์"));

C.push(h1("3. สิ่งที่ตรวจพบและแก้ไขในข้อมูลที่ได้รับ"));
C.push(table([3000, 3900, 2738], [
  ["ไฟล์", "ปัญหาที่พบ", "การแก้ไข"],
  ["พ.ร.บ.คุ้มครองแรงงาน (.docx)", "เลขมาตราผิด 3 จุด (85/1→84/1, 115/(6)→115/1, 126/1→125/1) และไม่มี ม.44, ม.57/1", "ใช้ PDF ฉบับกฤษฎีกา (รวมแก้ไขถึงฉบับที่ 9 พ.ศ. 2568)"],
  ["พ.ร.บ.แรงงานสัมพันธ์ (.docx)", "มาตรา ทวิ/ตรี 5 มาตราถูกรวมเข้ามาตราหลัก (17 ทวิ, 120 ทวิ, 120 ตรี, 129 ทวิ, 157 ทวิ) · PDF เป็นฉบับปี 2518 ที่วรรณยุกต์หาย", "ใช้ฉบับปรับปรุงล่าสุดจากกฤษฎีกา"],
  ["กฎกระทรวง ฉบับที่ 1, 14, 15", "ฉบับที่ 14/15 คือการแก้ไขฉบับที่ 1 · ไฟล์ฉบับที่ 1 เป็นฉบับเก่า", "ใช้ฉบับที่ 1 ที่รวมการแก้ไขแล้ว"],
  ["กฎกระทรวงค่าล่วงเวลา 2568", "ข้อความ OCR ผิด", "ใช้ฉบับจากกฤษฎีกา"],
  ["กฎกระทรวงอื่น ๆ", "OCR ผิดหลายจุด (เช่น “ถูกจ้าง” แทน “ลูกจ้าง”) · ฉบับที่ 2–13 ไม่พบในฐานกฤษฎีกาที่ยังใช้บังคับ", "ยังใช้ไฟล์เดิม · ต้องตรวจสถานะ"],
  ["ชีต dev100", "คอลัมน์ G (ตาม ref) ผิดบางข้อ · แท็บ Sheet1 มีแถวที่ไม่ใช่ DEV ~60 แถว", "ใช้คอลัมน์ H เป็นเฉลย · ไม่เปิด/ไม่ใช้ Sheet1"],
]));
C.push(h2("กฎหมายที่เพิ่มเข้าฐานข้อมูล (เฉลยหรือตัวอย่างคำตอบอ้างถึงแต่ไม่อยู่ในโฟลเดอร์)"));
C.push(li("ประมวลกฎหมายแพ่งและพาณิชย์ เฉพาะส่วนที่เกี่ยวกับคดีแรงงาน (จ้างแรงงาน, นิติกรรม/อายุความ, บุริมสิทธิ, ละเมิด, การสมรส)"));
C.push(li("พ.ร.บ.จัดตั้งศาลแรงงานและวิธีพิจารณาคดีแรงงาน พ.ศ. 2522 (ม.49 เลิกจ้างไม่เป็นธรรม)"));
C.push(p("ปัจจุบันฐานข้อมูลมี 1,709 วรรค/อนุมาตรา จาก 21 ฉบับ พร้อมประวัติการแก้ไขของแต่ละมาตรา"));

C.push(h1("4. สิ่งที่ระบบทำได้แล้ว"));
C.push(li(" ระบบกำหนดลำดับการคิดเอง AI ทำเฉพาะขั้นที่ต้องใช้ภาษา", "ระบบคุมกระบวนการ:"));
C.push(li(" ทุก citation ต้องมีในฐานข้อมูล ต้องเป็นมาตราที่ระบบค้นและเลือกไว้ และต้องมีผลบังคับ ชื่อมาตราสร้างจากฐานข้อมูลเสมอ", "ไม่มีมาตราที่แต่งขึ้น:"));
C.push(li(" อัตราค่าชดเชย ค่าล่วงเวลา ตัวหาร 30 (ม.68) ดึงจากตัวบทในฐานข้อมูลและตรวจซ้ำทุกตัวเลข อายุงานคำนวณจากวันที่ด้วยโค้ด", "คำนวณด้วยโค้ด:"));
C.push(li(" คำตอบบอกกฎหมายแม่และกฎหมายลูกคู่กัน และแนบหมายเหตุการแก้ไขมาตราจากฐานข้อมูล", "ลำดับชั้นและฉบับกฎหมาย:"));
C.push(li(" ข้อเท็จจริงไม่พอ → ตอบแบบมีเงื่อนไข และระบุสิ่งที่ต้องถามเพิ่ม", "ไม่เดา:"));
C.push(li(" คำตอบตาม template ของลูกค้า (คำตอบเบื้องต้น → ประเด็น → รายประเด็น → ตารางความเห็นทางกฎหมาย)", "รูปแบบ:"));
C.push(li(" หน้าแชท + แผงแหล่งที่มา (คลิกดูตัวบทเต็มและประวัติแก้ไข) + ขั้นตอนการคิดของระบบ พร้อมรหัสผ่าน", "UI:"));
C.push(h2("ทดสอบโมเดลตัดสินใจ (DecisionModel)"));
C.push(p("ทดสอบ OpenThai-SystemOne (iApp) กับการเลือกมาตรา 450 คู่: แยกมาตราที่ใช้/ไม่ใช้ได้ไม่ดีพอ (AUC 0.66) และทำให้ลำดับแย่ลง จึงใช้ Gemini เป็นค่าเริ่มต้น โครงสร้างรองรับการสลับไป OpenThai/Jev เมื่อมีรุ่นที่ดีกว่า"));

C.push(h1("5. สิ่งที่ต้องการจากลูกค้า"));
C.push(num(" ยืนยันว่าคอลัมน์ H ของชีต dev คือเฉลย", "เฉลย:"));
C.push(num(" แท็บ Sheet1 มีแถวที่ไม่ใช่ DEV ~60 แถว ถ้าเป็นข้อ test ควรย้ายออกจากชีตที่แชร์ (กัน data leakage)", "Sheet1:"));
C.push(num(" ส่งเอกสาร “ขอความอนุเคราะห์ตรวจสอบ” (แนบ) ให้อาจารย์ ยืนยันหลักการ 3 ข้อ และตรวจรายการประเด็น 28 ประเด็น", "อาจารย์:"));
C.push(num(" ถ้ามีไฟล์ที่ใช้คำนวณคะแนน baseline รายเกณฑ์อยู่แล้ว ขอไฟล์นั้น (ไม่ต้องให้อาจารย์ทำเพิ่ม)", "คะแนน baseline:"));
C.push(num(" ข้อมูลฎีกาที่คนเก่าดึงไว้ (การ scrape ใหม่เป็นงานแยกตามสัญญา)", "ฎีกา:"));
C.push(num(" ยืนยันการเพิ่ม ป.พ.พ. และ พ.ร.บ.จัดตั้งศาลแรงงานฯ เข้าฐานข้อมูล · สถานะกฎกระทรวงฉบับที่ 2–13", "กฎหมาย:"));

C.push(h1("6. ขั้นต่อไป"));
C.push(li("ปรับรายการประเด็นตามความเห็นอาจารย์ แล้วทดสอบชุด 30 ข้อ (ประมาณ 170 บาท)"));
C.push(li("เพิ่มข้อมูลฎีกาเมื่อได้รับ · เตรียม deploy ให้อาจารย์ทดลองใช้ 30 วัน (ส่งมอบเฟส 1)"));
C.push(li("เฟส 2: รัน test160 ด้วยระบบที่ freeze แล้ว → ไฟล์ Excel ให้อาจารย์ให้คะแนน"));

const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: 30 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: FONT, color: "1F3864" }, paragraph: { outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: FONT, color: "2E5597" }, paragraph: { outlineLevel: 1 } },
    ],
  },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: 16838 }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [t("LaborLex-TH · รายงานความคืบหน้า · หน้า ", { size: 24 }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 24 })] })] }) },
    children: C,
  }],
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(process.argv[2], b); console.log("wrote", b.length); });
