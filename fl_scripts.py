from time import sleep

class ScriptCalls (object):
	scripts = dict()
	
	def __init__ (self, func):
		self.scripts[func.__name__] = func

@ScriptCalls
def printwords (words):
	print(" ".join(words))

@ScriptCalls
def wait (seconds: int):
	sleep(seconds)

@ScriptCalls
def rettrue () -> bool:
	return True

@ScriptCalls
def retfalse () -> bool:
	return False

@ScriptCalls
def retbool (var: bool) -> bool:
	return var
