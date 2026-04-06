# Home Assistant Platform Integration Test Setup

These tests exercise the VOLTTRON `home_assistant` driver against a real Home Assistant instance:

- `test_home_assistant_input_boolean_platform_integration.py`
- `test_home_assistant_switch_platform_integration.py`

They are real integration tests, not mocked unit tests. A passing run verifies that:

- VOLTTRON starts a temporary platform instance
- `PlatformDriverAgent` is configured through the config store
- the Home Assistant driver authenticates with a real access token
- state changes are sent to Home Assistant and read back successfully

## Required Home Assistant setup

Before running these tests, your Home Assistant instance must provide:

- a valid long-lived access token
- an `input_boolean` entity for the input boolean test
- a `switch` entity for the switch test

Example entities used during development:

- `input_boolean.input_boolean_volttron_test_toggle`
- `switch.volttron_test_switch`

## Why `configuration.yaml` is not committed here

The switch test needs a real `switch.*` entity, but that entity belongs to each developer's local Home Assistant environment rather than this repository.

For local setup, a Home Assistant template switch can be added to the user's `configuration.yaml`:

```yaml
template:
  - switch:
      - name: "Volttron test switch"
        unique_id: volttron_test_switch
        state: "{{ is_state('input_boolean.input_boolean_volttron_test_toggle', 'on') }}"
        turn_on:
          action: input_boolean.turn_on
          target:
            entity_id: input_boolean.input_boolean_volttron_test_toggle
        turn_off:
          action: input_boolean.turn_off
          target:
            entity_id: input_boolean.input_boolean_volttron_test_toggle
```

This creates `switch.volttron_test_switch` backed by the input boolean. That Home Assistant configuration file is intentionally not committed to the VOLTTRON repo.

## Environment variables

Export these before running the tests:

```bash
export HOMEASSISTANT_TEST_IP=127.0.0.1
export HOMEASSISTANT_PORT=8123
export HOMEASSISTANT_ACCESS_TOKEN='<TOKEN>'
export HOMEASSISTANT_INPUT_BOOLEAN_ENTITY_ID='input_boolean.input_boolean_volttron_test_toggle'
export HOMEASSISTANT_SWITCH_ENTITY_ID='switch.volttron_test_switch'
```

## Running the tests

```bash
pytest services/core/PlatformDriverAgent/tests/test_home_assistant_input_boolean_platform_integration.py \
       services/core/PlatformDriverAgent/tests/test_home_assistant_switch_platform_integration.py -v
```

## Expected behavior

- the input boolean test drives the entity off -> on -> off
- the switch test drives the entity 0 -> 1 -> 0
- both tests should finish with the Home Assistant entities back in the off state

If the required environment variables are missing, the tests are skipped by design.
