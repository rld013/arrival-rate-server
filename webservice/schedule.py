import asyncio
import math
import random
import time
import logging
from collections import deque
from datetime import datetime, timezone
from enum import Enum
from typing import TypeVar

_logger = logging.getLogger(__name__)

T = TypeVar("T")


def deque_insert_ordered(dq: deque[T], iv: T):
    """ Assuming that dq is ordered, insert iv in the correct place to preserve ordering.
    >>> deck = deque([1,2,4])
    >>> deque_insert_ordered(deck, 3)
    >>> deck
    deque([1, 2, 3, 4])
    >>> deque_insert_ordered(deck,0)
    >>> deck
    deque([0, 1, 2, 3, 4])
    >>> deque_insert_ordered(deck, 10)
    >>> deck
    deque([0, 1, 2, 3, 4, 10])
    >>> deck2 = deque()
    >>> deque_insert_ordered(deck2,10.1)
    >>> deck2
    deque([10.1])
    >>> deque_insert_ordered(deck2, -3.2)
    >>> deck2
    deque([-3.2, 10.1])
    >>> deque_insert_ordered(deck2, -3.2)
    >>> deck2
    deque([-3.2, -3.2, 10.1])
    """
    ix = 0
    for ix, v in enumerate(dq):
        if v >= iv:
            break
    else:
        ix = ix + 1
    dq.insert(ix, iv)


class SampleStatus(Enum):
    """Value is HTTP status code"""
    OK = 200
    MISSED = 418
    DONE = 410


class Schedule:
    def __init__(self, rate, duration):
        self.rate = rate
        self.duration = duration
        self.underrun_count = 0
        self.arrival_count = int(math.ceil(duration * rate))
        arrivals = [
            duration * random.random()
            for _ in range(self.arrival_count)
        ]
        # Use a deque because popleft, the critical operation, is O(1)
        # A PriorityQueue get is O(log n)
        self.arrivals = deque(sorted(arrivals))
        _logger.info("Schedule(%s,%s) len %d", rate, duration, self.arrival_count)

        self.running = False
        self.start_time = None

    @property
    def status(self):
        if self.running:
            return 'running'
        elif self.start_time is None:
            return 'ready'
        else:
            return 'done'

    def unget(self, arrival):
        deque_insert_ordered(self.arrivals, arrival)
        _logger.warning("unget of delay %f len(arrivals) now %d", arrival, len(self.arrivals))
        self.running = True

    def __len__(self):
        # Note that this gives, by built-in conversion rules, that (len(self) == 0) ==> not bool(self)
        return len(self.arrivals)

    def info(self):
        if self.start_time:
            start_time = datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat()
        else:
            start_time = None
        return dict(
            arrival_count=self.arrival_count,
            arrival_remain_count=len(self.arrivals),
            start_time=start_time,
            running=self.running,
            underrun_count=self.underrun_count,
            status=self.status
        )

    def start(self, force=False):
        if force or (self.start_time is None):
            self.start_time = time.time()
            self.running = True
            _logger.info("Schedule started")
        else:
            pass

    def stop(self):
        self.running = False
        _logger.info("Schedule stopped")

    async def pause_til_next(self) -> (SampleStatus, float, float):
        delay, arrival = self._next_delay()
        match delay:
            case None:
                status = SampleStatus.DONE
            case _ if delay < 0:
                self.underrun_count += 1
                status = SampleStatus.MISSED
            case _:
                await asyncio.sleep(delay)
                status = SampleStatus.OK
        return status, delay, arrival

    def _next_delay(self) -> (float, float):
        if not self.running:
            return None, None
        try:
            next_arrival = self.arrivals.popleft()
        except IndexError:
            self.running = False
            return None, None
        next_time = self.start_time + next_arrival
        delay = next_time - time.time()
        return delay, next_arrival

    def started(self):
        return self.start_time is not None
