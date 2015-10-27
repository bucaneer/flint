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
		self.linkIDs = []
		self.realref = None
		for link in node_dict['links']:
			self.addlink(str(link['toID']))
		if 'condition' in node_dict:
			self.condition = ConditionCall(node_dict['condition'])
		else:
			self.condition = self.container.defaultcond
		self.script = 'script' in node_dict and ScriptCall(node_dict['script'])
		self.optvars = node_dict['vars'] if 'vars' in node_dict else dict()
		self.comment = 'comment' in node_dict and node_dict['comment']
		if 'nodebank' in node_dict:
			self.nodebank = node_dict['nodebank']
		else:
			self.nodebank = -1
	
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
	
	def todict (self):
		node_dict = { "type": self.typename, 
			"links": [{'toID':i} for i in self.linkIDs] }
		if self.condition is not self.container.defaultcond:
			node_dict['condition'] = self.condition.todict()
		if self.script:
			node_dict['script']    = self.script.todict()
		if self.optvars:
			node_dict['vars']      = self.optvars
		if self.comment:
			node_dict['comment']   = self.comment
		if self.nodebank != -1:
			node_dict['nodebank']  = self.nodebank
		return node_dict

class TextNode (ChartNode):
	def __init__ (self, container, node_dict, nodeID):
		super().__init__(container, node_dict, nodeID)
		self.text = node_dict['text']
		self.speaker = node_dict['speaker']
	
	def todict (self):
		node_dict = super().todict()
		node_dict.update({ "text": self.text, "speaker": self.speaker })
		return node_dict

class TalkNode (TextNode):
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

class ResponseNode (TextNode):
	pass

class BankNode (ChartNode):
	def __init__ (self, container, node_dict, nodeID):
		super().__init__(container, node_dict, nodeID)
		self.subnodes = []
		for subnode in node_dict['subnodes']:
			self.subnodes.append(subnode)
		

class NodesContainer (object):
	__types = { 'talk': TalkNode, 'response': ResponseNode, 'bank': BankNode,
		'root': ChartNode }
	def __init__ (self, nodes_dict):
		self.defaultcond = ConditionCall({"type":"cond","operator":"and","calls":[]})
		self.name = nodes_dict['name']
		self.nextID = str(nodes_dict['nextID'])
		self.nodes = dict()
		for nodeID, nodedict in nodes_dict['nodes'].items():
			nodeID = str(nodeID)
			self.newnode(nodedict, nodeID, traverse=False)
	
	def getnode (self, ID):
		return self.nodes[ID]
	
	def newnode (self, node_dict, newID=False, refID=False, bankID=False, traverse=True):
		if not newID:
			newID = self.nextID
			self.nextID = str(int(self.nextID) + 1)
		node = self.__types[node_dict['type']](self, node_dict, newID)
		if newID in self.nodes:
			raise RuntimeError("Duplicate ID in nodes list")
		self.nodes[newID] = node
		if refID:
			self.nodes[refID].addlink(newID)
		elif bankID:
			self.nodes[bankID].subnodes.append(newID)
		return node
	
	def newlink (self, fromID, toID, pos=None):
		if fromID != toID and toID in self.nodes and toID != "0" and \
		   fromID in self.nodes:			
			self.nodes[fromID].addlink(toID, pos=pos)
	
	def removenode (self, nodeID, forceinherit=False):		
		nodeobj = self.nodes[nodeID]
		for refID in nodeobj.referrers:
			try:
				self.removelink(refID, nodeID, forceinherit)
			except:
				raise RuntimeError("Link removal failed") 
		self.nodes.pop(childID)
	
	def removelink (self, refID, childID, forceinherit=False):
		assert refID in self.nodes 
		refnode = self.nodes[refID]
		assert childID in refnode.linkIDs
		childnode = self.nodes[childID]
		childindex = refnode.linkIDs.index(childID)
		for orphanID in childnode.linkIDs:
			if forceinherit:
				self.newlink(refID, orphanID, pos=childindex)
				childindex += 1
		refnode.linkIDs.remove(childID)
		return True
		
	def removesubnode (self, bankID, subID):
		banknode = self.nodes[bankID]
		assert isinstance(banknode, BankNode)
		assert subID in banknode.subnodes
		subnode = self.nodes[subID]
		banknode.subnodes.remove(subID)
		return True
	
	def siblingswap (self, parentID, childID1, childID2):
		parlinks = self.nodes[parentID].linkIDs
		assert childID1 in parlinks and childID2 in parlinks
		ind1 = parlinks.index(childID1)
		ind2 = parlinks.index(childID2)
		parlinks[ind2], parlinks[ind1] = parlinks[ind1], parlinks[ind2]
	
	def subnodeswap (self, bankID, subID1, subID2):
		assert isinstance(self.nodes[bankID], BankNode)
		subnodes = self.nodes[bankID].subnodes
		assert subID1 in subnodes and subID2 in subnodes
		ind1 = subnodes.index(subID1)
		ind2 = subnodes.index(subID2)
		subnodes[ind2], subnodes[ind1] = subnodes[ind1], subnodes[ind2]
	
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

