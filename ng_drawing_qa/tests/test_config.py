from ng_drawing_qa.config import load_config, is_rule_enabled

def test_default_config_loads():
    cfg = load_config()
    assert is_rule_enabled(cfg, "VALVE_TAG_RECONCILIATION")
