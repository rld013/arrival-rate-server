import math
import time

from aiohttp import web

from aiohttp.test_utils import TestClient, TestServer
import pytest

from webservice.arrival_rate_service import init_app


@pytest.mark.parametrize("arrival_rate", [1.0, 0.05, 12, 98.3])
@pytest.mark.parametrize("duration", [0, 1.0, 30, 90])
async def test_create(aiohttp_client:TestClient, loop, arrival_rate, duration):
    app = init_app(web.Application(loop=loop))

    client = await aiohttp_client(app)

    resp = await client.put('/foobar', data=dict(arrival_rate=arrival_rate, duration=duration))
    assert resp.status == 200

    resp = await client.get('/')
    info_list = await resp.json()
    assert isinstance(info_list, list)
    foobar_ct = 0
    for info in filter(lambda i:i.get('name') == 'foobar', info_list):
        foobar_ct += 1
        assert info['arrival_count'] == int(math.ceil(arrival_rate * duration)), f"Bad arrival count, got {info['arrival_count']}"
        assert info['running'] is False
        assert info['status'] == 'ready'
    assert foobar_ct == 1, f"Bad count {foobar_ct}"


async def test_wait_positive(aiohttp_client:TestClient):
    app = init_app()
    arrival_rate = 1.5
    duration = 12
    count = 18

    client = await aiohttp_client(app)

    # can't, sadly, use freezegun to adjust time, as it carefully avoids messing with asyncio.sleep
    # but await asyncio.sleep is at the core of the web service wait function
    # so have either to use a real schedule,
    # or monkeypatch asyncio.sleep, perhaps using freezetime.tick() to advance the clock

    resp = await client.put('/foobar', data=dict(arrival_rate=arrival_rate, duration=duration))
    assert resp.status == 200

    # let the schedule autostart
    start_time = time.time()
    for _ in range(count):
        resp = await client.get('/foobar/wait')
        assert resp.status == 200
        payload = await resp.json()
        arrival = payload.get('arrival')
        assert 0 <= (arrival - start_time) <= duration

    resp = await client.get('/foobar/wait')
    assert resp.status == 410



