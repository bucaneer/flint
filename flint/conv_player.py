#!/usr/bin/env python3
#
# Copyright (C) 2015, 2016 Justas Lavišius
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import flint.parsers.proj as pp
import flint.parsers.conv as cp
import random
from PyQt5.QtWidgets import QTextBrowser, QApplication
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QUrl


class NodeDisplay:
	def __init__ (self, nodeobj):
		self.typename = nodeobj.typename
		self.banktype = nodeobj.banktype
		self.text = nodeobj.text
		self.speaker = nodeobj.speaker
		self.listener = nodeobj.listener
		self.questionhub = nodeobj.questionhub
		self.ids = [nodeobj.ID]
		self.triggerconv = nodeobj.triggerconv
		self.randweight = nodeobj.randweight
	
	def concattext (self, strings):
		self.text = "".join(strings)
	
	def setproxyIDs (self, IDlist):
		self.ids = IDlist + self.ids
	
	def setcheck (self, check):
		self.visible = check[0]
		if check[1] is not None:
			self.funcname = check[1][0]
			self.funcpars = check[1][1]
		else:
			self.funcname = self.funcpars = None
	
	def __repr__ (self):
		return "<%s %s %s>" % (type(self).__name__, self.ids, self.visible)

class ConvPlayer (object):
	def __init__ (self, projfile):
		self.projfile = projfile
		self.proj = self.loadproj(projfile)
		self.convs = dict()
		self.persisttemp = set()
		self.persistperm = dict()
		self.currentconv = None
		self.currentnode = None
		self.nextlist = None
	
	def loadproj (self, projfile):
		return pp.loadjson(projfile)
	
	def loadconvfile (self, relpath, start=False):
		abspath = self.proj.checkpath(relpath)
		if abspath is None:
			return False
		conv = cp.loadjson(abspath, self.proj)
		self.convs[relpath] = conv
		if relpath not in self.persistperm:
			self.persistperm[relpath] = set()
		if start:
			self.startconv(relapth)
		return True
	
	def loadconv (self, conv, start=False):
		if not conv or not conv.proj or conv.proj.filename != self.proj.filename:
			return False
		relpath = self.proj.relpath(conv.filename)
		if self.proj.checkpath(relpath) is None:
			return False
		self.convs[relpath] = conv
		if relpath not in self.persistperm:
			self.persistperm[relpath] = set()
		if start:
			self.startconv(relpath)
		return True
	
	def startconv (self, relpath):
		if relpath not in self.convs and not self.loadconvfile(relpath):
			raise RuntimeError("Invalid Conversation path: %s" % relpath)
		if self.currentconv is not None:
			self.leaveconv()
		self.currentconv = relpath
		self.setcurrentnode(NodeDisplay(self.convs[relpath].nodes["0"]))
	
	def leaveconv (self):
		self.persisttemp = set()
		self.currentconv = None
		self.currentnode = None
		self.nextlist = None
	
	def setcurrentnode (self, nodedisplay):
		if nodedisplay is None:
			self.leaveconv()
			return
		if self.currentnode:
			self.runscripts(self.currentnode.ids, "exit")
		self.currentnode = nodedisplay
		self.persisttemp.update(nodedisplay.ids)
		self.persistperm[self.currentconv].update(nodedisplay.ids)
		self.runscripts(nodedisplay.ids, "enter")
		self.nextlist = self.getnext(nodedisplay)
		if nodedisplay.typename == "talk":
			return
		elif nodedisplay.typename == "trigger":
			self.startconv(nodedisplay.triggerconv)
		else:
			if self.nextlist:
				self.setcurrentnode(self.nextlist[0])
			else:
				self.leaveconv()
	
	def runscripts (self, IDlist, slot):
		nodes = self.convs[self.currentconv].nodes
		for nodeID in IDlist:
			nodeobj = nodes[nodeID]
			if slot == "exit":
				scripts = nodeobj.exitscripts
			elif slot == "enter":
				scripts = nodeobj.enterscripts
			
			for script in scripts:
				script.run()

	def checknode (self, nodeID):
		nodes = self.convs[self.currentconv].nodes
		nodeobj = nodes[nodeID]
		if nodeobj.persistence == "OncePerConv" and nodeID in self.persisttemp:
			return (False, None)
		elif nodeobj.persistence == "OnceEver" and nodeID in self.persistperm[self.currentconv]:
			return (False, None)
		check = nodeobj.condition.run()
		if check[0] and nodeobj.typename == "bank":
			retcheck = (False, None)
			for subID in nodeobj.subnodes:
				if self.checknode(subID)[0]:
					retcheck = (True, None)
					break
			if retcheck[0] != check[0]:
				check = retcheck
		return check
	
	def filternodelist (self, rawlist):
		showlist = [nd for nd in rawlist if nd.visible] # only nodes that passed checks
		if not showlist:
			return []
		hit = showlist[0]
		nexttype = hit.typename if hit.typename != "bank" else hit.banktype
		if nexttype in ("talk", "trigger"):
			typelist = [nd for nd in showlist if nd.typename in ("talk", "trigger") or nd.banktype == "talk"]
		elif nexttype == "response":
			typelist = [nd for nd in rawlist if nd.typename == "response" or nd.banktype == "response"]
		
		if hit.randweight:
			typelist = self.shuffle(typelist)
		returnlist = []
		for nd in typelist:
			if nd.typename == nexttype:
				returnlist.append(nd)
			elif nd.typename == "bank" and nd.visible:
				returnlist.extend(self.getnextsub(nd))
		qhub = returnlist[0].questionhub
		if (qhub == "ShowOnce" and any(id in hit.ids for id in self.persisttemp)) or qhub == "ShowNever":
			return self.getnext(hit, fromhub=True)
		else:
			return returnlist
	
	def weightedchoice (self, weightdict):
		randweights = []
		weightsum = 0
		for nd, weight in weightdict.items():
			weightsum += weight
			randweights.append((nd, weightsum))
		r = random.uniform(0, weightsum)
		for nd, ceil in randweights:
			if ceil > r:
				return nd
	
	def shuffle (self, ndlist):
		weightdict = dict()
		for nd in ndlist:
			if nd.randweight:
				weightdict[nd] = nd.randweight
		shuffled = []
		for nd in weightdict:
			choice = self.weightedchoice(weightdict)
			shuffled.append(choice)
			weightdict[choice] = 0
		return shuffled
	
	def getnext (self, nodedisplay, fromhub=None):
		nodes = self.convs[self.currentconv].nodes
		nodeID = nodedisplay.ids[-1]
		nodeobj = nodes[nodeID]
		if nodeobj.nodebank != -1:
			return self.getnext(NodeDisplay(nodes[nodeobj.nodebank]))
		rawlist = []
		for childID in nodeobj.linkIDs:
			childdisplay = NodeDisplay(nodes[childID])
			childdisplay.setcheck(self.checknode(childID))
			if fromhub:
				childdisplay.setproxyIDs(nodedisplay.ids)
			rawlist.append(childdisplay)
		
		return self.filternodelist(rawlist)
	
	def getnextsub (self, nodedisplay):
		nodes = self.convs[self.currentconv].nodes
		nodeID = nodedisplay.ids[-1]
		nodeobj = nodes[nodeID]
		rawlist = []
		for subID in nodeobj.subnodes:
			subdisplay = NodeDisplay(nodes[subID])
			subdisplay.setcheck(self.checknode(subID))
			subdisplay.setproxyIDs(nodedisplay.ids)
			rawlist.append(subdisplay)
		
		filterlist = self.filternodelist(rawlist)
		showlist = [nd for nd in filterlist if nd.visible]
		if nodeobj.bankmode == "First":
			return [showlist[0]] if showlist else [filterlist[0]]
		elif nodeobj.bankmode == "All":
			return filterlist
		elif nodeobj.bankmode == "Append":
			text = [nd.text for nd in showlist]
			nd = showlist[0]
			nd.concattext(text)
			return [nd]

