from ng_drawing_qa.config import is_rule_enabled, load_config
from ng_drawing_qa.rules.registry import RULE_METADATA_BY_ID, get_rule_metadata


def test_rule_metadata_covers_default_config_rules():
    metadata_ids = {rule.rule_id for rule in get_rule_metadata()}
    config_ids = set(load_config().get("rules", {}))
    assert config_ids <= metadata_ids


def test_ai_and_symbol_hooks_are_disabled_by_default():
    cfg = load_config()
    assert not is_rule_enabled(cfg, "AI_COMMENT_DRAFTS")
    assert not is_rule_enabled(cfg, "SYMBOL_RECOGNITION_STUB")
    assert not RULE_METADATA_BY_ID["AI_COMMENT_DRAFTS"].enabled_by_default
    assert not RULE_METADATA_BY_ID["SYMBOL_RECOGNITION_STUB"].enabled_by_default
