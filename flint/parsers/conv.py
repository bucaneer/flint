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

import json
import os.path as path

def scripttotext (script):
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
        elif call.typename == "cond":
            text += "["
            text += " {op} ".format(op=call.operatorname).join(calltotext(c) for c in call.calls)
            text += "]"
        return text
    
    if isinstance(script, list):
        return "; ".join(calltotext(c) for c in script)
    else:
        return calltotext(script)

def parsescript (script):
    pass
    #lines = 

class ScriptCall (object):
    def __init__ (self, sc_dict, scripts=None):
        self.typename = sc_dict['type']
        self.funcname = sc_dict['command']
        self.funcparams = sc_dict.get('params', [])
        self._not = sc_dict.get('not', False)
        if scripts is None:
            self.funccall = None
            return
        self.scripts = scripts
        if self.funcname not in self.scripts:
            raise RuntimeError("Unknown script: %s" % self.funcname)
        self.funccall = self.scripts[self.funcname]
    
    def run (self):
        if self.funccall is None:
            return None
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

class ScriptWrapper (object):
    def __init__ (self, cond_dict, scripts=None):
        self.types = {"script":ScriptCall, "wrap":ScriptWrapper}
        self.operators = {"and":True, "or":False, ";":None}
        self.typename = cond_dict['type']
        self.operatorname = cond_dict['operator']
        self.operator = self.operators[self.operatorname]
        self.calls = []
        for call in cond_dict['calls']:
            typename = self.types[ call['type'] ]
            self.calls.append( typename(call, scripts) )
    
    def run (self):
        if not self.calls:
            return (True, None)
        for call in self.calls:
            if call.typename == "script":
                callsig = (call.funcname, (*call.funcparams,))
                value = call.run()
            else:
                callsig = None
                value = call.run()[0]
            if self.operator is not None and bool(value) != self.operator:
                return (value, callsig)
        return (value, callsig)
    
    def setoperator (self, operatorname):
        self.operatorname = operatorname
        self.operator = self.operators[operatorname]
    
    def todict (self):
        return {"type": self.typename, "operator": self.operatorname, 
            "calls": [call.todict() for call in self.calls] }

class ChartNode (object):
    def __init__ (self, container, node_dict, nodeID):
        self.container = container
        if container.proj:
            scripts = container.proj.scripts
        else:
            scripts = None
        self.typename = node_dict['type']
        self.ID = str(nodeID)
        self.linkIDs = []
        
        for link in node_dict.get('links', []):
            self.addlink(str(link))
        
        self.condition = ScriptWrapper(node_dict.get('condition', self.container.defaultcond), scripts)
        
        self.enterscripts = [ScriptCall(s, scripts) for s in node_dict.get('enterscripts', [])]
        self.exitscripts  = [ScriptCall(s, scripts) for s in node_dict.get('exitscripts',  [])]
        
        self.randweight  = node_dict.get("randweight",        0)
        self.nodebank    = node_dict.get("nodebank",         -1)
        self.text        = node_dict.get("text",             "")
        self.speaker     = node_dict.get("speaker",          "")
        self.listener    = node_dict.get("listener",         "")
        self.optvars     = node_dict.get("vars",         dict())
        self.comment     = node_dict.get("comment",          "")
        self.persistence = node_dict.get("persistence",      "")
        self.subnodes    = node_dict.get("subnodes",         [])
        self.banktype    = node_dict.get("banktype",         "")
        self.bankmode    = node_dict.get("bankmode",         "")
        self.questionhub = node_dict.get("questionhub",      "")
        self.triggerconv = node_dict.get("triggerconv",      "")
    
    def reinitscripts (self):
        if self.container.proj:
            scripts = self.container.proj.scripts
        else:
            scripts = None
        self.enterscripts = [ScriptCall(s.todict(), scripts) for s in self.enterscripts]
        self.exitcripts   = [ScriptCall(s.todict(), scripts) for s in self.exitscripts]
        self.condition = ScriptWrapper(self.condition.todict(), scripts)
    
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
    
    def hascond (self):
        return self.condition.todict() != self.container.defaultcondcall.todict()
    
    def hasenterscripts (self):
        return len(self.enterscripts) > 0
    
    def hasexitscripts (self):
        return len(self.exitscripts) > 0
    
    def copy (self):
        return self.container.types[self.typename](self.container, self.todict(), "")
    
    def todict (self):
        node_dict = { "type": self.typename }
        if self.linkIDs:
            node_dict["links"]        = self.linkIDs
        if self.hascond():
            node_dict['condition']    = self.condition.todict()
        if self.enterscripts:
            node_dict['enterscripts'] = [s.todict() for s in self.enterscripts]
        if self.exitscripts:
            node_dict['exitscripts']  = [s.todict() for s in self.exitscripts]
        if self.optvars:
            node_dict['vars']         = self.optvars
        if self.comment:
            node_dict['comment']      = self.comment
        if self.nodebank != -1:
            node_dict['nodebank']     = self.nodebank
        if self.persistence:
            node_dict['persistence']  = self.persistence
        if self.randweight:
            node_dict['randweight']   = self.randweight
        return node_dict
    
    def __repr__ (self):
        return "<%s %s>" % (type(self).__name__, self.ID)

