#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ________________________________________________________________________
#
#  Copyright (C) 2014 Andrew Fullford
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# ________________________________________________________________________
#

import os, sys, logging, time, json, gc
import support
import taskforce.poll
import taskforce.httpd
import taskforce.http
from taskforce.utils import get_caller as my

try:
	from http.client import HTTPConnection
	from urllib.parse import parse_qs, urlparse, urlencode
except:
	from httplib import HTTPConnection
	from urlparse import parse_qs, urlparse
	from urllib import urlencode

env = support.env(base='.')

class Test(object):

	tcp_host = '127.0.0.1'
	tcp_port = 34567
	tcp_address = tcp_host + ':' + str(tcp_port)
	unx_address = os.path.join('/tmp', 's.' + __module__)
	http_test_map = {
		u'English': u'hello, world',
		u'français': u'bonjour le monde',
		u'deutsch': u'hallo welt',
		u'ελληνικά': u'γεια σας, στον κόσμο',
		u'español': u'hola mundo',
		u'ไทย': u'สวัสดี โลก',
		u'日本人': u'こんにちは世界',
		u'Nihonjin': u"kon'nichiwa sekai",
		u'中国': u'你好世界',
		u'Zhōngguó': u'nǐ hǎo shìjiè',
	}

	@classmethod
	def setUpAll(self, mode=None):
		self.log = support.logger()
		self.log.info("%s started", self.__module__)

	@classmethod
	def tearDownAll(self):
		gc.collect()
		self.log.info("%s ended", self.__module__)

	def getter(self, path):
		u = urlparse(path)
		self.log.info("GET path '%s', query '%s'", u.path, u.query)
		if u.path.endswith('/json'):
			return (200, json.dumps(self.http_test_map, indent=4)+'\n', 'application/json')
		else:
			text = """<html>
<head>
	<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
	<meta charset="UTF-8">
</head>
<body>
	<center>
	<table width=600>
"""
			for lang in sorted(self.http_test_map, key=lambda x: x.lower()):
				text += '\t\t<tr><td align="center">%s</td>' % (lang, )
				text += '<td align="center"><font size="15">%s</font></td></tr>\n' % (self.http_test_map[lang],)
			text += """</table>
	</center>
</body>
</html>
"""
			return (200, text, 'text/html; charset=utf-8')

	def poster(self, path, postdict):
		p = taskforce.httpd.merge_query(path, postdict)
		self.log.info('%d element post received', len(p))
		self.log.debug('Answer ...')
		for line in json.dumps(p, indent=4).splitlines():
			self.log.debug('%s', line)
		ans = json.loads(p.get('data')[0])
		if ans == self.http_test_map:
			return (200, 'ok\n', 'text/plain')
		text = ''
		for tag in set(list(ans), list(self.http_test_map)):
			text += "'%s' sent '%s' received '%s'\n" % (tag, self.http_test_map.get(tag), p.get(tag))
		return (409, 'bad\n' + text, 'text/plain')

	def do_get(self, httpc, httpd, path='/test/json'):
		httpd.register_get(r'/test/.*', self.getter)

		httpc.request('GET', path)

		pset = taskforce.poll.poll()
		pset.register(httpd, taskforce.poll.POLLIN)

		#  This is a little bit tricky because we are talking to ourselves,
		#  so immediately enter a poll loop, and collect the response once
		#  the daemon thread has been started.  This also means we can't
		#  exercise SSL because the httpd service needs control to complete
		#  the handshake.  SSL testing is done against the actual taskforce
		#  process in another test unit.
		#
		httpr = None
		done = False
		handled = False
		while not done:
			try:
				evlist = pset.poll(5000)
			except OSError as e:
				if e.errno != errno.EINTR:
					raise e
				else:
					self.log.info("%s Interrupted poll()", my(self))
					continue
			if not evlist:
				raise Exception("Event loop timed out")
			for item, mask in evlist:
				if item == httpd:
					try:
						item.handle_request()
					except Exception as e:
						self.log.warning("%s HTTP error -- %s", my(self), str(e))
				elif item == httpr:
					assert item.getheader('Content-Type') == 'application/json'
					text = httpr.read().decode('utf-8')
					self.log.info('%s %d byte response received', my(self), len(text))
					self.log.debug('%s Answer ...', my(self))
					for line in text.splitlines():
						self.log.debug('%s', line)
					ans = json.loads(text)
					assert ans == self.http_test_map
					done = True
					break
				else:
					raise Exception("Unknown event item: " + str(item))
			if not handled:
				httpr = httpc.getresponse()
				pset.register(httpr, taskforce.poll.POLLIN)
				self.log.info("%s HTTP response object successfully registered", my(self))
				handled = True

	def Test_A_tcp_https_connect(self):
		self.log.info("Starting %s", my(self))
		gc.collect()
		http_service = taskforce.httpd.HttpService()
		http_service.listen = self.tcp_address
		http_service.certfile = env.cert_file
		httpd = taskforce.httpd.server(http_service, log=self.log)
		l = support.listeners(log=self.log)
		self.log.info("Service active, listening on port %d: %s", self.tcp_port, l.get(self.tcp_port))
		assert self.tcp_port in l
		del httpd
		l = support.listeners(log=self.log)
		self.log.info("Service deleted, listening on port %d: %s", self.tcp_port, l.get(self.tcp_port))
		assert self.tcp_port not in l

	def Test_B_unx_https_connect(self):
		self.log.info("Starting %s", my(self))
		gc.collect()
		http_service = taskforce.httpd.HttpService()
		http_service.listen = self.unx_address
		http_service.certfile = env.cert_file
		httpd = taskforce.httpd.server(http_service, log=self.log)
		l = support.listeners(log=self.log)
		self.log.info("Service active, listening on %s", l.get(self.unx_address))
		assert self.unx_address in l
		del httpd
		l = support.listeners(log=self.log)
		self.log.info("Service deleted, listening on %s", l.get(self.unx_address))
		assert self.tcp_port not in l

	def Test_C_tcp_get(self):
		self.log.info("Starting %s", my(self))
		gc.collect()
		http_service = taskforce.httpd.HttpService()
		http_service.listen = self.tcp_address
		httpd = taskforce.httpd.server(http_service, log=self.log)
		httpc = taskforce.http.Client(address=self.tcp_address, log=self.log)
		self.do_get(httpc, httpd)
		httpd.close()
		del httpd

	def Test_D_unx_get(self):
		self.log.info("Starting %s", my(self))
		gc.collect()
		http_service = taskforce.httpd.HttpService()
		http_service.listen = self.unx_address
		httpd = taskforce.httpd.server(http_service, log=self.log)
		httpc = taskforce.http.Client(address=self.unx_address, log=self.log)
		self.do_get(httpc, httpd)
		httpd.close()
		del httpd

	def Test_E_get_error(self):
		self.log.info("Starting %s", my(self))
		gc.collect()
		http_service = taskforce.httpd.HttpService()
		http_service.listen = self.tcp_address
		httpd = taskforce.httpd.server(http_service, log=self.log)
		httpc = taskforce.http.Client(address=self.tcp_address, log=self.log)
		log_level = self.log.getEffectiveLevel()
		try:
			#  Mask the log message as we expect a failure
			self.log.setLevel(logging.CRITICAL)
			self.do_get(httpc, httpd, path='/invalid/path')
			expected_error_occurred = False
		except taskforce.http.HttpError as e:
			self.log.info("%s Received expected error -- %s", my(self), str(e))
			expected_error_occurred = True
		finally:
			self.log.setLevel(log_level)
		httpd.close()
		del httpd
		assert expected_error_occurred

	def Test_F_getmap_non_text_error(self):
		self.log.info("Starting %s", my(self))
		gc.collect()
		httpc = taskforce.http.Client(address='mmm.fullford.com:80', log=self.log)
		log_level = self.log.getEffectiveLevel()
		try:
			#  Mask the log message as we expect a failure
			self.log.setLevel(logging.CRITICAL)
			httpc.getmap('/invalid/path', {'with': 'invalid query'})
			expected_error_occurred = False
		except taskforce.http.HttpError as e:
			self.log.info("%s Received expected error -- %s", my(self), str(e))
			expected_error_occurred = True
		finally:
			self.log.setLevel(log_level)
		assert expected_error_occurred

	def Test_G_getmap_non_json_error(self):
		self.log.info("Starting %s", my(self))
		gc.collect()
		httpc = taskforce.http.Client(address='mmm.fullford.com:80', log=self.log)
		log_level = self.log.getEffectiveLevel()
		try:
			#  Mask the log message as we expect a failure
			self.log.setLevel(logging.CRITICAL)
			httpc.getmap('/', {'with': 'invalid query'})
			expected_error_occurred = False
		except taskforce.http.HttpError as e:
			self.log.info("%s Received expected error -- %s", my(self), str(e))
			expected_error_occurred = True
		finally:
			self.log.setLevel(log_level)
		assert expected_error_occurred

	def Test_H_post(self):
		self.log.info("Starting %s", my(self))
		gc.collect()
		http_service = taskforce.httpd.HttpService()
		http_service.listen = self.tcp_address
		httpd = taskforce.httpd.server(http_service, log=self.log)
		httpd.register_post(r'/test/.*', self.poster)

		body = urlencode({'data': json.dumps(self.http_test_map, indent=4)+'\n'})
		httpc = taskforce.http.Client(address=self.tcp_address)
		httpc.request('POST', '/test/json?hello=world', body, {"Content-type": "application/x-www-form-urlencoded"})

		pset = taskforce.poll.poll()
		pset.register(httpd, taskforce.poll.POLLIN)

		httpr = None
		done = False
		handled = False
		while not done:
			try:
				evlist = pset.poll(5000)
			except OSError as e:
				if e.errno != errno.EINTR:
					raise e
				else:
					self.log.info("Interrupted poll()")
					continue
			if not evlist:
				raise Exception("Event loop timed out")
			for item, mask in evlist:
				if item == httpd:
					try:
						item.handle_request()
					except Exception as e:
						self.log.warning("HTTP error -- %s", str(e))
				elif item == httpr:
					assert item.getheader('Content-Type') == 'text/plain'
					text = httpr.read().decode('utf-8')
					self.log.info('%d byte response received', len(text))
					self.log.debug('Answer ...')
					codeword = None
					for line in text.splitlines():
						if not codeword:
							codeword = line.split()[0]
						self.log.debug('%s', line)
					assert codeword == 'ok'
					done = True
					break
				else:
					raise Exception("Unknown event item: " + str(item))
			if not handled:
				httpr = httpc.getresponse()
				pset.register(httpr, taskforce.poll.POLLIN)
				self.log.info("HTTP response object successfully registered")
				handled = True
		del httpd
