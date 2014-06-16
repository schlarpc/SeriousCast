# SeriousCast

This is a SiriusXM Internet Radio to SHOUTcast bridge server.
It handles authentication and decryption of SiriusXM streams and remuxes them
into a format appropriate for standard internet radio streaming clients.

SeriousCast also offers a simple web streaming interface for all of its streams
using the VLC browser plugin.

## Requirements

SeriousCast is written in Python 3.

It has dependencies on:
* [cryptography](https://cryptography.io/en/latest/)
* [Requests](http://docs.python-requests.org/en/latest/)
* [Jinja2](http://jinja.pocoo.org/docs/)

You can use `pip install -r requirements.txt` to install these packages,
although Windows users may need to get an
[OpenSSL binary](https://www.openssl.org/related/binaries.html).

An experimental HTTP Live Streaming server is being implemented using Flask, in `flask_server.py`.
Flask is not required to run the SHOUTcast server.

## Setup

Make a copy of settings-example.cfg named settings.cfg.
Replace the `username` and `password` fields with your SiriusXM credentials.
The `hostname` field should be set to the publicly accessible hostname (or IP
address) for your server.

After editing the configuration file, you should be able to run `server.py`
to start the service. Navigate to the configured port (default 30000) in a web
browser to get a list of available channels. Each channel has a "Stream" option,
which plays in your browser window, and a "Playlist" option, which downloads
a .pls file for use in your SHOUTcast player of choice.

## License

SeriousCast is licensed under the MIT (Expat) License.