class TextNode (ChartNode):
    def todict (self):
        node_dict = super().todict()
        if self.text:
            node_dict["text"]     = self.text
        if self.speaker:
            node_dict["speaker"]  = self.speaker
        if self.listener:
            node_dict["listener"] = self.listener
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
    
    def todict (self):
        node_dict = super().todict()
        if self.questionhub:
            node_dict["questionhub"] = self.questionhub
        return node_dict

class ResponseNode (TextNode):
    pass

class BankNode (ChartNode):
    def __init__ (self, container, node_dict, nodeID):
        super().__init__(container, node_dict, nodeID)
        if not self.bankmode:
            self.bankmode = "First"
    
    def todict (self):
        node_dict = super().todict()
        if self.subnodes:
            node_dict["subnodes"] = self.subnodes
        if self.bankmode and self.bankmode != "First":
            node_dict["bankmode"] = self.bankmode
        if self.banktype:
            node_dict["banktype"] = self.banktype
        return node_dict

class TriggerNode (ChartNode):
    def todict (self):
        node_dict = super().todict()
        if self.triggerconv:
            node_dict["triggerconv"] = self.triggerconv
        return node_dict

class NodesContainer (object):
    types = { 'talk': TalkNode, 'response': ResponseNode, 'bank': BankNode,
        'root': ChartNode, 'trigger': TriggerNode }
    def __init__ (self, nodes_dict, filename="", proj=None):
        self.defaultcond = {"type":"cond","operator":"and","calls":[]}
        self.defaultcondcall = ScriptWrapper(self.defaultcond)
        self.filename = path.abspath(filename) if filename else ""
        self.projfile = nodes_dict.get("project", "")
        self.proj = proj
        self.name = nodes_dict['name']
        self.nextID = str(nodes_dict['nextID'])
        self.nodes = dict()
        for nodeID, nodedict in nodes_dict['nodes'].items():
            nodeID = str(nodeID)
            self.newnode(nodedict, nodeID)
        self.defaulttemplates = {
            "bank":    {"type": "bank"},
            "talk":    {"type": "talk"},
            "response":{"type": "response"},
            "trigger": {"type": "trigger"}
            }
        self.templates = self.defaulttemplates.copy()
        self.templates.update(nodes_dict.get('templates', dict()))
    
    def reinitscripts (self):
        for node in self.nodes.values():
            node.reinitscripts()
    
    def newnode (self, node_dict, newID=False, refID=False, bankID=False, force=False):
        if not newID:
            newID = self.nextID
            self.nextID = str(int(self.nextID) + 1)
        node = self.types[node_dict['type']](self, node_dict, newID)
        if newID in self.nodes and not force:
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
    
    def savetofile (self):
        if not self.filename or self.filename.startswith("\0TEMP"):
            return
        writejson(self, self.filename)
    
    def todict (self):
        nodes_dict = {"name":self.name, "nextID":self.nextID, "nodes":self.nodes}
        if self.templates and self.templates is not self.defaulttemplates:
            nodes_dict["templates"] = dict()
            for typename, template in self.templates.items():
                if template != self.defaulttemplates[typename]:
                    nodes_dict["templates"][typename] = template
        if self.proj is not None:
            projfile = path.relpath(self.proj.filename, start=path.dirname(self.filename))
            nodes_dict["project"] = projfile
        return nodes_dict

def loadjson (filename, proj=None):
    with open(filename, 'r') as f:
        return NodesContainer(json.load(f), filename, proj=proj)

def writejson (nodecont, filename):
    with open(filename, 'w') as f:
        json.dump(nodecont, f, indent=3, separators=(',', ': '),
            sort_keys=True, ensure_ascii=False,
            default=lambda o: o.todict() )

def newcontainer (proj=None):
    nodes_dict = { "name": "Untitled", "nextID": 1, "nodes": { "0": {"type": "root"} } }
    return NodesContainer(nodes_dict, proj=proj)
