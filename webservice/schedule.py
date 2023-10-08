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
    """
    A schedule, which is a sequence of arrivals within a duration. An arrival is an offset in [0..duration].
    Once a schedule is started, it will deliver arrivals in order, along with the delay from the calling instant
    (but see Lamport ) until the arrival instant.
    If the arrival instant has passed before you ask for it, you'll get status MISSED.
    If all the arrivals are gone, you'll get status DONE.
    """

    def __init__(self, rate, duration):
        self.rate = rate
        self.duration = duration
        self.underrun_count = 0
        self.arrival_count = math.ceil(rate * duration)
        arrivals = [
            random.uniform(0, duration)
            for _ in range(self.arrival_count)
        ]
        # Use a deque because popleft, the critical operation, is O(1)
        # PriorityQueue get is O(log n)
        self.arrivals = deque(sorted(arrivals))
        _logger.info("Schedule(%s,%s) len %d", rate, duration, self.arrival_count)

        self.running = False
        self.start_time = None
        """`start_time` is wallclock, for sharing"""
        self.start_clock = None
        """`start_clock` is from self.clock, for waiting"""
        self.clock = time.monotonic

    @property
    def status(self):
        if self.running:
            return 'running'
        elif self.start_clock is None:
            return 'ready'
        else:
            return 'done'

    def unget(self, arrival):
        if arrival < 0 or arrival > self.duration:
            raise ValueError(f"Arrival not in 0..{self.duration}")
        deque_insert_ordered(self.arrivals, arrival)
        _logger.warning("unget of delay %f len(arrivals) now %d", arrival, len(self.arrivals))
        self.running = True

    def __len__(self):
        # Note that this gives, by built-in conversion rules, that (len(self) == 0) ==> not bool(self)
        return len(self.arrivals)

    def info(self):
        if self.start_time:
            start_time = datetime.utcfromtimestamp(self.start_time).isoformat()
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

    def start(self, force=False, delay=0.0):
        if force or (self.start_clock is None):
            self.start_clock = self.clock() + delay
            self.start_time = time.time() + delay
            self.running = True
            _logger.info("Schedule started")
        else:
            pass

    def stop(self):
        self.running = False
        _logger.info("Schedule stopped")

    def arrival_time(self, arrival):
        """Translate an arrival to a wallclock time"""
        if arrival is None:
            return None
        return arrival + self.start_time

    def delay_til_next(self) -> (SampleStatus, float, float):
        delay, arrival = self._next_delay()
        match delay:
            case None:
                status = SampleStatus.DONE
            case _ if delay < 0:
                self.underrun_count += 1
                status = SampleStatus.MISSED
            case _:
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
        next_clock = self.start_clock + next_arrival
        delay = next_clock - self.clock()
        return delay, next_arrival

    def started(self):
        return self.start_clock is not None
