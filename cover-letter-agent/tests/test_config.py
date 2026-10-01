import config

VALID_KEY = "sk-ant-test-0000000000000000"


def test_missing_env_file(app_paths):
    settings = config.load_settings()
    assert settings.key_status == "missing"
    assert settings.model == config.DEFAULT_MODEL


def test_empty_key_is_missing(app_paths):
    config.ENV_PATH.write_text("ANTHROPIC_API_KEY=\n")
    assert config.load_settings().key_status == "missing"


def test_wrong_format_is_invalid(app_paths):
    config.ENV_PATH.write_text("ANTHROPIC_API_KEY=paste-your-key-here\n")
    assert config.load_settings().key_status == "invalid"


def test_valid_key_and_model_override(app_paths):
    config.ENV_PATH.write_text(f"ANTHROPIC_API_KEY={VALID_KEY}\nANTHROPIC_MODEL=claude-opus-5-5\n")
    settings = config.load_settings()
    assert settings.key_status == "ok"
    assert settings.model == "claude-opus-5-5"


def test_key_never_in_repr(app_paths):
    config.ENV_PATH.write_text(f"ANTHROPIC_API_KEY={VALID_KEY}\n")
    settings = config.load_settings()
    assert VALID_KEY not in repr(settings)
    assert VALID_KEY not in str(settings)


def test_ensure_dirs(app_paths):
    config.ensure_dirs()
    assert config.DATA_DIR.is_dir() and config.OUTPUT_DIR.is_dir()
