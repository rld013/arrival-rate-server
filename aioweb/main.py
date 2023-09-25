import asyncio
import logging
import math
import random
import time
from collections import deque
from datetime import datetime, timezone
from enum import Enum
from typing import TypeVar

import aiohttp
from aiohttp import web
routes = web.RouteTableDef()

_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


T = TypeVar("T")


def deque_insert_ordered(dq:deque[T], iv:T):
    """ Assuming that dq is ordered, insert iv in the correct place to preserve ordering.
    >>> dq = deque([1,2,4])
    >>> deque_insert_ordered(dq, 3)
    >>> dq
    deque([1, 2, 3, 4])
    >>> deque_insert_ordered(dq,0)
    >>> dq
    deque([0, 1, 2, 3, 4])
    >>> deque_insert_ordered(dq, 10)
    >>> dq
    deque([0, 1, 2, 3, 4, 10])
    >>> dq = deque()
    >>> deque_insert_ordered(dq,10.1)
    >>> dq
    deque([10.1])
    >>> deque_insert_ordered(dq, -3.2)
    >>> dq
    deque([-3.2, 10.1])
    """
    ix = 0
    for ix, v in enumerate(dq):
        if v >= iv:
            break
    else:
        ix = ix + 1
    dq.insert(ix, iv)


class SampleStatus(Enum):
    "Value is HTTP status code"
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


    def unget(self, delay):
        deque_insert_ordered(self.arrivals, delay)
        _logger.warning("unget of delay %f len(arrivals) now %d", delay, len(self.arrivals))
        self.running = True

    def info(self):
        if self.start_time:
            start_time = datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat()
        else:
            start_time = None
        return dict(
            arrival_count = self.arrival_count,
            arrival_remain_count = len(self.arrivals),
            start_time = start_time,
            running = self.running,
            underrun_count = self.underrun_count,
            status = self.status
        )

    def start(self):
        self.start_time = time.time()
        self.running = True
        _logger.info("Schedule started")

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


# Done Implement check for underrun
# Done More logging
# Done Store schedule in app rather than global
# Done Handle client disconnect (push arrival back on deque)
# TODO Rethink URLs
# Done Separate creation from starting and/or autostart
# TODO Add an optional delay to start
# TODO Split source code into web, schedule
# TODO Add other protocols (WebSocket, Server-sent events, SockJS)
# TODO Add an autorenew capability so a Schedule will optionally restart when it's exhausted

def get_schedule(request) -> Schedule:
    name = request.match_info['schedule']
    try:
        return request.app['schedules'][name]
    except KeyError:
        raise aiohttp.web.HTTPNotFound(reason="Schedule not found")


def set_schedule(request, sched):
    name = request.match_info['schedule']

    if sched:
        request.app['schedules'][name] = sched
    else:
        request.app['schedules'].pop(name, None)


@routes.get('/')
async def get_schedule_list(request):
    allSchedules = request.app['schedules']
    all_info = {nm:sk.info() for nm,sk in allSchedules.items()}
    return web.json_response(all_info)


@routes.get('/{schedule}/info')
async def get_info(request):
    theSchedule = get_schedule(request)
    return web.json_response(theSchedule.info())


@routes.get('/{schedule}/wait')
async def get_go(request):
    theSchedule = get_schedule(request)

    if not theSchedule.running:
        theSchedule.start()

    status, delay, arrival = await theSchedule.pause_til_next()
    _logger.info("/wait -> %s delay %s arrival %s", status, delay, arrival)
    resp = web.json_response({'status':status.name.lower(), 'arrival': arrival}, status=status.value)
    try:
        await resp.prepare(request)
        await resp.write_eof()
    except OSError:
        # In case client has disconnected, put the schedule back in the queue
        if delay is not None:
            theSchedule.unget(delay)
    return resp # resp has already been sent so this is a no-op


@routes.put("/{schedule}")
async def create_schedule(request):
    params = await request.post()
    arrival_rate = float(params.get('arrival_rate', 1.0))
    duration = float(params.get('duration', 10.0))
    theSchedule = Schedule(arrival_rate, duration)
    set_schedule(request, theSchedule)
    # theSchedule.start()
    _logger.info("created")
    return web.json_response(theSchedule.info())


@routes.post("/{schedule}/start")
async def start_schedule(request):
    theSchedule = get_schedule(request)
    theSchedule.start()
    _logger.info("started")
    return web.json_response(theSchedule.info())


@routes.post('/{schedule}/stop')
async def stop_schedule(request):
    theSchedule = get_schedule(request)
    if theSchedule.running:
        _logger.info("stopping")
        theSchedule.stop()
        info = theSchedule.info()
    else:
        _logger.info("already stopped")
        info = {'status': 'stopped'}

    return web.json_response(info)


@routes.delete('/{schedule}')
async def delete_schedule(request):
    old_sched = set_schedule(request, None)
    if old_sched:
        old_sched_info = old_sched.info()
    else:
        old_sched_info = {'schedule': None}
    return web.json_response(old_sched_info, status=200)


app = web.Application()
app.add_routes(routes)
app['schedules'] = dict()

if __name__ == '__main__':
    web.run_app(app)
