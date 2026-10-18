"""The tests never ask GitHub: any real request fails them."""

import urllib.request


def _no_network(*args, **kwargs):
    raise AssertionError("a test tried the network")


urllib.request.urlopen = _no_network
