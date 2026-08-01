import pytest

from app.models import Engagement
from app.services.engagements import get_active_engagement, resolve_engagement_id, set_active_engagement


def test_auto_creates_default_engagement_when_none_exist(db_session):
    assert db_session.query(Engagement).count() == 0
    active = get_active_engagement(db_session)
    assert active.name == "Default Engagement"
    assert active.is_active is True
    assert db_session.query(Engagement).count() == 1


def test_returns_existing_active_engagement(db_session):
    first = get_active_engagement(db_session)
    second = get_active_engagement(db_session)
    assert first.id == second.id
    assert db_session.query(Engagement).count() == 1


def test_set_active_engagement_switches_and_deactivates_others(db_session):
    default = get_active_engagement(db_session)
    other = Engagement(name="Client B", is_active=False)
    db_session.add(other)
    db_session.commit()

    result = set_active_engagement(db_session, other.id)
    assert result.id == other.id
    assert result.is_active is True

    db_session.refresh(default)
    assert default.is_active is False


def test_set_active_engagement_rejects_unknown_id(db_session):
    import uuid

    with pytest.raises(ValueError, match="does not exist"):
        set_active_engagement(db_session, uuid.uuid4())


def test_resolve_engagement_id_prefers_explicit_over_active(db_session):
    active = get_active_engagement(db_session)
    other = Engagement(name="Client B")
    db_session.add(other)
    db_session.commit()

    assert resolve_engagement_id(db_session, other.id) == other.id
    assert resolve_engagement_id(db_session, None) == active.id


def test_get_active_reuses_existing_engagement_if_none_marked_active(db_session):
    """Edge case: an engagement exists but somehow nothing is is_active
    (e.g. manual DB edit) — should adopt the oldest one rather than create
    a second 'Default Engagement'."""
    orphan = Engagement(name="Orphaned", is_active=False)
    db_session.add(orphan)
    db_session.commit()

    active = get_active_engagement(db_session)
    assert active.id == orphan.id
    assert active.is_active is True
    assert db_session.query(Engagement).count() == 1
