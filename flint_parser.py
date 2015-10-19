#!/usr/bin/env python

import fl_scripts
import json

class ScriptCall (fl_scripts.ScriptCalls):
	def __init__ (self, sc_dict):
		self.typename = sc_dict['type']
		self.funcname = sc_dict['command']
		if self.funcname[:3] != "sc_":
			raise RuntimeError("Attempted to bind non-custom function")
		self.funccall = getattr(self, self.funcname)
		self.funcparams = sc_dict['params'] if 'params' in sc_dict else []
		self._not = int(sc_dict['not']) if 'not' in sc_dict else False
	
	def run (self):
		if self._not:
			return not self.funccall(*self.funcparams)
		else:
			return self.funccall(*self.funcparams)
	
	def todict (self):
		sc_dict = {"type": self.typename, "command": self.funcname}
		if len(self.funcparams) > 0:
			sc_dict['params'] = self.funcparams
		if self._not:
			sc_dict['not'] = self._not
		return sc_dict

class ConditionCall (object):
	def __init__ (self, cond_dict):
		self.types = {"script":ScriptCall, "cond":ConditionCall}
		self.operators = {"and":True, "or":False}
		self.typename = cond_dict['type']
		self.operatorname = cond_dict['operator']
		self.operator = self.operators[cond_dict['operator']]
		self.calls = []
		for call in cond_dict['calls']:
			typename = self.types[ call['type'] ]
			self.calls.append( typename(call) )
	
	def run (self):
		for call in self.calls:
			if call.run() != self.operator:
				return not self.operator
		return self.operator
	
	def todict (self):
		return {"type": self.typename, "operator": self.operatorname, 
			"calls": [call.todict() for call in self.calls] }

class ChartNode (object):
	def __init__ (self, container, node_dict, nodeID):
		self.container = container
		self.typename = node_dict['type']
		self.ID = str(nodeID)
		self.text = node_dict['text']
		self.speaker = node_dict['speaker']
		self.linkIDs = []
		#self.children = []
		self.referrers = []
		self.realref = None
		for link in node_dict['links']:
			self.addlink(str(link['toID']))
		if 'condition' in node_dict:
			self.condition = ConditionCall(node_dict['condition'])
		else:
			self.condition = self.container.defaultcond
		self.script = 'script' in node_dict and ScriptCall(node_dict['script'])
		self.optvars = 'vars' in node_dict and node_dict['vars']
		self.comment = 'comment' in node_dict and node_dict['comment']
	
	def checkcond (self):
		return self.condition.run()
		
	def checkchildren (self):
		pass				
	
	def display (self):
		pass
	
	def addlink (self, nodeID, pos=None):
		if nodeID not in self.linkIDs:
			if pos is None:
				self.linkIDs.append(nodeID)
			else:
				self.linkIDs.insert(pos, nodeID)
	
	"""def addchild (self, nodeobj):
		self.children.append(nodeobj)"""
	
	def modreferrer (self, nodeID, isghost):
		if nodeID not in self.referrers:
			self.referrers.append(nodeID)
		if not isghost:
			self.realref = nodeID
			#self.parent.nodes[nodeID].addchild(self)
	
	def todict (self):
		node_dict = { "type": self.typename, "text": self.text, 
			"speaker": self.speaker, "links": [{'toID':i} for i in self.linkIDs] }
		if self.condition is not self.container.defaultcond:
			node_dict['condition'] = self.condition.todict()
		if self.script:
			node_dict['script']    = self.script.todict()
		if self.optvars:
			node_dict['vars']      = self.optvars
		if self.comment:
			node_dict['comment']   = self.comment
		return node_dict

class TalkNode (ChartNode):
	def display (self):
		return self.text
	
	def checkchildren (self):
		todisplay = []
		for nodeid in self.linkIDs:
			nodeobj = self.container.nodes[nodeid]
			cond = nodeobj.checkcond()
			if cond:
				todisplay.append(nodeid)
				if nodeobj.typename == "response":
					break

class ResponseNode (ChartNode):
	pass

class BankNode (ChartNode):
	pass

