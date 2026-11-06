import pytest
from app.collect import bridge, frequency
from test_collection_bridge import private_state, list_capture, detail_capture, _TEST_CLOCK


def session():
    return bridge.create_session({'keyword': 'Java', 'city_name': '北京', 'city_code': '101010100'})['run_id']


def test_direct_content_submission_cannot_bypass_permit(private_state):
    run = session()
    with pytest.raises(ValueError, match='capture_permit'):
        bridge.append_capture(run, list_capture())
    assert bridge.get_session(run)['listed'] == 0


def test_permission_consumption_replay_and_shared_rate_limit(private_state):
    run = session()
    permit = bridge.authorize_capture(run, 'list')['permit']
    with pytest.raises(frequency.FrequencyLimitError):
        bridge.authorize_capture(run, 'list')
    with pytest.raises(frequency.FrequencyLimitError):
        frequency.reserve_action('boss', 'Java', '101010100')
    result = bridge.append_capture(run, list_capture(), permit=permit)
    assert result['result']['listed'] == 1
    assert bridge.append_capture(run, list_capture(), permit=permit)['duplicate'] is True
    with pytest.raises(ValueError, match='capture_permit'):
        bridge.append_capture(run, list_capture(count=2), permit=permit)


def test_expired_or_wrong_kind_permission_cannot_write(private_state):
    run = session()
    permit = bridge.authorize_capture(run, 'list')['permit']
    with pytest.raises(ValueError, match='capture_permit'):
        bridge.append_capture(run, detail_capture(), permit=permit)
    _TEST_CLOCK[0] += 15
    with pytest.raises(ValueError, match='capture_permit'):
        bridge.append_capture(run, list_capture(), permit=permit)


def test_new_session_does_not_reset_platform_frequency(private_state):
    run = session()
    bridge.authorize_capture(run, 'list')
    bridge.finish_session(run)
    another = session()
    with pytest.raises(frequency.FrequencyLimitError):
        bridge.authorize_capture(another, 'list')


def test_blocked_notice_can_stop_immediately_without_content_permit(private_state):
    run = session()
    bridge.authorize_capture(run, 'list')
    result = bridge.append_capture(run, {
        'schema_version': 'm1-browser-bridge-v1', 'kind': 'blocked',
        'page_url': 'https://www.zhipin.com/security/',
        'blocked_reason': 'security_verification',
    })
    assert result['session']['status'] == 'stopped'


def test_real_bridge_routes_require_permit_and_enforce_cooldown(private_state, monkeypatch):
    import asyncio
    import httpx
    from fastapi import FastAPI
    from app.collect import bridge_access
    from app.routers.collection_bridge import router
    from app.response import BizError
    from fastapi.responses import JSONResponse
    app = FastAPI()
    app.include_router(router, prefix='/api')
    @app.exception_handler(BizError)
    async def error_handler(_request, exc):
        return JSONResponse({'code': 4001, 'message': str(exc)}, status_code=400)
    monkeypatch.setattr(bridge_access, '_TOKEN_PATH', private_state / 'token')
    token = bridge_access.get_bridge_token()
    run = session()
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=('127.0.0.1', 1234)), base_url='http://127.0.0.1:18000') as client:
            headers = {'Origin': bridge_access.EXTENSION_ORIGIN, bridge_access.TOKEN_HEADER: token}
            base = '/api/collection/bridge/sessions/' + run
            assert (await client.post(base + '/captures', headers=headers, json=list_capture())).status_code == 400
            authorized = await client.post(base + '/permit', headers=headers, json={'kind': 'list'})
            assert authorized.status_code == 200
            permit = authorized.json()['data']['permit']
            assert (await client.post(base + '/permit', headers=headers, json={'kind': 'list'})).status_code == 400
            headers['X-TalentMind-Capture-Permit'] = permit
            captured = await client.post(base + '/captures', headers=headers, json=list_capture())
            assert captured.json()['data']['result']['listed'] == 1
    asyncio.run(exercise())
