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

from collections import deque, OrderedDict
from PyQt5.QtGui import QTextDocument
from PyQt5.QtWidgets import QPlainTextDocumentLayout
from flint.glob import log

class HistoryAction (object):
    def __init__ (self, unfunc, unargs, refunc, reargs, descr):
        self.unfunc = unfunc
        self.unargs = unargs.copy()
        self.unargs["undo"] = True
        self.refunc = refunc
        self.reargs = reargs.copy()
        self.reargs["undo"] = True
        self.descr = descr
    
    def undo (self):
        log("debug", "UNDO %s(%s)" % (self.unfunc.__name__, self.unargs))
        self.unfunc(**self.unargs)
    
    def redo (self):
        log("debug", "REDO %s(%s)" % (self.refunc.__name__, self.reargs))
        self.refunc(**self.reargs)

class TreeEditor (object):
    def __init__ (self, nodecontainer):
        self.nodecontainer = nodecontainer
        self.nodeorder = OrderedDict()
        self.changes = deque()
        self.collapsednodes = []
        self.nodedocs = dict()
        self.hits = None
        
        historysize = 10 # OPTION
        self.undohistory = deque(maxlen=historysize)
        self.redohistory = deque(maxlen=historysize)
    
    def traverse (self):
        queue = deque()
        # queue element: (fromID, toID, state)
        # state:         None: auto, 1: normal, 0: ghost, -1: hidden
        queue.append((None, "0", None))
        nodes = self.nodecontainer.nodes
        visitlog = dict()
        neworder = OrderedDict()
        
        def follow (ID, state, sub=False):
            if sub:
                links = nodes[ID].subnodes
            else:
                links = nodes[ID].linkIDs
            
            for nextID in links:
                queue.append((ID, nextID, state))
        
        while queue:
            refID, curID, state = queue.popleft()
            fullID = (refID, curID)
            if fullID in neworder:
                continue
            visited = curID in visitlog
            skipped = visitlog.get(curID, False)
            collapsed = fullID in self.collapsednodes
            
            prefstate = 0
            if collapsed:
                if not visited:
                    visitlog[curID] = fullID # skip
            elif (visited and skipped) or not visited:
                visitlog[curID] = False # proceed
                prefstate = 1
            
            neworder[fullID] = prefstate if state is None else state
            
            if prefstate or state is not None:
                follow(curID, state, sub=True)
                follow(curID, state)
            
            if not queue: 
                for refID, fullID in visitlog.items():
                    if fullID:
                        # dead end: all instances of this node are collapsed
                        fromID, toID = fullID
                        if neworder[fullID] == 0:
                            neworder[fullID] = 1 # un-ghost last instance
                        follow(curID, -1, sub=True)
                        follow(toID, -1)
                        visitlog[refID] = False
        
        missingraw = [(ID, s) for ID, s in self.nodeorder.items() if ID not in neworder]
        missing = []
        misskeys = []
        toremove = []
        for ID, state in missingraw:
            if state is None: # marked for removal
                toremove.append(ID)
            else:
                missing.append(ID)
                misskeys.append(ID[1])
        changes = []
        for fullID, state in neworder.items():
            fromID, toID = fullID
            if fullID in self.nodeorder and self.nodeorder[fullID] is None:
                changes.append(("newitem", (fullID, state)))
            elif fullID not in self.nodeorder:
                if toID in misskeys:
                    index = misskeys.index(toID)
                    misskeys.pop(index)
                    oldID = missing.pop(index)
                    changes.append(("reparent", (oldID, fullID)))
                    if self.nodeorder[oldID] != neworder[fullID]:
                        changes.append(("setstate", (fullID, state)))
                else:
                    changes.append(("newitem", (fullID, state)))
            elif state != self.nodeorder[fullID]:
                changes.append(("setstate", (fullID, state)))
        toremove.extend(missing)
        for fullID in toremove:
            changes.append(("removeitem", (fullID,)))
        
        log("debug", "CHANGES %s" % changes)
        self.trash = nodes - visitlog.keys()
        self.changes.extend(changes)
        self.nodeorder = neworder
    
    def updatedocs (self):
        newnodedocs = dict()
        for nodeID, nodeobj in self.nodecontainer.nodes.items():
            if nodeID in self.nodedocs:
                newnodedocs[nodeID] = self.nodedocs[nodeID]
            else:
                newnodedocs[nodeID] = dict()
                if nodeobj.typename in ("talk", "response"):
                    textdoc = QTextDocument(self)
                    textdoc.setDocumentLayout(QPlainTextDocumentLayout(textdoc))
                    textdoc.setPlainText(nodeobj.text)
                    newnodedocs[nodeID]["text"] = textdoc
                commentdoc = QTextDocument(self)
                commentdoc.setDocumentLayout(QPlainTextDocumentLayout(commentdoc))
                commentdoc.setPlainText(nodeobj.comment)
                newnodedocs[nodeID]["comment"] = commentdoc
                
                for s in ("enterscripts", "exitscripts", "condition"):
                    scriptdoc = QTextDocument(self)
                    scriptdoc.setDocumentLayout(QPlainTextDocumentLayout(scriptdoc))
                    scriptdoc.setPlainText(self.scripttotext(nodeobj.__dict__[s]))
                    newnodedocs[nodeID][s] = scriptdoc
        self.nodedocs = newnodedocs
    
    def scripttotext (self, script):
        def calltotext (call):
            text = ""
            if call.typename == "script":
                text += call.funcname
                paramstr = []
                for p in call.funcparams:
                    if isinstance(p, str):
                        paramstr.append('"%s"' % p)
                    else:
                        paramstr.append('%s' % p)
                text += "(%s)" % ", ".join(paramstr)
            elif call.typename == "wrap":
                text += "["
                text += " {op} ".format(op=call.operatorname).join(calltotext(c) for c in call.calls)
                text += "]"
            return text
        
        if isinstance(script, list):
            return "; ".join(calltotext(c) for c in script)
        else:
            return calltotext(script)
    
    def addundoable (self, hist):
        self.undohistory.appendleft(hist)
        self.redohistory.clear()
    
    def linknode (self, nodeID, refID, pos=None, undo=False):
        self.nodecontainer.newlink(refID, nodeID, pos)
        
        if not undo:
            hist = HistoryAction(self.unlink,
                {"nodeID": nodeID, "refID": refID},
                self.linknode,
                {"nodeID": nodeID, "refID": refID, "pos": pos},
                "Link node %s to node %s" % (nodeID, refID))
            self.addundoable(hist)
    
    def linksubnode (self, subID, bankID, pos, undo=False):
        """Only called as Undo action, assume sane arguments."""
        self.nodecontainer.nodes[bankID].subnodes.insert(pos, subID)
    
    def addnode (self, nodeID, typename="", ndict=None, undo=False):
        if ndict is not None:
            nodedict = ndict
        elif typename and typename in self.nodecontainer.templates:
            nodedict = self.nodecontainer.templates[typename]
        else:
            return
        newobj = self.nodecontainer.newnode(nodedict, refID=nodeID)
        newid = newobj.ID
        
        if not undo:
            hist = HistoryAction(self.unlink,
                {"nodeID": newid, "refID": nodeID},
                self.linknode,
                {"nodeID": newid, "refID": nodeID},
                "Link new node %s to node %s" % (newid, nodeID))
            self.addundoable(hist)
        return newid
    
    def addsubnode (self, nodeID, typename="", ndict=None, undo=False):
        if ndict is not None:
            nodedict = ndict
        elif typename and typename in self.nodecontainer.templates:
            nodedict = self.nodecontainer.templates[typename]
        else:
            return
        nodedictmod = nodedict.copy()
        nodedictmod["nodebank"] = nodeID
        newobj = self.nodecontainer.newnode(nodedictmod, bankID=nodeID)
        newid = newobj.ID
        if newobj.typename in ("talk", "response"):
            self.changebanktype(nodeID, newobj.typename)
        elif newobj.typename == "trigger":
            self.changebanktype(nodeID, "talk")
        elif newobj.typename == "bank":
            newobj.banktype = self.nodecontainer.nodes[nodeID].banktype
        
        if not undo:
            pos = self.nodecontainer.nodes[nodeID].subnodes.index(newid)
            hist = HistoryAction(self.unlinksubnode,
                {"subID": newid, "bankID": nodeID},
                self.linksubnode,
                {"subID": newid, "bankID": nodeID, "pos": pos},
                "Add new subnode %s to node %s" % (newid, nodeID))
            self.addundoable(hist)
        return newid
    
    def changebanktype (self, bankID, banktype):
        nodes = self.nodecontainer.nodes
        bankobj = nodes[bankID]
        bankobj.banktype = banktype
        if bankobj.nodebank != -1:
            if nodes[bankobj.nodebank].banktype:
                return
            self.changebanktype(bankobj.nodebank, banktype)
        else:
            bankobj.banktype = banktype
            subbanks = [nodes[subID] for subID in bankobj.subnodes if nodes[subID].typename == "bank"]
            while subbanks:
                subbank = subbanks.pop(-1)
                if subbank.banktype != banktype:
                    self.changebanktype(subbank.ID, banktype)
                subbanks.extend([nodes[subID] for subID in subbank.subnodes if nodes[subID].typename == "bank"])
    
    def unlink (self, nodeID, refID, undo=False):
        nodeitem = self.itembyID(nodeID)
        cont = self.nodecontainer
        refnode = cont.nodes[refID]
        pos = refnode.linkIDs.index(nodeID)
        refnode.linkIDs.remove(nodeID)
        
        if not undo:
            hist = HistoryAction(self.linknode, {"nodeID": nodeID, "refID": refID, "pos": pos},
                self.unlink, {"nodeID": nodeID, "refID": refID},
                "Unlink node %s with subtree from %s" % (nodeID, refID))
            self.addundoable(hist)
    
    def unlinksubnode (self, subID, bankID, undo=False):
        cont = self.nodecontainer
        pos = cont.nodes[bankID].subnodes.index(subID)
        cont.nodes[bankID].subnodes.remove(subID)
        
        if not undo:
            hist = HistoryAction(
                self.linksubnode,   {"subID": subID, "bankID": bankID, "pos": pos},
                self.unlinksubnode, {"subID": subID, "bankID": bankID},
                "Unlink subnode %s from bank %s" % (subID, bankID))
            self.addundoable(hist)
    
    def unlink_inherit (self, nodeID, refID, undo=False):
        cont = self.nodecontainer
        nodeobj = cont.nodes[nodeID]
        refnode = cont.nodes[refID]
        pos = refnode.linkIDs.index(nodeID)
        refnode.linkIDs.remove(nodeID)
        inherited = []
        index = pos
        for orphan in nodeobj.linkIDs:
            if orphan not in refnode.linkIDs:
                inherited.append(orphan)
                refnode.linkIDs.insert(index, orphan)
                index += 1
        
        if not undo:
            hist = HistoryAction(self.undoinherit,
                {"nodeID": nodeID, "refID": refID, "pos": pos, "inherited": inherited},
                self.unlink_inherit, {"nodeID": nodeID, "refID": refID},
                "Unlink node %s from node %s" % (nodeID, refID))
            self.addundoable(hist)
    
    def undoinherit (self, nodeID, refID, pos, inherited, undo=False):
        """Only called as Undo action, assume sane arguments."""
        cont = self.nodecontainer
        ref = cont.nodes[refID]
        for childID in inherited:
            ref.linkIDs.remove(childID)
        cont.newlink(refID, nodeID, pos)
    
    def move (self, nodeID, refID, up, undo=False):
        cont = self.nodecontainer
        parent = cont.nodes[refID]
        if cont.nodes[nodeID].nodebank == -1:
            siblings = parent.linkIDs
        else:
            siblings = parent.subnodes
        
        nodeind = siblings.index(nodeID)
        if up:
            sibind = nodeind-1
            desc = "up"
        else:
            sibind = nodeind+1
            desc = "down"
        
        siblings[nodeind], siblings[sibind] = siblings[sibind], siblings[nodeind]
        
        if not undo:
            hist = HistoryAction(
                self.move, {"nodeID": nodeID, "refID": refID, "up": not up}, 
                self.move, {"nodeID": nodeID, "refID": refID, "up": up},
                "Move node %s %s" % (nodeID, desc))
            self.addundoable(hist)
    
    def parentswap (self, gpID, parID, nodeID, pos=None, undo=False):
        log("debug", "PARENSTSWAP %s" % str((gpID, parID, nodeID, pos, undo)))
        nodes = self.nodecontainer.nodes
        parlinks = nodes[parID].linkIDs
        childlinks = nodes[nodeID].linkIDs
        grandpalinks = nodes[gpID].linkIDs
        
        childindex = parlinks.index(nodeID)
        parlinks.remove(nodeID)
        parlinks.insert(childindex, parID)
        
        if pos is not None:
            log("debug", "- duplicate -> pos: %s; gplinks: %s" % (pos, grandpalinks))
            parindex = pos
            grandpalinks.insert(pos, parID)
        else:
            parindex = grandpalinks.index(parID)
        grandpalinks.pop(parindex)
        
        if nodeID not in grandpalinks:
            grandpalinks.insert(parindex, nodeID)
            dupepos = None
        else:
            dupepos = parindex
        
        nodes[parID].linkIDs = childlinks
        nodes[nodeID].linkIDs = parlinks
        
        if not undo:
            hist = HistoryAction(self.parentswap,
                {"gpID": gpID, "parID": nodeID, "nodeID": parID, "pos": dupepos},
                self.parentswap,
                {"gpID": gpID, "parID": parID, "nodeID": nodeID, "pos": None},
                "Swap node %s with parent %s" % (nodeID, parID))
            self.addundoable(hist)
    
    def nodetobank (self, nodeID, subID=None, undo=False):
        cont = self.nodecontainer
        selnode = cont.nodes[nodeID]
        nodedict = selnode.todict()
        
        bankdict = nodedict.copy()
        bankdict["type"] = "bank"
        bankdict["banktype"] = nodedict["type"] if nodedict["type"] in ("talk", "response") else "talk"
        clonedict = nodedict.copy()
        clonedict["links"] = []
        clonedict["nodebank"] = nodeID
        
        cont.newnode(bankdict, newID=nodeID, force=True)
        if subID is None:
            newobj = cont.newnode(clonedict, bankID=nodeID)
            subID = newobj.ID
        else:
            cont.nodes[nodeID].subnodes.insert(0, subID)
        
        self.nodedocs[subID] = self.nodedocs[nodeID]
        self.nodedocs.pop(nodeID)
        
        if not undo:
            hist = HistoryAction(self.banktonode, {"nodeID": nodeID},
                self.nodetobank, {"nodeID": nodeID, "subID": subID},
                "Transform node %s to Bank" % nodeID)
            self.addundoable(hist)
    
    def banktonode (self, nodeID, undo=False):
        cont = self.nodecontainer
        selnode = cont.nodes[nodeID]
        subID = selnode.subnodes[0]
        nodedict = cont.nodes[subID].todict()
        
        clonedict = nodedict.copy()
        clonedict["nodebank"] = selnode.nodebank
        clonedict["links"] = selnode.linkIDs
        
        cont.newnode(clonedict, newID=nodeID, force=True)
        
        self.nodedocs[nodeID] = self.nodedocs[subID]
        
        if not undo:
            hist = HistoryAction(self.nodetobank, {"nodeID": nodeID, "subID": subID}, 
                self.banktonode, {"nodeID": nodeID},
                "Transform node %s from Bank" % nodeID)
            self.addundoable(hist)
    
    def splitnode (self, nodeID, splitID=None, undo=False):
        cont = self.nodecontainer
        selnode = cont.nodes[nodeID]
        
        if splitID is None:
            nodedict = selnode.todict()
            nodedict["subnodes"] = []
            newnode = cont.newnode(nodedict)
            newID = newnode.ID
        else:
            newID = splitID
        selnode.linkIDs = [newID]
        
        if not undo:
            hist = HistoryAction(
                self.unlink_inherit, {"nodeID": newID, "refID": nodeID}, 
                self.splitnode, {"nodeID": nodeID, "splitID": newID},
                "Split node %s" % nodeID)
            self.addundoable(hist)
    
    def collapse (self, fullID, collapse=None):
        if fullID in self.collapsednodes:
            if collapse is None or not collapse:
                desc = "Uncollapse"
                self.collapsednodes.remove(fullID)
                col = False
        else:
            if collapse is None or collapse:
                desc = "Collapse"
                self.collapsednodes.append(fullID)
                col = True
        self.itembyfullID(fullID).collapse(col)
    
    def getfield (self, nodeobj, field):
        objdict = nodeobj.__dict__
        if field in objdict:
            return str(objdict[field])
        elif field == "entername":
            return "\n".join([s.funcname for s in nodeobj.enterscripts])
        elif field == "enterarg":
            return "\n".join(["\n".join([str(p) for p in s.funcparams]) for s in nodeobj.enterscripts])
        elif field == "exitname":
            return "\n".join([s.funcname for s in nodeobj.exitscripts])
        elif field == "exitarg":
            return "\n".join(["\n".join([str(p) for p in s.funcparams]) for s in nodeobj.exitscripts])
        elif field == "condname":
            retval = ""
            conds = [nodeobj.condition]
            while conds:
                cond = conds.pop(-1)
                for call in cond.calls:
                    if call.typename == "script":
                        retval += call.funcname+"\n"
                    elif call.typename == "wrap":
                        conds.append(call)
            return retval
        elif field == "condarg":
            retval = ""
            conds = [nodeobj.condition]
            while conds:
                cond = conds.pop(-1)
                for call in cond.calls:
                    if call.typename == "script":
                        retval += "\n".join([str(p) for p in call.funcparams])
                    elif call.typename == "wrap":
                        conds.append(call)
            return retval
    
    def search (self, query, fields):
        if not query or True not in fields.values():
            self.hits = None
        else:
            hits = []
            for nodeID, nodeobj in self.nodecontainer.nodes.items():
                for field in fields:
                    if field and query in self.getfield(nodeobj, field).casefold():
                        hits.append(nodeID)
            self.hits = hits
    
    def removenodes (self, nodeIDs):
        for nodeID in nodeIDs:
            self.nodecontainer.nodes.pop(nodeID)
            self.nodedocs.pop(nodeID)
        self.undohistory.clear()
        self.redohistory.clear()
    
    def removetrash (self):
        for nodeID in self.trash:
            self.nodecontainer.nodes.pop(nodeID)
            self.nodedocs.pop(nodeID)
        self.undohistory.clear()
        self.redohistory.clear()
