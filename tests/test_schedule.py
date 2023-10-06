import copy

from webservice.schedule import Schedule


def is_sorted(l):
    all(l[i] <= l[i + 1] for i in range(len(l) - 1))


def check_order(sked:Schedule):
    skopy = copy.deepcopy(sked)
    skopy.start()
    pairlist = []
    while skopy:
        pairlist.append(skopy._next_delay())
    assert is_sorted([z[0] for z in pairlist])
    assert is_sorted([z[1] for z in pairlist])


def test_unget():
    pass


def test_status():
    pass


def test_creation():
    pass


class TestSchedule:
    def __init__(self):
        pass

    def test_status(self):
        pass


