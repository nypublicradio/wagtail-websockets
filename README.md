# Wagtail Websockets (WIP)

**NOTE: This is a work-in-progress/pre-alpha package, and is mostly intended as
a proof of concept.**

Library to use [django-channels](https://github.com/django/channels) within the
context of Wagtail, with the first use-case being **content-locking**.

## Requirements

1. Wagtail
2. Redis

## Installation

1. In your Wagtail project, run:

```
pip install git+https://github.com/nypublicradio/wagtail-websockets.git
```

2. Add the app to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
	...
	'content_locking',
	...
]
```

3. In your `settings.py`, add the following block:

```python
# The line below references a file we will create in step 4:
ASGI_APPLICATION = '<YOURPROJECTNAME>.routing.application'

# This references a Redis server that you will need to run - the IP address and
# port should match your own server:
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}

```
