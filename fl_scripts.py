#!/usr/bin/env python

from time import sleep

class ScriptCalls (object):
	def sc_print (self, *params):
		print(" ".join(params))
		return True
	
	def sc_wait (self, *params):
		sleep(5)
		return True
	
	def sc_quick (self, *params):
		return True
	
	def sc_false (self, *params):
		return False
