from tests.integration.evaluator.rules import title_matches_scenario
from tests.integration.scenarios import LIVE_TICKET_SCENARIOS


def test_vpn_network_title_accepts_symptom_focused_llm_titles():
    scenario = next(s for s in LIVE_TICKET_SCENARIOS if s.id == "vpn_network")
    assert title_matches_scenario(
        "DPD Timeout Error Preventing Access to Internal Tools",
        scenario,
    )
    assert title_matches_scenario("Cisco AnyConnect VPN disconnects after 30 seconds", scenario)


def test_vpn_network_title_rejects_unrelated_topics():
    scenario = next(s for s in LIVE_TICKET_SCENARIOS if s.id == "vpn_network")
    assert not title_matches_scenario("Outlook inbox not syncing", scenario)
