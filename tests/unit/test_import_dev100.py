from src.eval.import_dev100 import resolve_citations


def test_resolve_citations():
    assert resolve_citations("ป.พ.พ. มาตรา 1448, 1458") == ["CCC:1448", "CCC:1458"]
    assert resolve_citations("พรบ.คุ้มครองแรงงาน มาตรา 123 และ 124\nป.พ.พ. มาตรา 193/34 (9)") == [
        "LPA2541:123", "LPA2541:124", "CCC:193/34"]
    assert resolve_citations("มาตรา 14/1 มาตรา 118 และประมวลกฎหมายแพ่งและพาณิชย์ มาตรา 150") == [
        "LPA2541:14/1", "LPA2541:118", "CCC:150"]
    assert resolve_citations("ไม่ถูกต้อง มาตรา 41/2 ที่อ้างถึง ไม่มีอยู่ในกฎหมาย") == []
    assert resolve_citations("มาตรา 118") == ["LPA2541:118"]
