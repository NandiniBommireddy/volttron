import pytest

from platform_driver.interfaces import home_assistant as ha_interface


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


@pytest.fixture
def lock_interface(monkeypatch):
    state_by_entity = {"lock.test_lock": "unlocked"}
    post_calls = []

    def fake_get(url, headers=None):
        entity_id = url.rsplit("/", 1)[-1]
        state = state_by_entity.get(entity_id, "unlocked")
        return _FakeResponse(status_code=200, payload={"state": state, "attributes": {}})

    def fake_post(url, headers=None, json=None):
        entity_id = json["entity_id"]
        post_calls.append((url, entity_id))
        if url.endswith("/api/services/lock/lock"):
            state_by_entity[entity_id] = "locked"
        elif url.endswith("/api/services/lock/unlock"):
            state_by_entity[entity_id] = "unlocked"
        return _FakeResponse(status_code=200, payload={})

    monkeypatch.setattr(ha_interface.requests, "get", fake_get)
    monkeypatch.setattr(ha_interface.requests, "post", fake_post)

    interface = ha_interface.Interface()
    interface.configure(
        {"ip_address": "127.0.0.1", "access_token": "fake", "port": "8123"},
        [
            {
                "Entity ID": "lock.test_lock",
                "Entity Point": "state",
                "Volttron Point Name": "lock_state",
                "Units": "Locked / Unlocked",
                "Writable": True,
                "Starting Value": 0,
                "Type": "int",
            },
            {
                "Entity ID": "lock.read_only_lock",
                "Entity Point": "state",
                "Volttron Point Name": "lock_state_read_only",
                "Units": "Locked / Unlocked",
                "Writable": False,
                "Starting Value": 0,
                "Type": "int",
            },
        ],
    )
    return interface, state_by_entity, post_calls


def test_lock_register_writable_configured_from_registry(lock_interface):
    interface, _, _ = lock_interface
    writable_register = interface.get_register_by_name("lock_state")
    readonly_register = interface.get_register_by_name("lock_state_read_only")

    assert writable_register.read_only is False
    assert readonly_register.read_only is True


def test_lock_set_point_controls_lock_and_unlock_services(lock_interface):
    interface, state_by_entity, post_calls = lock_interface

    assert interface._set_point("lock_state", 1) == 1
    assert state_by_entity["lock.test_lock"] == "locked"
    assert post_calls[-1][0].endswith("/api/services/lock/lock")

    assert interface._set_point("lock_state", 0) == 0
    assert state_by_entity["lock.test_lock"] == "unlocked"
    assert post_calls[-1][0].endswith("/api/services/lock/unlock")


def test_lock_state_value_mapping_is_consistent_for_get_and_scrape(lock_interface):
    interface, state_by_entity, _ = lock_interface

    state_by_entity["lock.test_lock"] = "unlocked"
    assert interface.get_point("lock_state") == 0
    assert interface._scrape_all()["lock_state"] == 0

    state_by_entity["lock.test_lock"] = "locked"
    assert interface.get_point("lock_state") == 1
    assert interface._scrape_all()["lock_state"] == 1


def test_lock_state_reflects_in_scrape_after_write(lock_interface):
    interface, _, _ = lock_interface

    assert interface._scrape_all()["lock_state"] == 0
    interface._set_point("lock_state", 1)
    assert interface._scrape_all()["lock_state"] == 1
    interface._set_point("lock_state", 0)
    assert interface._scrape_all()["lock_state"] == 0


def test_lock_rejects_invalid_state_values_and_read_only_writes(lock_interface):
    interface, _, _ = lock_interface

    with pytest.raises(ValueError):
        interface._set_point("lock_state", 2)

    with pytest.raises(IOError):
        interface._set_point("lock_state_read_only", 1)
