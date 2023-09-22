import asyncio
import logging
import math
import random
import time
from collections import deque
from datetime import datetime, timezone
from typing import TypeVar

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

class Schedule:
    def __init__(self, rate, duration):
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
        )

    def start(self):
        self.start_time = time.time()
        self.running = True
        _logger.info("Schedule started")

    def stop(self):
        self.running = False
        _logger.info("Schedule stopped")

    async def pause_til_next(self):
        delay, arrival = self._next_delay()
        match delay:
            case None:
                status = 'done'
            case _ if delay < 0:
                self.underrun_count += 1
                status = 'missed'
            case _:
                await asyncio.sleep(delay)
                status = 'ok'
        return status, delay, arrival

    def _next_delay(self):
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
# TODO Separate creation from starting
# TODO Add an optional delay to start
# TODO Split source code into web, schedule

# theSchedule: Schedule | None = None

def get_schedule(request) -> Schedule|None:
    name = request.match_info['sked']
    try:
        return request.app['schedules'][name]
    except KeyError:
        return None

def set_schedule(request, sched):
    name = request.match_info['sked']

    request.app['schedules'][name] = sched

@routes.get('/')
async def get_sked_list(request):
    allSchedules = request.app['schedules']
    all_info = {nm:sk.info() for nm,sk in allSchedules.items()}
    return web.json_response(all_info)

@routes.get('/{sked}')
async def get_info(request):
    theSchedule = get_schedule(request)
    if theSchedule:
        return web.json_response(theSchedule.info())
    else:
        return web.json_response({'schedule':None})

@routes.get('/{sked}/go')
async def get_go(request):
    theSchedule = get_schedule(request)
    if theSchedule and theSchedule.running:
        status, delay, arrival = await theSchedule.pause_til_next()
        _logger.info("/go -> %s delay %s arrival %s", status, delay, arrival)
    else:
        _logger.info("stop")
        delay = None
        status = "stop"
        arrival = None
    resp = web.json_response({'status':status, 'arrival': arrival})
    try:
        await resp.prepare(request)
        await resp.write_eof()
    except:
        if delay is not None:
            theSchedule.unget(delay)
    return resp


@routes.get("/{sked}/start")
async def start_service(request):
    arrival_rate = float(request.query.get('arrival_rate', 1.0))
    duration = float(request.query.get('duration', 10.0))
    theSchedule = Schedule(arrival_rate, duration)
    set_schedule(request, theSchedule)
    theSchedule.start()
    _logger.info("started")
    return web.json_response(theSchedule.info())


# app.route("/stop")
@routes.get('/{sked}/stop')
async def stop_service(request):
    theSchedule = get_schedule(request)
    if theSchedule and theSchedule.running:
        _logger.info("stopping")
        theSchedule.stop()
        info = theSchedule.info()
    else:
        _logger.info("already stopped")
        info = {'status': 'stopped'}

    return web.json_response(info)

app = web.Application()
app.add_routes(routes)
app['schedules'] = dict()

if __name__ == '__main__':
    web.run_app(app)
