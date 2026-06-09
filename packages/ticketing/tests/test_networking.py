from tech_support_ticketing.networking import resolve_zammad_base_url


def test_resolve_zammad_base_url_unchanged_outside_docker(monkeypatch):
    monkeypatch.setattr("tech_support_ticketing.networking.is_running_in_docker", lambda: False)
    assert resolve_zammad_base_url("http://localhost:8080") == "http://localhost:8080"
    assert resolve_zammad_base_url("https://zammad.example.com") == "https://zammad.example.com"


def test_resolve_zammad_base_url_rewrites_localhost_in_docker(monkeypatch):
    monkeypatch.setattr("tech_support_ticketing.networking.is_running_in_docker", lambda: True)
    assert resolve_zammad_base_url("http://localhost:8080") == "http://host.docker.internal:8080"
    assert resolve_zammad_base_url("http://127.0.0.1:8080") == "http://host.docker.internal:8080"


def test_resolve_zammad_base_url_remote_unchanged_in_docker(monkeypatch):
    monkeypatch.setattr("tech_support_ticketing.networking.is_running_in_docker", lambda: True)
    assert (
        resolve_zammad_base_url("https://sandbox.zammad.example.com")
        == "https://sandbox.zammad.example.com"
    )
