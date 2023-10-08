# measure time to get and unget
# with priority queue and with deque
# over a range of sizes and unget ratios
import heapq
import math
import random
import timeit
from collections import deque
from typing import TypeVar


class BaseSchedule():
    def __init__(self, rate, duration):
        self.rate = rate
        self.duration = duration
        self.arrival_count = int(math.ceil(duration * rate))
        arrivals = [
            duration * random.random()
            for _ in range(self.arrival_count)
        ]
        # Use a deque because popleft, the critical operation, is O(1)
        # A PriorityQueue get is O(log n)
        self.set_arrivals(arrivals)

        self.running = False
        self.start_time = None

    def set_arrivals(self, arrivals):
        pass

    def get(self):
        pass

    def unget(self, arrival):
        pass

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


class DequeSchedule(BaseSchedule):
    def __init__(self, rate, duration):
        super().__init__(rate, duration)
        # Use a deque because popleft, the critical operation, is O(1)
        # A PriorityQueue get is O(log n)

    def set_arrivals(self, arrivals):
        self.arrivals = deque(sorted(arrivals))

    def get(self):
        next_arrival = self.arrivals.popleft()
        return next_arrival

    def unget(self, arrival):
        deque_insert_ordered(self.arrivals, arrival)

    def __len__(self):
        # Note that this gives, by built-in conversion rules, that (len(self) == 0) ==> not bool(self)
        return len(self.arrivals)


class PQSchedule(BaseSchedule):
    def __init__(self, rate, duration):
        super().__init__(rate, duration)

    def set_arrivals(self, arrivals):
        self.arrivals = arrivals[:]
        heapq.heapify(self.arrivals)

    def get(self):
        next_arrival = heapq.heappop(self.arrivals)
        return next_arrival

    def unget(self, arrival):
        heapq.heappush(self.arrivals, arrival)

    def __len__(self):
        # Note that this gives, by built-in conversion rules, that (len(self) == 0) ==> not bool(self)
        return len(self.arrivals)


def time_schedule(clazz, rate, duration, unget_ratio=0.001, putback_prob=0.5):
    sked = clazz(rate, duration)

    def exercise(sked):
        ungot = None
        while sked:
            arr = sked.get()
            if random.random() <= unget_ratio:
                ungot = arr
            if ungot is not None and random.random() < 0.5:
                sked.unget(ungot)
                ungot = None

    return timeit.timeit(lambda: exercise(sked), setup='gc.enable()', number=1000)


if __name__ == '__main__':
    putback_prob = 0.3333
    print(f"putback probability {putback_prob}")
    print("Duration\tPQ Time\tDeque Time")
    for dur in [60, 120, 600, 2**10, 1200, 3000, 5000, 2**13]:
        pt = time_schedule(PQSchedule, 1000, dur, putback_prob=putback_prob)
        dt = time_schedule(DequeSchedule, 1000, dur, putback_prob=putback_prob)
        print(f"{dur}\t{pt}\t{dt}")
