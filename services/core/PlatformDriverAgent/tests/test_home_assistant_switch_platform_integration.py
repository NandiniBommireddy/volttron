import json
import os
import tempfile
from unittest.mock import patch

import gevent
import pytest

from volttron.platform import get_services_core
from volttron.platform.agent.known_identities import CONFIGURATION_STORE, PLATFORM_DRIVER
from volttrontesting.utils import platformwrapper as platformwrapper_module
from volttrontesting.fixtures.volttron_platform_fixtures import build_wrapper, cleanup_wrapper
from volttrontesting.utils.utils import get_rand_port


HOMEASSISTANT_TEST_IP = os.environ.get("HOMEASSISTANT_TEST_IP", "127.0.0.1")
HOMEASSISTANT_ACCESS_TOKEN = os.environ.get("HOMEASSISTANT_ACCESS_TOKEN", "")
HOMEASSISTANT_PORT = os.environ.get("HOMEASSISTANT_PORT", "8123")
HOMEASSISTANT_SWITCH_ENTITY_ID = os.environ.get("HOMEASSISTANT_SWITCH_ENTITY_ID", "")

skip_msg = (
    "Set HOMEASSISTANT_ACCESS_TOKEN and HOMEASSISTANT_SWITCH_ENTITY_ID to run "
    "the real Home Assistant switch integration test."
)

pytestmark = pytest.mark.skipif(
    not (HOMEASSISTANT_TEST_IP and HOMEASSISTANT_ACCESS_TOKEN and HOMEASSISTANT_PORT and HOMEASSISTANT_SWITCH_ENTITY_ID),
    reason=skip_msg,
)

HOMEASSISTANT_DEVICE_TOPIC = "devices/home_assistant_switch"


def _local_vip_address():
    return f"tcp://127.0.0.1:{get_rand_port('127.0.0.1')}"


def _wait_for_peer(agent, peer, timeout=30):
    deadline = gevent.get_hub().loop.now() + timeout
    while gevent.get_hub().loop.now() < deadline:
        peers = agent.vip.peerlist().get(timeout=10)
        if peer in peers:
            return True
        gevent.sleep(1)
    return False


@pytest.fixture(scope="module")
def volttron_instance():
    def _short_volttron_home():
        root = tempfile.mkdtemp(prefix="vt-", dir="/tmp")
        volttron_home = os.path.join(root, "volttron_home")
        os.makedirs(volttron_home)
        os.chmod(root, 0o755)
        os.chmod(volttron_home, 0o755)
        return volttron_home

    with patch.object(platformwrapper_module, "create_volttron_home", _short_volttron_home):
        wrapper = build_wrapper(
            _local_vip_address(),
            messagebus="zmq",
            ssl_auth=False,
            auth_enabled=False,
            instance_name="ha_switch_test",
        )
        try:
            yield wrapper
        finally:
            cleanup_wrapper(wrapper)


@pytest.fixture(scope="module")
def platform_driver(volttron_instance):
    platform_uuid = volttron_instance.install_agent(
        agent_dir=get_services_core("PlatformDriverAgent"),
        config_file={
            "publish_breadth_first_all": False,
            "publish_depth_first": False,
            "publish_breadth_first": False,
        },
        start=False,
    )
    gevent.sleep(5)
    volttron_instance.start_agent(platform_uuid)
    if not _wait_for_peer(volttron_instance.dynamic_agent, PLATFORM_DRIVER):
        volttron_instance.stop_agent(platform_uuid)
        gevent.sleep(2)
        volttron_instance.start_agent(platform_uuid)
        assert _wait_for_peer(volttron_instance.dynamic_agent, PLATFORM_DRIVER)

    assert volttron_instance.is_agent_running(platform_uuid)

    yield platform_uuid

    volttron_instance.stop_agent(platform_uuid)
    if not volttron_instance.debug_mode:
        volttron_instance.remove_agent(platform_uuid)


@pytest.fixture(scope="module")
def switch_configured_platform(volttron_instance, platform_driver):
    capabilities = [{"edit_config_store": {"identity": PLATFORM_DRIVER}}]
    volttron_instance.add_capabilities(volttron_instance.dynamic_agent.core.publickey, capabilities)

    registry_config = "homeassistant_switch_test.json"
    registry_obj = [
        {
            "Entity ID": HOMEASSISTANT_SWITCH_ENTITY_ID,
            "Entity Point": "state",
            "Volttron Point Name": "switch_state",
            "Units": "On / Off",
            "Units Details": "0: off, 1: on",
            "Writable": True,
            "Starting Value": 0,
            "Type": "int",
            "Notes": "Home Assistant switch integration test",
        }
    ]

    agent = volttron_instance.dynamic_agent
    agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_store",
        PLATFORM_DRIVER,
        registry_config,
        json.dumps(registry_obj),
        config_type="json",
    ).get(timeout=20)
    gevent.sleep(2)

    driver_config = {
        "driver_config": {
            "ip_address": HOMEASSISTANT_TEST_IP,
            "access_token": HOMEASSISTANT_ACCESS_TOKEN,
            "port": HOMEASSISTANT_PORT,
        },
        "driver_type": "home_assistant",
        "registry_config": f"config://{registry_config}",
        "timezone": "US/Pacific",
        "interval": 15,
    }

    agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "manage_store",
        PLATFORM_DRIVER,
        HOMEASSISTANT_DEVICE_TOPIC,
        json.dumps(driver_config),
        config_type="json",
    ).get(timeout=20)
    gevent.sleep(5)

    # Put the switch in a known state for a deterministic test start.
    agent.vip.rpc.call(PLATFORM_DRIVER, "set_point", "home_assistant_switch", "switch_state", 0).get(timeout=20)
    gevent.sleep(5)

    yield agent

    agent.vip.rpc.call(CONFIGURATION_STORE, "manage_delete_store", PLATFORM_DRIVER).get(timeout=20)
    gevent.sleep(1)


def test_switch_platform_round_trip(switch_configured_platform):
    agent = switch_configured_platform

    off_value = agent.vip.rpc.call(
        PLATFORM_DRIVER, "get_point", "home_assistant_switch", "switch_state"
    ).get(timeout=20)
    assert off_value == 0

    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point", "home_assistant_switch", "switch_state", 1
    ).get(timeout=20)
    gevent.sleep(5)

    on_value = agent.vip.rpc.call(
        PLATFORM_DRIVER, "get_point", "home_assistant_switch", "switch_state"
    ).get(timeout=20)
    assert on_value == 1

    scraped_on = agent.vip.rpc.call(
        PLATFORM_DRIVER, "scrape_all", "home_assistant_switch"
    ).get(timeout=20)
    assert scraped_on == {"switch_state": 1}

    agent.vip.rpc.call(
        PLATFORM_DRIVER, "set_point", "home_assistant_switch", "switch_state", 0
    ).get(timeout=20)
    gevent.sleep(5)

    scraped_off = agent.vip.rpc.call(
        PLATFORM_DRIVER, "scrape_all", "home_assistant_switch"
    ).get(timeout=20)
    assert scraped_off == {"switch_state": 0}
