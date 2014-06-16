#!/usr/bin/env python3

import http.server
import socketserver
import socket
import subprocess
import re
import configparser
import struct
import os
import mimetypes
import json
import sys
import logging
import collections

import jinja2

import sirius
import mpegutils


class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class SeriousBackend(metaclass=Singleton):
    def __init__(self):
        if not os.path.isfile('settings.cfg'):
            logging.critical('settings.cfg not found')
            sys.exit(1)

        self._cfg = configparser.ConfigParser()
        self._cfg.read('settings.cfg')

        self.sxm = sirius.Sirius()
        self.templates = jinja2.Environment(loader=jinja2.FileSystemLoader('templates'), autoescape=True)

        username = self.config('username')
        password = self.config('password')
        logging.info('Signing in with username "{}"'.format(username))
        self.sxm.login(username, password)


    def config(self, key):
        return self._cfg.get('SeriousCast', key)


class SeriousHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


class SeriousRequestHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.sbe = SeriousBackend()
        super().__init__(*args, **kwargs)


    def send_standard_headers(self, content_length, headers=None, response_code=200):
        logging.debug('HTTP {} [{}] ({} b)'.format(response_code, self.path, content_length))

        self.protocol_version = 'HTTP/1.1'
        self.send_response_only(response_code)
        self.send_header('Connection', 'close')
        self.send_header('Content-length', content_length)

        if headers != None:
            for field_name, field_value in headers.items():
                self.send_header(field_name, field_value)

        self.end_headers()


    def index(self):
        template = self.sbe.templates.get_template('list.html')
        channels = sorted(self.sbe.sxm.lineup.values(), key=lambda k: k['siriusChannelNo'])
        html = template.render({'channels': channels})
        response = html.encode('utf-8')

        self.send_standard_headers(len(response), {
            'Content-type': 'text/html; charset=utf-8',
        })

        self.wfile.write(response)


    def file_not_found(self):
        template = self.sbe.templates.get_template('404.html')
        html = template.render()
        response = html.encode('utf-8')

        self.send_standard_headers(len(response), {
            'Content-type': 'text/html; charset=utf-8',
        }, response_code=404)

        self.wfile.write(response)


    def static_file(self, path):
        # we'll collapse .. and such and follow symlinks to make sure
        # we're staying inside of ./static/
        full_path = os.path.realpath(os.path.join("./static/", path))

        if full_path.startswith(os.path.realpath("./static/")):
            # if a better mime type than octet-stream is available, use it
            content_type = 'appllication/octet-stream'
            extension = os.path.splitext(full_path)[1]
            if extension in mimetypes.types_map:
                content_type = mimetypes.types_map[extension]

            with open(full_path, 'rb') as f:
                content = f.read()
                self.send_standard_headers(len(content), {
                    'Content-type': content_type,
                })
                self.wfile.write(content)
        else:
            self.file_not_found()


    def channel_stream(self, channel_number, rewind=0):
        channel_number = int(channel_number)
        rewind = int(rewind)

        if channel_number not in self.sbe.sxm.lineup:
            return self.file_not_found()

        channel = self.sbe.sxm.lineup[channel_number]
        url = 'http://{}:{}/'.format(self.sbe.config('hostname'), self.sbe.config('port'))

        logging.info('Streaming: Channel #{} "{}" with rewind {}'.format(
            channel_number,
            channel['name'],
            rewind))

        self.protocol_version = 'ICY' # if we don't pretend to be shoutcast, doctors HATE us
        self.send_response_only(200)
        self.send_header('Content-type', 'audio/aacp')
        self.send_header('icy-br', '64')
        self.send_header('icy-name', channel['name'])
        self.send_header('icy-genre', channel['genre'])
        self.send_header('icy-url', url)
        self.send_header('icy-metaint', '32768')
        self.end_headers()

        channel_id = str(channel['channelKey'])
        track_title = ''

        for ts_packet in self.sbe.sxm.packet_generator(channel_id, rewind):
            audio = bytearray()

            pes_streams = collections.defaultdict(bytearray)
            for pes_packet in mpegutils.parse_transport_stream(ts_packet):
                if 'payload' in pes_packet:
                    pes_streams[pes_packet['pid']].extend(pes_packet['payload'])

            for pid, pes_stream in pes_streams.items():
                for es_packet in mpegutils.parse_packetized_elementary_stream(pes_stream):
                    if pid == 768:
                        audio.extend(es_packet['payload'])
                    elif pid == 1024:
                        metadata = mpegutils.parse_sxm_metadata(es_packet['payload'])
                        if metadata:
                            new_title = '{} - {}'.format(metadata[1], metadata[0])
                            if new_title != track_title:
                                logging.info("Now playing: " + new_title)
                                track_title = new_title

                    if len(audio) >= 32768:
                        meta_title = "StreamTitle='" + track_title + "';"
                        meta_length = -(-len(meta_title) // 16)
                        meta_title = meta_title.ljust(meta_length * 16).encode('utf-8')
                        audio_interval = audio[:32768]
                        del audio[:32768]
                        try:
                            self.wfile.write(audio_interval)
                            self.wfile.write(bytes((meta_length,)))
                            self.wfile.write(meta_title)
                        except (ConnectionResetError, ConnectionAbortedError) as e:
                            logging.info('Connection dropped: ' + str(e))
                            return


    def channel_metadata(self, channel_number, rewind=0):
        channel_number = int(channel_number)
        rewind = int(rewind)

        if channel_number not in self.sbe.sxm.lineup:
            return self.file_not_found()

        channel = self.sbe.sxm.lineup[channel_number]
        channel_id = str(channel['channelKey'])
        packet = next(self.sbe.sxm.packet_generator(channel_id, rewind))
        metadata = self.extract_metadata(packet)

        response = json.dumps({
            'channel': channel,
            'nowplaying': metadata,
        }, sort_keys=True, indent=4).encode('utf-8')

        self.send_standard_headers(len(response), {
            'Content-type': 'application/json',
        })

        self.wfile.write(response)


    def channel_playlist(self, channel_number):
        channel_number = int(channel_number)

        if channel_number not in self.sbe.sxm.lineup:
            return self.file_not_found()

        template = self.sbe.templates.get_template('playlist.pls')
        playlist = template.render({'url': 'http://{}:{}/channel/{}'.format(
            self.sbe.config('hostname'),
            self.sbe.config('port'),
            channel_number)})
        response = playlist.encode('utf-8')

        filename = '{} - {}.pls'.format(channel_number, self.sbe.sxm.lineup[channel_number]['name'])
        filename = filename.encode('ascii', 'ignore').decode().replace(' ', '_')

        self.send_standard_headers(len(response), {
            'Content-type': 'audio/x-scpls',
            'Content-disposition': 'attachment; filename="{}"'.format(filename),
        })

        self.wfile.write(response)


    def do_GET(self):
        routes = (
            (r'^/$', self.index),
            (r'^/static/(?P<path>.+)$', self.static_file),
            (r'^/channel/(?P<channel_number>[0-9]+)$', self.channel_stream),
            (r'^/channel/(?P<channel_number>[0-9]+)/(?P<rewind>[0-9]+)$', self.channel_stream),
            (r'^/metadata/(?P<channel_number>[0-9]+)$', self.channel_metadata),
            (r'^/metadata/(?P<channel_number>[0-9]+)/(?P<rewind>[0-9]+)$', self.channel_metadata),
            (r'^/playlist/(?P<channel_number>[0-9]+)$', self.channel_playlist),
        )

        for route_path, route_handler in routes:
            match = re.search(route_path, self.path)
            if match:
                return route_handler(**match.groupdict())

        self.file_not_found()


if __name__ == '__main__':
    # Basic logging to file
    logging.basicConfig(level=logging.DEBUG,
        format='%(asctime)s :: %(levelname)s :: %(thread)d :: %(message)s',
        datefmt='%m/%d %H:%M',
        filename='seriouscast.log',
        filemode='w')

    # Set up console logging output
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console_format = logging.Formatter('%(levelname)s :: %(thread)-5d :: %(message)s')
    console.setFormatter(console_format)
    logging.getLogger('').addHandler(console)

    # Disable (most) logging from requests
    requests_log = logging.getLogger("requests")
    requests_log.setLevel(logging.WARNING)

    logging.info('Setting up server, please wait')
    sbe = SeriousBackend()
    port = int(sbe.config('port'))
    logging.info('Starting server on port {}'.format(port))
    server = SeriousHTTPServer(('0.0.0.0', port), SeriousRequestHandler)
    server.serve_forever()