class TextPlayer (QTextBrowser):
	visitedNode = pyqtSignal(str)
	showedNode = pyqtSignal(str)
	closed = pyqtSignal()
	
	def __init__ (self, parent, projfile):
		super().__init__(parent)
		self.setOpenLinks(False)
		self.anchorClicked.connect(self.activatechoice)
		self.player = ConvPlayer(projfile)
		self.choices = dict()
	
	def startconv (self, conv):
		self.player.loadconv(conv, start=True) and self.displaycurrent()
	
	def startconvfile (self, relpath):
		self.player.startconv(relpath)
		self.displaycurrent()
	
	def displaycurrent (self):
		nd = self.player.currentnode
		self.emitshow(nd.ids)
		self.emitvisit(nd.ids)
		display = "<p>%s</p>" % nd.text
		choices = self.player.nextlist
		self.choices = dict()
		num = 1
		if not choices:
			self.choices[str(num)] = None
			display += '<p><a href="%s">[Leave]</a></p>' % num
		for choice in self.player.nextlist:
			self.emitshow(choice.ids)
			if choice.visible:
				if choice.typename == "response":
					if choice.funcname is not None:
						choicetext = '<p><a href="%s">[%s] %s</a></p>' % (num, choice.funcname, choice.text)
					else:
						choicetext = '<p><a href="%s">%s</a></p>' % (num, choice.text)
					self.choices[str(num)] = choice
					num += 1
				else:
					self.choices[str(num)] = choice
					display += '<p><a href="%s">[Continue]</a></p>' % num
					break
			else:
				choicetext = "<p>[FAILED: %s %s]</p>" % (choice.funcname, choice.funcpars)
			display += choicetext
		self.setHtml(display)
	
	@pyqtSlot(QUrl)
	def activatechoice (self, choiceURL):
		choice = self.choices[choiceURL.toDisplayString()]
		if choice is not None:
			self.emitvisit(choice.ids)
		self.player.setcurrentnode(choice)
		if self.player.currentnode is not None:
			self.displaycurrent()
		else:
			self.window().close()
	
	def closeEvent (self, event):
		self.closed.emit()
		super().closeEvent(event)
	
	def emitshow (self, nodeIDs):
		for nodeID in nodeIDs:
			self.showedNode.emit(nodeID)
	
	def emitvisit (self, nodeIDs):
		for nodeID in nodeIDs:
			self.visitedNode.emit(nodeID)
