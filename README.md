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

## API Reference

