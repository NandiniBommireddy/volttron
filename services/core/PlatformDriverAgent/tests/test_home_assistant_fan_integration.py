import pytest
from unittest.mock import patch, MagicMock
from platform_driver.interfaces.home_assistant import Interface


@patch("platform_driver.interfaces.home_assistant.requests.get")
def test_get_point_fan(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "state": "off",
        "attributes": {}
    }
    mock_get.return_value = mock_response

    interface = Interface()
    registry = [
        {
            "Entity ID": "fan.test_fan",
            "Entity Point": "state",
            "Volttron Point Name": "fan_state",
            "Units": "On / Off",
            "Writable": True,
            "Starting Value": 0,
            "Type": "int",
        }
    ]
    interface.configure(
        {"ip_address": "127.0.0.1", "access_token": "fake", "port": "8123"},
        registry
    )

    assert interface.get_point("fan_state") == 0

    mock_response.json.return_value = {"state": "on", "attributes": {}}
    assert interface.get_point("fan_state") == 1


@patch("platform_driver.interfaces.home_assistant.requests.get")
def test_scrape_all_fan(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "state": "on",
        "attributes": {}
    }
    mock_get.return_value = mock_response

    interface = Interface()
    registry = [
        {
            "Entity ID": "fan.test_fan",
            "Entity Point": "state",
            "Volttron Point Name": "fan_state",
            "Units": "On / Off",
            "Writable": True,
            "Starting Value": 0,
            "Type": "int",
        }
    ]
    interface.configure(
        {"ip_address": "127.0.0.1", "access_token": "fake", "port": "8123"},
        registry
    )

    result = interface._scrape_all()
    assert result["fan_state"] == 1

    mock_response.json.return_value = {"state": "off", "attributes": {}}
    result = interface._scrape_all()
    assert result["fan_state"] == 0


@patch("platform_driver.interfaces.home_assistant.requests.post")
def test_set_point_fan_on(mock_post):
    mock_post.return_value.status_code = 200

    interface = Interface()
    registry = [
        {
            "Entity ID": "fan.test_fan",
            "Entity Point": "state",
            "Volttron Point Name": "fan_state",
            "Units": "On / Off",
            "Writable": True,
            "Starting Value": 0,
            "Type": "int",
        }
    ]
    interface.configure(
        {"ip_address": "127.0.0.1", "access_token": "fake", "port": "8123"},
        registry
    )

    value = interface._set_point("fan_state", 1)
    assert value == 1
    assert mock_post.called
    call_url = mock_post.call_args[0][0]
    assert call_url.endswith("/api/services/fan/turn_on")

@patch("platform_driver.interfaces.home_assistant.requests.post")
def test_set_point_fan_off(mock_post):
    mock_post.return_value.status_code = 200

    interface = Interface()
    registry = [
        {
            "Entity ID": "fan.test_fan",
            "Entity Point": "state",
            "Volttron Point Name": "fan_state",
            "Units": "On / Off",
            "Writable": True,
            "Starting Value": 0,
            "Type": "int",
        }
    ]
    interface.configure(
        {"ip_address": "127.0.0.1", "access_token": "fake", "port": "8123"},
        registry
    )

    value = interface._set_point("fan_state", 0)
    assert value == 0
    assert mock_post.called
    call_url = mock_post.call_args[0][0]
    assert call_url.endswith("/api/services/fan/turn_off")

def test_set_point_fan_invalid_value():
    interface = Interface()
    registry = [
        {
            "Entity ID": "fan.test_fan",
            "Entity Point": "state",
            "Volttron Point Name": "fan_state",
            "Units": "On / Off",
            "Writable": True,
            "Starting Value": 0,
            "Type": "int",
        }
    ]
    interface.configure(
        {"ip_address": "127.0.0.1", "access_token": "fake", "port": "8123"},
        registry
    )

    with pytest.raises(ValueError):
        interface._set_point("fan_state", 5)
