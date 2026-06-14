from ng_drawing_qa.reference import normalize_value

def test_normalization_basic():
    assert normalize_value("BV 101") == "BV-101"
    assert normalize_value("BV_101") == "BV-101"

def test_normalization_fuzzy_remove():
    assert normalize_value("BV-101", remove_separators=True) == "BV101"
