#!/usr/bin/env python

from time import sleep

class ScriptCalls (object):
	def sc_print (self, words):
		print(" ".join(words))
		return True
	
	def sc_wait (self, seconds: int):
		sleep(seconds)
		return True
	
	def sc_quick (self):
		return True
	
	def sc_false (self):
		return False
	
	def sc_bool (self, var: bool):
		return var
