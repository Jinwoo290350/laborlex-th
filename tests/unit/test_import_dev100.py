from src.eval.import_dev100 import resolve_citations, split_verdict


def test_resolve_citations():
    assert resolve_citations("ป.พ.พ. มาตรา 1448, 1458") == ["CCC:1448", "CCC:1458"]
    assert resolve_citations("พรบ.คุ้มครองแรงงาน มาตรา 123 และ 124\nป.พ.พ. มาตรา 193/34 (9)") == [
        "LPA2541:123", "LPA2541:124", "CCC:193/34"]
    assert resolve_citations("มาตรา 14/1 มาตรา 118 และประมวลกฎหมายแพ่งและพาณิชย์ มาตรา 150") == [
        "LPA2541:14/1", "LPA2541:118", "CCC:150"]
    assert resolve_citations("ไม่ถูกต้อง มาตรา 41/2 ที่อ้างถึง ไม่มีอยู่ในกฎหมาย") == []
    assert resolve_citations("มาตรา 118") == ["LPA2541:118"]
    assert resolve_citations("มาตรา 123 (ไม่มีอำนาจรับคำร้อง)") == ["LPA2541:123"]


def test_split_verdict():
    assert split_verdict("ไม่ถูกต้อง มาตรา 23/12 ไม่มีอยู่ในกฎหมาย") == ("incorrect", "มาตรา 23/12 ไม่มีอยู่ในกฎหมาย")
    assert split_verdict("ถูกบางส่วน มาตรา 4/1 ถูกต้อง")[0] == "partial"
    assert split_verdict("ถูกต้อง") == ("correct", "")
    assert split_verdict("ถูกต้อง แต่ขาดมาตรา 122")[0] == "partial"
    assert split_verdict("(1) ถูกต้อง อ้างมาตราถูกต้อง อายุงาน 8 ปี")[0] == "correct"
    assert split_verdict("พรบ.คุ้มครองแรงงาน มาตรา 118") == ("", "พรบ.คุ้มครองแรงงาน มาตรา 118")
    assert split_verdict("มาตรา 5, 61 ถูกต้องทั้งหมด แต่ขาดมาตรา 27")[0] == "partial"
