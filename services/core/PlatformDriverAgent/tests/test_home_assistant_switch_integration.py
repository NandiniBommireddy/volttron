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
def switch_interface(monkeypatch):
    state_by_entity = {"switch.test_switch": "off"}
    post_calls = []

    def fake_get(url, headers=None):
        entity_id = url.rsplit("/", 1)[-1]
        state = state_by_entity.get(entity_id, "off")
        return _FakeResponse(status_code=200, payload={"state": state, "attributes": {}})

    def fake_post(url, headers=None, json=None):
        entity_id = json["entity_id"]
        post_calls.append((url, entity_id))
        if url.endswith("/api/services/switch/turn_on"):
            state_by_entity[entity_id] = "on"
        elif url.endswith("/api/services/switch/turn_off"):
            state_by_entity[entity_id] = "off"
        return _FakeResponse(status_code=200, payload={})

    monkeypatch.setattr(ha_interface.requests, "get", fake_get)
    monkeypatch.setattr(ha_interface.requests, "post", fake_post)

    interface = ha_interface.Interface()
    interface.configure(
        {"ip_address": "127.0.0.1", "access_token": "fake", "port": "8123"},
        [
            {
                "Entity ID": "switch.test_switch",
                "Entity Point": "state",
                "Volttron Point Name": "switch_state",
                "Units": "On / Off",
                "Writable": True,
                "Starting Value": 0,
                "Type": "int",
            },
            {
                "Entity ID": "switch.read_only_switch",
                "Entity Point": "state",
                "Volttron Point Name": "switch_state_read_only",
                "Units": "On / Off",
                "Writable": False,
                "Starting Value": 0,
                "Type": "int",
            },
        ],
    )
    return interface, state_by_entity, post_calls


def test_switch_register_writable_configured_from_registry(switch_interface):
    interface, _, _ = switch_interface
    writable_register = interface.get_register_by_name("switch_state")
    readonly_register = interface.get_register_by_name("switch_state_read_only")

    assert writable_register.read_only is False
    assert readonly_register.read_only is True


def test_switch_set_point_controls_on_and_off_services(switch_interface):
    interface, state_by_entity, post_calls = switch_interface

    assert interface._set_point("switch_state", 1) == 1
    assert state_by_entity["switch.test_switch"] == "on"
    assert post_calls[-1][0].endswith("/api/services/switch/turn_on")

    assert interface._set_point("switch_state", 0) == 0
    assert state_by_entity["switch.test_switch"] == "off"
    assert post_calls[-1][0].endswith("/api/services/switch/turn_off")


def test_switch_state_value_mapping_is_consistent_for_get_and_scrape(switch_interface):
    interface, state_by_entity, _ = switch_interface

    state_by_entity["switch.test_switch"] = "off"
    assert interface.get_point("switch_state") == 0
    assert interface._scrape_all()["switch_state"] == 0

    state_by_entity["switch.test_switch"] = "on"
    assert interface.get_point("switch_state") == 1
    assert interface._scrape_all()["switch_state"] == 1


def test_switch_state_reflects_in_scrape_after_write(switch_interface):
    interface, _, _ = switch_interface

    assert interface._scrape_all()["switch_state"] == 0
    interface._set_point("switch_state", 1)
    assert interface._scrape_all()["switch_state"] == 1
    interface._set_point("switch_state", 0)
    assert interface._scrape_all()["switch_state"] == 0


def test_switch_rejects_invalid_state_values_and_read_only_writes(switch_interface):
    interface, _, _ = switch_interface

    with pytest.raises(ValueError):
        interface._set_point("switch_state", 2)

    with pytest.raises(IOError):
        interface._set_point("switch_state_read_only", 1)
