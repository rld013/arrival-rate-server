import logging

import aiohttp
from aiohttp import web
from aiohttp.abc import Request

from webservice.schedule import Schedule

routes = web.RouteTableDef()

_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

# Done Implement check for underrun
# Done More logging
# Done Store schedule in app rather than global
# Done Handle client disconnect (push arrival back on deque)
# Wont Rethink URLs
# Done Separate creation from starting and/or autostart
# TODO Add an optional delay to start
# Done Split source code into web, schedule
# TODO Add other protocols (WebSocket, Server-sent events, SockJS)
# TODO Add an autorenew capability so a Schedule will optionally restart when it's exhausted
# Wont Use Priority Queue rather than deque, for easier putback


def get_schedule(request: Request) -> Schedule:
    name = get_schedule_name(request)
    try:
        return request.app['schedules'][name]
    except KeyError:
        raise aiohttp.web.HTTPNotFound(reason="Schedule not found")


def set_schedule(request: Request, sched: Schedule | None) -> Schedule | None:
    name = get_schedule_name(request)

    prev_sched = request.app['schedules'].pop(name, None)
    if sched is not None:
        request.app['schedules'][name] = sched
    else:
        pass
    return prev_sched


def get_schedule_name(request):
    name = request.match_info['schedule']
    return name


@routes.get('/')
async def get_schedule_list(request: Request):
    all_schedules = request.app['schedules']
    all_info = [sk.info()|{'name':nm} for nm, sk in all_schedules.items()]
    return web.json_response(all_info)


@routes.put("/{schedule}")
async def create_schedule(request: Request):
    params = await request.post()
    arrival_rate = float(params.get('arrival_rate', 1.0))
    duration = float(params.get('duration', 10.0))
    the_schedule = Schedule(arrival_rate, duration)
    set_schedule(request, the_schedule)
    # theSchedule.start()
    _logger.info("created")
    return web.json_response(the_schedule.info())


@routes.delete('/{schedule}')
async def delete_schedule(request: Request):
    old_sched = set_schedule(request, None)
    if old_sched:
        old_sched_info = old_sched.info()
    else:
        old_sched_info = {'schedule': None}
    return web.json_response(old_sched_info, status=200)


@routes.get('/{schedule}/info')
async def get_info(request: Request):
    the_schedule = get_schedule(request)
    return web.json_response(the_schedule.info())


@routes.get('/{schedule}/wait')
async def get_go(request: Request):
    the_schedule = get_schedule(request)

    the_schedule.start(force=False)

    status, delay, arrival = await the_schedule.pause_til_next()
    _logger.info("/wait -> %s delay %s arrival %s", status, delay, arrival)
    resp = web.json_response({'status': status.name.lower(), 'arrival': arrival}, status=status.value, reason=status.name)
    try:
        await resp.prepare(request)
        await resp.write_eof()
    except OSError:
        # In case client has disconnected, put the schedule back in the queue
        if arrival is not None:
            the_schedule.unget(arrival)
    return resp    # resp has already been sent so this is a no-op


@routes.post("/{schedule}/start")
async def start_schedule(request: Request):
    the_schedule = get_schedule(request)
    the_schedule.start(force=True)
    _logger.info("started")
    return web.json_response(the_schedule.info())


@routes.post('/{schedule}/stop')
async def stop_schedule(request: Request):
    the_schedule = get_schedule(request)
    if the_schedule.running:
        _logger.info("stopping")
        the_schedule.stop()
    else:
        _logger.info("already stopped")
    info = the_schedule.info()

    return web.json_response(info)


def init_app(app):
    if app is None:
        app = web.Application()
    app.add_routes(routes)
    app['schedules'] = dict()
    return app


if __name__ == '__main__':
    app = init_app()
    web.run_app(app)
