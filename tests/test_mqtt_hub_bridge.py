"""Hub bridge: map a Hub event type to the entities it affects."""
from __future__ import annotations


def test_event_type_to_entities():
    from web.services.mqtt import entities_affected_by
    affected = entities_affected_by("sync_state")
    obj_ids = {e.object_id for e in affected}
    assert "sync_status" in obj_ids


def test_clip_indexed_affects_archive_entities():
    from web.services.mqtt import entities_affected_by
    obj_ids = {e.object_id for e in entities_affected_by("clip_indexed")}
    assert "last_downloaded_clip" in obj_ids
    assert "total_clips" in obj_ids


def test_unknown_event_yields_empty():
    from web.services.mqtt import entities_affected_by
    assert list(entities_affected_by("this_event_does_not_exist")) == []
