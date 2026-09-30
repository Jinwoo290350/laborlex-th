const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType,
  HeadingLevel, AlignmentType, BorderStyle, LevelFormat, PageBreak, Footer, PageNumber,
} = require("docx");

const tax = JSON.parse(fs.readFileSync(__dirname + "/tax.json", "utf8"));
const FONT = "TH Sarabun New";
const PAGE_W = 11906, MARGIN = 1134;               // A4, 2 cm margins
const W = PAGE_W - 2 * MARGIN;                     // 9638 DXA content width
const GREY = "EDEDED", BLUE = "DCE8F5";
const border = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
const borders = { top: border, bottom: border, left: border, right: border };

const t = (text, o = {}) => new TextRun({ text, font: FONT, ...o });
const p = (children, o = {}) =>
  new Paragraph({ children: Array.isArray(children) ? children : [t(children)], spacing: { after: 80 }, ...o });
const h1 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t(s)], spacing: { before: 240, after: 120 } });
const h2 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [t(s)], spacing: { before: 200, after: 80 }, keepNext: true });
const bullet = (s) => new Paragraph({ numbering: { reference: "bul", level: 0 }, children: [t(s)], spacing: { after: 40 } });

function cell(children, width, o = {}) {
  const kids = (Array.isArray(children) ? children : [children]).map((c) => (typeof c === "string" ? p(c) : c));
  return new TableCell({
    width: { size: width, type: WidthType.DXA }, borders,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    shading: o.fill ? { fill: o.fill, type: ShadingType.CLEAR, color: "auto" } : undefined,
    children: kids,
  });
}
function table(cols, rows, headerFill = GREY) {
  return new Table({
    width: { size: cols.reduce((a, b) => a + b, 0), type: WidthType.DXA }, columnWidths: cols,
    rows: rows.map((r, i) => new TableRow({
      tableHeader: i === 0, cantSplit: true,
      children: r.map((c, j) => cell(i === 0 ? p([t(c, { bold: true })]) : c, cols[j], { fill: i === 0 ? headerFill : undefined })),
    })),
  });
}

const children = [];
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
  children: [t("ขอความอนุเคราะห์ตรวจสอบ", { bold: true, size: 40 })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 },
  children: [t("ระบบตอบคำถามกฎหมายแรงงาน LaborLex-TH", { bold: true, size: 36 })] }));

children.push(p("เรียน อาจารย์ทุกท่าน"));
children.push(p("ระบบจะแยกคำถามเป็น “ประเด็น” แล้วตรวจ “องค์ประกอบ” ของแต่ละประเด็นกับข้อเท็จจริงก่อนตอบ เอกสารนี้ขอให้อาจารย์ช่วยยืนยันหลักการ 3 ข้อ และตรวจรายการประเด็นกับองค์ประกอบที่ระบบใช้ เพื่อให้คำตอบตรงกับแนวที่อาจารย์ใช้ตรวจ"));
children.push(p([t("วิธีตอบ: ", { bold: true }), t("ส่วนที่ 1–2 ตอบสั้น ๆ ในช่องว่าง · ส่วนที่ 3 ติ๊ก ✓ (ถูก) หรือ ✗ (ผิด/ควรแก้) ต่อองค์ประกอบ และเขียนแก้เฉพาะที่ผิด ไม่ต้องให้คะแนน")]));
children.push(p([t("เวลาโดยประมาณ: ", { bold: true }), t("ส่วนที่ 1–2 ประมาณ 10 นาที · ส่วนที่ 3 ประมาณ 45–60 นาที (แบ่งกันตรวจคนละช่วงได้)")]));

// ---------- Part 1
children.push(h1("ส่วนที่ 1  หลักการที่ขอให้ยืนยัน"));
const q = [
  ["1", "คำถามที่ไม่ระบุวันเกิดเหตุ ระบบจะตอบตามกฎหมายฉบับปัจจุบัน และถ้ามาตราที่ใช้เคยถูกแก้ไข จะหมายเหตุหลักเดิมไว้สั้น ๆ ตรงกับแนวที่อาจารย์ใช้ตรวจหรือไม่"],
  ["2", "ถ้ากฎหมายลำดับรอง (กฎกระทรวง/ประกาศ) กำหนดเกินกรอบที่กฎหมายแม่ให้อำนาจไว้ ระบบจะแสดงทั้งสองฉบับ แจ้งว่า “อาจขัดกับกฎหมายแม่” และยึดตามกฎหมายแม่ อาจารย์เห็นด้วยหรือไม่"],
  ["3", "สินจ้างแทนการบอกกล่าวล่วงหน้า (ม.17 วรรคสอง และ ม.17/1 พ.ร.บ.คุ้มครองแรงงาน) ระบบคำนวณว่า: เลิกจ้างวันที่ X โดยไม่บอกกล่าว → จ่ายค่าจ้างตั้งแต่วันที่ X ถึงกำหนดจ่ายค่าจ้างคราวถัดไป ถัดจากกำหนดจ่ายคราวแรกที่ถึงหลังวันที่ X และไม่เกินสามเดือน\nตัวอย่าง: จ่ายเงินเดือนทุกสิ้นเดือน เลิกจ้างวันที่ 10 มีนาคม → จ่ายถึง 30 เมษายน วิธีนับนี้ถูกต้องหรือไม่"],
];
const qrows = [["ข้อ", "คำถาม", "ความเห็นอาจารย์"]];
for (const [n, s] of q) {
  qrows.push([n, s.split("\n").map((x) => p(x)), [p("☐ ถูกต้อง   ☐ ไม่ถูกต้อง"), p("หมายเหตุ: ....................................")]]);
}
children.push(table([700, 5738, 3200], qrows, BLUE));

