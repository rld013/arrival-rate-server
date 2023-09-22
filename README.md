# Introduction 

This is a minimal scheduling service with a REST-style interface. The service allows you to create a Schedule (a series of instants) then draw samples from that Schedule. The purpose is to simulate a Poisson arrival process for load testing.

The only entity is a Schedule; operations available on a Schedule are 
- create
- start _not implemented_
- info
- wait
- draw _not implemented_
- stop
- delete _not implemented_

# Installation

This is a Python 3 app. The requirements are listed in the "requirements.txt" file.

The service is built on aiohttp.

# Use

## API Reference

