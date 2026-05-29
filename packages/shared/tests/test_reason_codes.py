from tech_support_shared.reason_codes import DEFAULT_USER_MESSAGES, ReasonCode


def test_all_reason_codes_have_default_messages():
    for code in ReasonCode:
        assert code in DEFAULT_USER_MESSAGES
        assert DEFAULT_USER_MESSAGES[code]
