# Introduction 

This is a minimal scheduling service with a REST-style interface. The service allows you to create a Schedule (a series of instants) then draw samples from that Schedule. The purpose is to simulate a Poisson arrival process for load testing.

The only entity is a Schedule; operations available on a Schedule are 
- create(arrival_rate _arrivals per second_, duration _in seconds_)
- start
- info
- wait -> 200 _Success_, 418 _Missed_, 410 _Done_
  - May delay an arbitrary amount of time, until the next arrival time
- draw _not implemented_
  - Produce the next arrival time immediately. The client must delay until that time.
- stop
- delete

# Installation

This is a Python 3 app. The requirements are listed in the "requirements.txt" file.

The service is built on aiohttp.

# Use

The schedule server uses `asyncio.sleep(delay)` to wait for the next scheduled time.
The granularity of this sleep depends on the resolution of the underlying clock, 
`time.monotonic()`. See [PEP 418](https://peps.python.org/pep-0418/) and `_clock_resolution`
in [asyncio/base_events.py](https://github.com/python/cpython/blob/main/Lib/asyncio/base_events.py)

If you need more than 1,000 arrivals per second, you should divide the scheduling work among
several independent copies of this service. Since each arrival is independent, the
cumulative schedule will be the same (stochastically) as if you'd piled the whole
schedule on one service.

## API Reference

