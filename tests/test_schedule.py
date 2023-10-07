import copy
import math
import time

import pytest

from webservice.schedule import Schedule, SampleStatus


def is_sorted(l):
    return all(l[i - 1] <= l[i] for i in range(1, len(l)))


def assert_order(sked:Schedule):
    skopy = copy.deepcopy(sked)
    skopy.start(force=True)
    pairlist = []
    while skopy:
        pairlist.append(skopy._next_delay())
    assert is_sorted([z[0] for z in pairlist])
    assert is_sorted([z[1] for z in pairlist])


async def test_unget_happy():
    sked = Schedule(0.5, 10)
    sked.start()
    ungets = []
    for i in range(3):
        status, delay, arrival = await sked.pause_til_next()
        ungets.append(arrival)
    for a in reversed(ungets):
        if a is not None:
            sked.unget(a)
            assert_order(sked)
    assert_order(sked)


async def test_missed():
    sked = Schedule(100, 1)
    sked.start()
    assert len(sked) == 100
    time.sleep(0.1)
    status, delay, arrival = await sked.pause_til_next()
    assert status == SampleStatus.MISSED
    assert len(sked) == 99


async def test_basic_operation():
    sked = Schedule(1.5, 12.0)
    assert sked.status == 'ready'
    sked.start()
    assert sked.status == 'running'
    prev_arrival = None
    for i in range(18):
        assert sked.status == 'running'
        status, delay, arrival = await sked.pause_til_next()
        assert 0.0 <= delay and delay <= 12.0, f"Delay {delay} not within duration"
        assert status == SampleStatus.OK
        assert (prev_arrival is None) or (arrival >= prev_arrival)
        prev_arrival = arrival
    status, delay, arrival = await sked.pause_til_next()
    assert status == SampleStatus.DONE
    assert sked.status == 'done'
    # we can't actually assert that more time than duration has passed, as we may not have a sample at the end of the time span
    assert len(sked) == 0


@pytest.mark.parametrize("arrival_rate", [1.0, 0.05, 12, 14.3])
@pytest.mark.parametrize("duration", [0, 1.0, 30, 90])
def test_creation(arrival_rate, duration):
    sked = Schedule(arrival_rate, duration)
    assert len(sked) == int(math.ceil(arrival_rate * duration))
    assert len(sked) == sked.arrival_count
    assert_order(sked)

