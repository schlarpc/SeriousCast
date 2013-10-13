# SeriousCast

This is a SiriusXM Internet Radio to SHOUTcast bridge server.
It handles authentication and decryption of SiriusXM streams and remuxes them
into a format appropriate for standard internet radio streaming clients.

## Requirements

It is written in Python 3 and has dependencies on:
* [PyCrypto](https://www.dlitz.net/software/pycrypto/)
* [Requests](http://docs.python-requests.org/en/latest/)
* [Jinja2](http://jinja.pocoo.org/docs/)

Additionally, a copy of ffmpeg (on the PATH) is required for the stream muxing.

## Setup

Make a copy of settings-example.cfg named settings.cfg. Replace the username and
password fields with your SiriusXM credentials. The hostname field should be
set to the publicly accessible hostname for your server.

After editing the configuration file, you should be able to run server.py
to start the service. Navigate to port 30000 in a web browser to get a list
of available channels along with .pls downloads for each.

## License

SeriousCast is licensed under the MIT (Expat) License.
