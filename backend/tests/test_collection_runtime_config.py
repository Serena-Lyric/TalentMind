"""Runtime config defaults and partial overrides; no browser or database."""
import pytest

from app.collect.runtime.platforms import PLATFORMS, config_from_payload


def test_empty_payload_uses_default_keywords_and_all_platform_cities():
    config = config_from_payload({})
    assert config.keywords == ('Python',)
    assert config.cities == {platform: definition.cities for platform, definition in PLATFORMS.items()}
    config.validate()


def test_partial_override_keeps_unspecified_platform_defaults():
    config = config_from_payload({
        'keywords': ['Java'],
        'cities': {'boss': [['上海', '102']]},
    })
    assert config.keywords == ('Java',)
    assert config.cities['boss'] == (('上海', '102'),)
    assert config.cities['zhaopin'] == PLATFORMS['zhaopin'].cities
    assert config.cities['liepin'] == PLATFORMS['liepin'].cities
    config.validate()


@pytest.mark.parametrize('payload', [
    {'keywords': []},
    {'cities': {'boss': []}},
    {'cities': {'boss': [['北京']]}},
])
def test_explicit_empty_or_malformed_values_remain_rejected(payload):
    with pytest.raises(ValueError):
        config_from_payload(payload).validate()


def test_slower_delays_are_accepted():
    config = config_from_payload({
        'page_delay_min': 45,
        'page_delay_max': 60,
        'switch_interval_min': 900,
        'switch_interval_max': 1200,
        'settle': 8,
    })
    config.validate()
