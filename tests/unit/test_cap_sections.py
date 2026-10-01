from src.agent.nodes.decide import cap_sections


def test_cap_counts_sections_not_paragraphs():
    keys = ["L:1:1", "L:1:2", "L:2:1", "L:3:1", "L:2:2"]
    assert cap_sections(keys, 2) == ["L:1:1", "L:1:2", "L:2:1", "L:2:2"]
