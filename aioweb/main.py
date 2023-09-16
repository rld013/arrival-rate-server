import asyncio
import logging
import random
import time
from collections import deque
from datetime import datetime, timezone

from aiohttp import web

_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

class Schedule:
    def __init__(self, rate, duration):
        self.underrun_count = 0
        self.arrival_count = int(duration * rate)
        arrivals = [
            duration * random.random()
            for _ in range(self.arrival_count)
        ]
        self.arrivals = deque(sorted(arrivals))
        _logger.info("Schedule(%s,%s) len %d", rate, duration, self.arrival_count)

        self.running = False
        self.start_time = None

    def unget(self, delay):
        self.arrivals.insert(0,delay)
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
        delay = self._next_delay()
        match delay:
            case None:
                status = 'done'
            case _ if delay < 0:
                self.underrun_count += 1
                status = 'missed'
            case _:
                await asyncio.sleep(delay)
                status = 'ok'
        return status, delay

    def _next_delay(self):
        if not self.running:
            return None
        try:
            next_arrival = self.arrivals.popleft()
        except IndexError:
            self.running = False
            return None
        next_time = self.start_time + next_arrival
        delay = next_time - time.time()
        return delay


# Done Implement check for underrun
# Done More logging
# TODO Store schedule in app rather than global
# TODO Handle client disconnect (push arrival back on deque)

theSchedule: Schedule | None = None


async def get_info(request):
    if theSchedule:
        return web.json_response(theSchedule.info())
    else:
        return web.json_response({'schedule':None})

async def get_go(request):
    if theSchedule and theSchedule.running:
        status, delay = await theSchedule.pause_til_next()
        _logger.info("/go -> %s delay %s", status, delay)
    else:
        _logger.info("stop")
        delay = None
        status = "Stop"
    resp = web.Response(text=status)
    try:
        await resp.prepare(request)
        await resp.write_eof()
    except:
        if delay:
            theSchedule.unget(delay)
    return resp


# app.route("/start/<float:arrival_rate>/<float:duration>")
async def start_service(request):
    global theSchedule
    arrival_rate = float(request.match_info['arrival_rate'])
    duration = float(request.match_info['duration'])
    theSchedule = Schedule(arrival_rate, duration)
    theSchedule.start()
    _logger.info("started")
    return web.Response(text="Running")


# app.route("/stop")
async def stop_service(_request):
    if theSchedule and theSchedule.running:
        _logger.info("stopping")
        theSchedule.stop()
    else:
        _logger.info("already stopped")

    return web.Response(text="Stopped")

app = web.Application()
app.add_routes([
    web.get("/", get_info),
    web.get("/go", get_go),
    web.get("/start/{arrival_rate}/{duration}", start_service),
    web.get("/stop", stop_service),
])

if __name__ == '__main__':
    web.run_app(app)