// ---------- Part 2
children.push(h1("ส่วนที่ 2  ข้อเสนอปรับรายการประเด็น"));
children.push(p("ทีมงานตรวจรายการประเด็นเบื้องต้นแล้ว มีข้อเสนอต่อไปนี้ ขออาจารย์ตัดสิน"));
const prop = [
  ["1", "รวมประเด็น “นิยามการเลิกจ้างและเงินค้างจ่าย” (ข้อ 28) เข้ากับ “ค่าชดเชยการเลิกจ้าง” (ข้อ 1) และรวม “ความรับผิดของนายจ้างและตัวแทน” (ข้อ 25) เข้ากับ “สถานะลูกจ้างและสัญญาจ้างแรงงาน” (ข้อ 10) เพราะขอบเขตซ้อนกัน"],
  ["2", "แยกประเด็นใหม่ “อายุความ” (ป.พ.พ. ม.193/34) ออกจาก “อำนาจพนักงานตรวจแรงงานและสิทธิเรียกร้อง” (ข้อ 18)"],
  ["3", "เพิ่มประเด็น “การเลิกจ้างที่ไม่เป็นธรรม” (ม.49 พ.ร.บ.จัดตั้งศาลแรงงานและวิธีพิจารณาคดีแรงงาน)"],
  ["4", "ควรเพิ่มประเด็นต่อไปนี้หรือไม่ (ยังไม่มีในชุดคำถามพัฒนา): ข้อบังคับเกี่ยวกับการทำงาน · ค่าจ้างขั้นต่ำ · การใช้แรงงานเด็ก · กำหนดเวลาจ่ายค่าจ้าง ดอกเบี้ยและเงินเพิ่ม (ม.9) · ผู้รับเหมาช่วงและการจ้างเหมาค่าแรง · ข้อตกลงเกี่ยวกับสภาพการจ้าง\n(ถ้าเพิ่มประเด็นมากเกินไป ระบบอาจยกประเด็นเกินจำเป็นมาตอบ กรุณาเลือกเฉพาะที่พบบ่อย)"],
];
const prows = [["ข้อ", "ข้อเสนอ", "ความเห็นอาจารย์"]];
for (const [n, s] of prop) prows.push([n, s.split("\n").map((x) => p(x)), [p("☐ เห็นด้วย   ☐ ไม่เห็นด้วย"), p("หมายเหตุ: ....................................")]]);
children.push(table([700, 5738, 3200], prows, BLUE));

// ---------- Part 3
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(h1("ส่วนที่ 3  รายการประเด็นและองค์ประกอบ (28 ประเด็น)"));
children.push(p("แต่ละประเด็นแสดง: คำอธิบาย · มาตราหลักที่ระบบค้นก่อน · องค์ประกอบที่ระบบตรวจกับข้อเท็จจริงตามลำดับ · ข้อผิดพลาดที่พบบ่อย กรุณาติ๊กช่อง ✓/✗ และเขียนแก้ในช่องขวา"));
children.push(p("องค์ประกอบร่างจากตัวบทในฐานข้อมูลของระบบ (ไม่ได้ใช้ความรู้นอกตัวบท) จึงอาจตกหลักที่มาจากคำพิพากษาฎีกา หากองค์ประกอบใดควรเพิ่ม กรุณาเขียนเพิ่มท้ายตาราง", { spacing: { after: 160 } }));

tax.forEach((it, idx) => {
  children.push(h2(`${idx + 1}. ${it.name}`));
  children.push(p([t("คำอธิบาย: ", { bold: true }), t(it.description)]));
  children.push(p([t("มาตราหลัก: ", { bold: true }), t(it.primary.join(" · ") || "-")]));
  children.push(p([t("ใช้กับคำถามพัฒนา: ", { bold: true }), t(`${it.n} ข้อ`)]));
  const rows = [["#", "องค์ประกอบที่ระบบตรวจ", "✓ / ✗", "แก้ไข / ความเห็น"]];
  it.elements.forEach((e, i) => rows.push([String(i + 1), e, "☐ ✓  ☐ ✗", ""]));
  rows.push(["+", "องค์ประกอบที่ควรเพิ่ม", "", ""]);
  children.push(table([500, 5638, 1100, 2400], rows));
  if (it.pitfalls.length) {
    children.push(p([t("ข้อผิดพลาดที่พบบ่อย (ระบบใช้เตือนตัวเอง):", { bold: true })], { spacing: { before: 100, after: 40 } }));
    it.pitfalls.forEach((s) => children.push(bullet(s)));
  }
  children.push(p([t("ประเด็นนี้โดยรวม: ☐ ใช้ได้   ☐ ต้องแก้   ☐ ควรตัด/รวม", { bold: true })], { spacing: { before: 100, after: 200 } }));
});

children.push(h1("ความเห็นเพิ่มเติม"));
for (let i = 0; i < 6; i++) children.push(p("..................................................................................................................................................."));
children.push(p([t("ผู้ตรวจ: ...................................   วันที่: ...................", { bold: true })], { spacing: { before: 200 } }));

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
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
    alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: 16838 }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [t("LaborLex-TH · เอกสารตรวจสอบสำหรับอาจารย์ · หน้า ", { size: 24 }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 24 })] })] }) },
    children,
  }],
});
const out = process.argv[2];
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(out, b); console.log("wrote", out, b.length); });
