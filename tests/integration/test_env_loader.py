from tests.integration.env_loader import integration_env_bool, parse_env_value


def test_parse_env_value_strips_inline_comment():
    assert parse_env_value('false          # browser mode') == "false"
    assert parse_env_value('"true" # yes') == "true"


def test_integration_env_bool():
    import os

    os.environ["INTEGRATION_HEADLESS"] = "false          # show browser"
    assert integration_env_bool("INTEGRATION_HEADLESS", default=True) is False

    os.environ["INTEGRATION_HEADLESS"] = "true"
    assert integration_env_bool("INTEGRATION_HEADLESS", default=False) is True

    del os.environ["INTEGRATION_HEADLESS"]
    assert integration_env_bool("INTEGRATION_HEADLESS", default=False) is False
