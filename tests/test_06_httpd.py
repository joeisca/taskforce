#!/usr/bin/env python
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

import os
import support
import taskforce.httpd

class Test(object):

	http_host = '127.0.0.1'
	http_port = 56789

	@classmethod
	def setUpAll(self, mode=None):
		self.log = support.logger()
		self.log.info("%s started", self.__module__)

	@classmethod
	def tearDownAll(self):
		self.log.info("%s ended", self.__module__)

	def Test_A_open_close(self):
		http = taskforce.httpd.Server(host=self.http_host, port=self.http_port, log=self.log)
		self.log.info("Server listening on: %s", str(http.server_address))
		l = support.listeners(log=self.log)
		self.log.info("Service active, listening on port %d: %s", self.http_port, l.get(self.http_port))
		assert self.http_port in l
		del http
		l = support.listeners(log=self.log)
		self.log.info("Service deleted, listening on port %d: %s", self.http_port, l.get(self.http_port))
		assert self.http_port not in l
