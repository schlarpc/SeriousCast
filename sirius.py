#!/usr/bin/env python3.3

import re
import hashlib
import binascii
import xml.etree.ElementTree as ET
import json
import struct
import time
import logging

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

import requests


class SiriusException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


class Sirius():
    BASE_URL = 'https://www.siriusxm.com/player/'
    HARDWARE_ID = '00000000'
    ETHERNET_MAC = '0000CAFEBABE'
    KEY_LENGTH = 16
    PACKET_AES_KEY = 'D0DB1CA3B300831A301AF9144FC6986A'


    def _encrypt(self, plaintext):
        """
        Encryption based on account password
        Key is derived using PBKDF2 and a salt
        """
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(bytes(16)), backend=self.backend)
        encryptor = cipher.encryptor()
        return encryptor.update(bytes.fromhex(plaintext)) + encryptor.finalize()


    def _decrypt(self, ciphertext):
        """
        Decryption based on account password
        Key is derived using PBKDF2 and a salt
        """
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(bytes(16)), backend=self.backend)
        decryptor = cipher.decryptor()
        return decryptor.update(bytes.fromhex(ciphertext)) + decryptor.finalize()


    def _decrypt_packet(self, data):
        """
        This is a completely different kind of crypto used for audio packets
        The key is hard coded in the player because of reasons
        IVs are prepended to each packet, this is "simple AES" in their code
        """
        key = bytes.fromhex(self.PACKET_AES_KEY)
        iv = data[:16]
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=self.backend)
        decryptor = cipher.decryptor()
        return decryptor.update(data[16:]) + decryptor.finalize()


    def _filter_playlist(self, playlist, last=None, rewind=0):
        """
        Gets new items from a playlist, optionally given a resume point
        Rewind specifies a number of minutes to go back in history
        """
        playlist = [x.strip() for x in playlist.splitlines() if not x[0] == '#']
        if last and last in playlist:
            return playlist[playlist.index(last) + 1:]
        return playlist[-(10 + 3 * rewind):]


    def _parse_lineup(self, lineup):
        """
        This is called with the channel lineup to make it usable
        """
        self.lineup = {}
        for category in lineup['lineup-response']['lineup']['categories']:
            genres = category['genres']
            if isinstance(genres, dict):
                genres = [genres]

            for genre in genres:
                for channel in genre['channels']:
                    channel['genre'] = genre['name']
                    self.lineup[int(channel['siriusChannelNo'])] = channel


    def __init__(self):
        """
        Creates a new instance of the Sirius player
        At construction, we only get the global config and the channel lineup
        """
        self.backend = default_backend()
        self.token_cache = {}

        player_page = requests.get(self.BASE_URL).text
        config_url = re.search("flashvars.configURL = '(.+?)'", player_page).group(1)
        self.config = ET.fromstring(requests.get(config_url).text)

        lineup_url = self.config.findall("./consumerConfig/config[@name='ChannelLineUpBaseUrl']")[0].attrib['value']
        lineup = json.loads(requests.get(lineup_url + '/en-us/json/lineup/200/client/ump').text)
        self._parse_lineup(lineup)

        # with open('personal/lineup.json', 'w') as f:
            # f.write(json.dumps(self.lineup, indent=4, sort_keys=True))


    def login(self, username, password):
        """
        This negotiates the authentication with Sirius
        By the end of this method, self.key is set to the session AES key and
        self.session_id is set to your session ID
        """
        self.username = username
        self.password = password

        auth_url = self.config.findall("./consumerConfig/config[@name='AuthenticationBaseUrl']")[0].attrib['value']

        auth_request = json.dumps({
            'AuthenticationRequest': {
                'userName': username, 
                'consumerType': 'ump2',
            }
        })
        auth_challenge = json.loads(requests.post(auth_url + '/en-us/json/user/login/v3/initiate',
            auth_request).text)['AuthenticationResponse']

        challenge = auth_challenge['authenticationChallenge']
        salt = auth_challenge['salt']
        iterations = auth_challenge['iterationsCount']

        message_hash = hashlib.sha256(bytes.fromhex(self.HARDWARE_ID + self.ETHERNET_MAC + challenge)).hexdigest()
        message = challenge + message_hash[:32]

        password_hash = hashlib.md5(password.encode()).hexdigest()
        kdf = PBKDF2HMAC(
            algorithm = hashes.SHA256,
            length = self.KEY_LENGTH,
            salt = bytes.fromhex(salt),
            iterations = iterations,
            backend = self.backend,
        )
        self.key = kdf.derive(bytes.fromhex(password_hash))

        password_encrypted = self._encrypt(message + '10' * 16)

        auth_response = json.dumps({
            'AuthenticationRequest': {
                'userName': username, 
                'consumerType': 'ump2',
                'currency': 840,
                'playerIdentification': {
                    'hardwareIdentification': self.HARDWARE_ID,
                    'ethernetMac': self.ETHERNET_MAC,
                },
                'authenticationData': binascii.hexlify(password_encrypted).decode(),
            }
        })
        auth_result = json.loads(requests.post(auth_url + '/en-us/json/user/login/v3/complete',
            auth_response).text)['AuthenticationResponse']

        if auth_result['status'] == 0:
            if auth_result['messages']['code'] == 401:
                raise SiriusException('Invalid password')
            else:
                raise SiriusException('Unknown login error')

        self.session_id = auth_result['sessionId']


    def _channel_token(self, channel_key, invalidate=False):
        """
        Returns a 2-tuple that acts as a stream token
        """
        if not invalidate and channel_key in self.token_cache:
            return self.token_cache[channel_key]

        token_url = self.config.findall("./consumerConfig/config[@name='TokenBaseUrl']")[0].attrib['value']
        resp = requests.get(token_url + '/en-us/json/v3/streaming/ump2/' + channel_key + '/', params = {
            'sessionId': self.session_id,
        }).text

        resp = json.loads(resp)
        if 'tokenResponse' in resp and 'tokenData' in resp['tokenResponse']:
            token_response = resp['tokenResponse']
            token_data = self._decrypt(token_response['tokenData'])
            length = struct.unpack('<H', token_data[4:6])[0]
            channel_url, token = re.search('(.+?)\\?token=([a-f0-9_]+)',
                token_data[6 : 6 + length].decode()).group(1, 2)

            self.token_cache[channel_key] = (channel_url, token)
            return self.token_cache[channel_key]
        else:
            self.login(self.username, self.password)
            return self._channel_token(channel_key, True)


    def _get_token_resource(self, channel_key, file):
        """
        Retrieves a token protected channel resource, returns response object
        """
        channel_url, token = self._channel_token(channel_key)
        hq_path = channel_url + 'HLS_' + channel_key + '_64k/'
        resp = requests.get(hq_path + file, params={'token': token})
        if resp.status_code == 200:
            return resp
        else:
            logging.warning('Expired token, renewing')
            self._channel_token(channel_key, True)
            return self._get_token_resource(channel_key, file)


    def get_playlist(self, channel_key):
        """
        Retrieve m3u8 playlist for a given channel
        """
        resp = self._get_token_resource(channel_key, channel_key + '_64k_large.m3u8')
        return resp.text


    def get_segment(self, channel_key, segment):
        """
        Get a media segment from a channel, return decrypted as MPEG TS
        """
        resp = self._get_token_resource(channel_key, segment)
        segment = self._decrypt_packet(resp.content)
        return segment


    def packet_generator(self, id, rewind=0):
        """
        Generator that produces AAC-HE audio in an MPEG-TS container
        See also: HTTP Live Streaming
        Rewind specifies a number of minutes to go back in history
        """
        channel_url, token = self._channel_token(id)

        hq_url = channel_url + 'HLS_' + id + '_64k/'
        playlist_url = hq_url + id + '_64k_large.m3u8'
        playlist = []
        entry = None

        while True:
            if len(playlist) < 3:
                resp = requests.get(playlist_url, params={'token': token})
                if resp.status_code == 200:
                    new_entries = self._filter_playlist(resp.text, entry, rewind)
                    playlist += [x for x in new_entries if x not in playlist]
                else:
                    logging.warning('Expired token, renewing')
                    channel_url, token = self._channel_token(id, True)

            if len(playlist):
                entry = playlist.pop(0)
                logging.debug('Got audio chunk ' + entry)

                resp = requests.get(hq_url + entry, params={'token': token})
                if resp.status_code == 200:
                    yield self._decrypt_packet(resp.content)
                else:
                    playlist.insert(0, entry)
                    logging.warning('Expired token, renewing')
                    channel_url, token = self._channel_token(id, True)
            else:
                time.sleep(10)
