"""OpenAI strict JSON schema compatibility for ConversationAnalysis."""

import json

from tech_support_agents.openai_llm import ConversationAnalysis


def test_conversation_analysis_schema_has_no_open_dict_fields():
    schema = ConversationAnalysis.model_json_schema()
    encoded = json.dumps(schema)
    assert "additionalProperties" not in encoded or "true" not in encoded.replace(
        '"additionalProperties":false', ""
    )

    props = schema.get("properties", {})
    assert "payload" not in props
