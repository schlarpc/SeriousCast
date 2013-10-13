# SeriousCast

This is a SiriusXM Internet Radio to SHOUTcast bridge server.
It handles authentication and decryption of SiriusXM streams and remuxes them
into a format appropriate for standard internet radio streaming clients.

## Requirements

It is written in Python 3 and has dependencies on:
* [PyCrypto](https://www.dlitz.net/software/pycrypto/)
* [requests](http://docs.python-requests.org/en/latest/)

Additionally, a copy of ffmpeg (on the PATH) is required for the stream muxing.

## Setup

Make a copy of settings-example.cfg named settings.cfg. Replace the username and
password fields with your SiriusXM credentials. The hostname field should be
set to the publicly accessible hostname for your server.

After editing the configuration file, you should be able to run server.py
to start the service.

## License

SeriousCast is licensed under the MIT (Expat) License.
