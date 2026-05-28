"""Topology integrity tests."""
from __future__ import annotations


def test_topology_has_expected_entities():
    from web.services.mqtt_topology import TOPOLOGY
    obj_ids = {e.object_id for e in TOPOLOGY}
    expected = {
        # binary_sensors / sensors (Task 5)
        "dashcam", "sync_status",
        "queue_pending", "queue_failed", "queue_downloading",
        "last_downloaded_clip", "total_clips", "current_filename",
        "current_progress", "disk_used",
    }
    assert expected.issubset(obj_ids), expected - obj_ids


def test_unique_ids_unique_per_node():
    from web.services.mqtt_topology import (
        TOPOLOGY, build_unique_id,
    )
    cfg = {"discovery_prefix": "homeassistant", "node_id": "viofosync",
           "version": "0.2.0"}
    uids = [build_unique_id(e.object_id, cfg) for e in TOPOLOGY]
    assert len(uids) == len(set(uids))


def test_sensors_have_state_fn():
    from web.services.mqtt_topology import TOPOLOGY
    for e in TOPOLOGY:
        if e.component in ("sensor", "binary_sensor"):
            assert e.state_fn is not None, e.object_id


def test_default_enabled_set():
    from web.services.mqtt_topology import TOPOLOGY
    enabled_by_default = {
        e.object_id for e in TOPOLOGY if e.enabled_by_default
    }
    assert {
        "dashcam", "sync_status",
        "queue_pending", "last_downloaded_clip", "disk_used",
    }.issubset(enabled_by_default)
    # The verbose ones are off by default
    disabled = {
        e.object_id for e in TOPOLOGY if not e.enabled_by_default
    }
    assert {
        "queue_failed", "queue_downloading", "current_filename",
        "current_progress", "total_clips",
    }.issubset(disabled)


def test_publish_intervals():
    """Coalescing intervals match the spec's table."""
    from web.services.mqtt_topology import TOPOLOGY
    by_id = {e.object_id: e for e in TOPOLOGY}
    assert by_id["current_filename"].min_publish_interval_s == 2.0
    assert by_id["current_progress"].min_publish_interval_s == 2.0
    assert by_id["queue_pending"].min_publish_interval_s == 1.0
    assert by_id["queue_failed"].min_publish_interval_s == 1.0
    assert by_id["queue_downloading"].min_publish_interval_s == 1.0
    assert by_id["last_downloaded_clip"].min_publish_interval_s == 5.0
    assert by_id["total_clips"].min_publish_interval_s == 5.0


def test_button_entries_present():
    from web.services.mqtt_topology import TOPOLOGY
    button_ids = {e.object_id for e in TOPOLOGY
                  if e.component == "button"}
    assert button_ids == {
        "start_sync", "pause_sync", "skip_current",
        "refresh_queue", "retry_failed", "rescan_archive",
    }


def test_buttons_have_no_state_fn():
    from web.services.mqtt_topology import TOPOLOGY
    for e in TOPOLOGY:
        if e.component == "button":
            assert e.state_fn is None, e.object_id


def test_button_default_enabled():
    from web.services.mqtt_topology import TOPOLOGY
    for e in TOPOLOGY:
        if e.component == "button":
            assert e.enabled_by_default is True, e.object_id


def test_command_handler_present_only_on_buttons():
    from web.services.mqtt_topology import TOPOLOGY
    for e in TOPOLOGY:
        if e.command_handler is not None:
            assert e.component == "button", e.object_id


def test_sync_status_entity_lists_new_affected_events():
    from web.services.mqtt_topology import TOPOLOGY
    entity = next(e for e in TOPOLOGY if e.object_id == "sync_status")
    events = set(entity.affected_by_hub_events)
    assert "dashcam_online" in events
    assert "dashcam_offline" in events
    assert "disk_pct" in events
    assert "sync_error" in events
    # Plus the original ones
    assert "sync_state" in events
    assert "item_started" in events
    assert "item_finished" in events


def test_sync_status_entity_has_attrs_fn():
    from web.services.mqtt_topology import TOPOLOGY
    from web.services.mqtt_state import attrs_sync_status
    entity = next(e for e in TOPOLOGY if e.object_id == "sync_status")
    assert entity.attrs_fn is attrs_sync_status
