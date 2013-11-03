#!/usr/bin/env python3.3

import http.server
import socketserver
import socket
import subprocess
import re
import configparser
import struct

import jinja2
import sirius


class SeriousHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


class SeriousRequestHandler(http.server.BaseHTTPRequestHandler):
    def extract_metadata(self, data):
        metadata = {'artist': '', 'title': '', 'album': ''}

        try:
            while True:
                # find the start of an MPEG PES
                idx = data.index(b'\x00\x00\x01')
                data = data[idx + 3:]

                # check if the stream id is the siriusxm metadata id, 0xbf
                if (data[0] == 0xbf):
                    packet_length, subtype, count = struct.unpack('!xHxxxxBB', data[:9])
                    data = data[9:]

                    # subtype FE is song info
                    if subtype == 0xfe:
                        els = []
                        for i in range(count):
                            length = data[0]
                            els.append(data[2 : length + 2])
                            data = data[length + 2:]
                        metadata = {
                            'title': els[0].decode('utf-8'),
                            'artist': els[1].decode('utf-8'),
                            'album': els[2].decode('utf-8'),
                            }
        except ValueError:
            pass

        return metadata


    def send_response_and_log(self, response_code):
        self.log_request(response_code)
        self.send_response_only(response_code)


    def channel_stream(self, channel_number):
        channel = sxm.lineup[channel_number]

        self.protocol_version = 'ICY' # if we don't pretend to be shoutcast, doctors HATE us
        self.log_request(200)
        self.send_response_only(200)
        self.send_header('Content-type', 'audio/aacp')
        self.send_header('icy-br', '64')
        self.send_header('icy-name', channel['name'])
        self.send_header('icy-genre', channel['genre'])
        self.send_header('icy-url', url)
        self.send_header('icy-metaint', '180000')
        self.end_headers()

        channel_id = str(channel['channelKey'])

        for packet in sxm.packet_generator(channel_id):
            # extracting metadata from the stream packet
            metadata = self.extract_metadata(packet)
            stream_title = '{} - {}'.format(metadata['artist'], metadata['title']).replace("'", '')
            print(stream_title)
            stream_title = "StreamTitle='" + stream_title + "';"
            meta_length = -(-len(stream_title) // 16)
            stream_title = stream_title.ljust(meta_length * 16).encode('utf-8')

            # convert stream from mpeg ts to adts
            command = ['ffmpeg', '-i', 'pipe:0', '-y', '-map', '0:1', '-c:a', 'copy', '-f', 'adts', 'pipe:1']
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            adts_data = proc.communicate(packet)[0]
            adts_data += b'\0' * (180000 - len(adts_data))

            try:
                self.wfile.write(adts_data)
                self.wfile.write(bytes((meta_length,)))
                self.wfile.write(stream_title)
            except (ConnectionResetError, ConnectionAbortedError) as e:
                print('Connection dropped: ', e)
                return


    def channel_playlist(self, channel_number):
        template = templates.get_template('playlist.pls')
        playlist = template.render({'url': url + 'channel/{}'.format(
            channel_number)})
        response = playlist.encode('utf-8')

        filename = '{} - {}.pls'.format(channel_number, sxm.lineup[channel_number]['name'])
        filename = filename.encode('ascii', 'ignore').decode().replace(' ', '_')

        self.protocol_version = 'HTTP/1.1'
        self.send_response_and_log(200)
        self.send_header('Content-type', 'audio/x-scpls')
        self.send_header('Content-disposition', 'attachment; filename="{}"'.format(filename))
        self.send_header('Content-length', len(response))
        self.send_header('Connection', 'close')
        self.end_headers()

        self.wfile.write(response)


    def index(self):
        template = templates.get_template('list.html')
        html = template.render({'channels': sorted(sxm.lineup.values(), key=lambda k: k['siriusChannelNo'])})
        response = html.encode('utf-8')

        self.protocol_version = 'HTTP/1.1'
        self.send_response_and_log(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Content-length', len(response))
        self.send_header('Connection', 'close')
        self.end_headers()

        self.wfile.write(response)


    def do_GET(self):
        match = re.search('^/channel/([0-9]+)$', self.path)
        if match:
            channel_number = int(match.group(1))
            return self.channel_stream(channel_number)

        match = re.search('^/playlist/([0-9]+)$', self.path)
        if match:
            channel_number = int(match.group(1))
            return self.channel_playlist(channel_number)

        self.index()


if __name__ == '__main__':
    print('Setting up, please wait')

    cfg = configparser.ConfigParser()
    cfg.read('settings.cfg')
    username = cfg.get('SeriousCast', 'username')
    password = cfg.get('SeriousCast', 'password')
    url = 'http://{}:{}/'.format(
        cfg.get('SeriousCast', 'hostname'),
        cfg.get('SeriousCast', 'port'),
    )

    sxm = sirius.Sirius()
    sxm.login(username, password)

    templates = jinja2.Environment(loader=jinja2.FileSystemLoader('templates'))

    port = cfg.getint('SeriousCast', 'port')
    server = SeriousHTTPServer(('0.0.0.0', port), SeriousRequestHandler)
    print('Starting server, use <Ctrl-C> to stop')
    server.serve_forever()