class NodesContainer (object):
	__types = {'talk': TalkNode, 'response': ResponseNode, 'bank': BankNode}
	def __init__ (self, nodes_dict):
		self.defaultcond = ConditionCall({"type":"cond","operator":"and","calls":[]})
		self.name = nodes_dict['name']
		self.nextID = str(nodes_dict['nextID'])
		self.nodes = dict()
		#self.nodegraph = dict()
		for nodeID, nodedict in nodes_dict['nodes'].items():
			nodeID = str(nodeID)
			self.newnode(nodedict, nodeID, traverse=False)
		self.traverse()
	
	def traverse (self, nodeID="0"):
		self.nodegraph = dict()
		nodeID = str(nodeID)
		queue = []
		rank = 0
		visited = {nodeID: False}
		queue.append((nodeID, rank))
		while queue:
			popped = queue.pop(0)
			curID = popped[0]
			curnode = self.nodes[curID]
			ghostref = visited[curID]
			rank = popped[1]
			visited[curID] = True
			if not ghostref:
				if curID not in self.nodegraph:
					self.nodegraph[curID] = []
					for nextID in curnode.linkIDs:
						isghost = nextID in visited
						self.nodegraph[curID].append((nextID, isghost))
						self.nodes[nextID].modreferrer(curID, isghost)
						#curnode.modreferrer(nextID, isghost)						
						queue.append((nextID, rank+1))
						visited[nextID] = nextID in visited and visited[nextID]
						#print("NODEGRAPH: ",self.nodegraph)
	
	def getnode (self, ID):
		return self.nodes[ID]
	
	def newnode (self, node_dict, newID=False, refID=False, traverse=True):
		if not newID:
			newID = self.nextID
			self.nextID = str(int(self.nextID) + 1)
		node = self.__types[node_dict['type']](self, node_dict, newID)
		if newID in self.nodes:
			raise RuntimeError("Duplicate ID in nodes list")
		self.nodes[newID] = node
		if refID:
			self.nodes[refID].addlink(newID)
			#if refID not in self.nodegraph:
			#	self.nodegraph[refID] = []
			#self.nodegraph[refID].append((newID, False))
			#self.nodegraph[newID] = []
		if traverse:
			self.traverse()
		#return newID
		return node
	
	def newlink (self, fromID, toID, pos=None):
		if fromID != toID and toID in self.nodes and toID != "0" and \
		   fromID in self.nodes:			
			self.nodes[fromID].addlink(toID, pos=pos)
			self.traverse()
	
	def removenode (self, nodeID, forceinherit=False):		
		nodeobj = self.nodes[nodeID]
		for refID in nodeobj.referrers:
			try:
				self.removelink(refID, nodeID, forceinherit)
			except:
				raise RuntimeError("Link removal failed") 
		del self.nodes[childID]
		self.traverse()
	
	def removelink (self, refID, childID, forceinherit=False):
		assert refID in self.nodes 
		refnode = self.nodes[refID]
		assert childID in refnode.linkIDs
		childnode = self.nodes[childID]
		childindex = refnode.linkIDs.index(childID)
		for orphanID in childnode.linkIDs:
			if forceinherit: # or len(childnode.referrers) == 1:
				self.newlink(refID, orphanID, pos=childindex)
				childindex += 1
		del childnode.referrers[childnode.referrers.index(refID)]
		del refnode.linkIDs[refnode.linkIDs.index(childID)]
		self.traverse()
		return True
	
	def siblingswap (self, parentID, childID1, childID2):
		parlinks = self.nodes[parentID].linkIDs
		assert childID1 in parlinks and childID2 in parlinks
		ind1 = parlinks.index(childID1)
		ind2 = parlinks.index(childID2)
		parlinks[ind2], parlinks[ind1] = parlinks[ind1], parlinks[ind2]
		self.traverse()
	
	def todict (self):
		return {"name":self.name, "nextID":self.nextID, "nodes":self.nodes}

def loadjson (filename):
	with open(filename, 'r') as f:
		return NodesContainer(json.load(f))

def writejson (nodecont, filename):
	with open(filename, 'w') as f:
		json.dump(nodecont, f, indent=3, 
			separators=(',', ': '), sort_keys=True,
			default=lambda o: o.todict() )

