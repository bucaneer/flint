import fl_scripts
import json
import os.path as path

class ScriptCall (fl_scripts.ScriptCalls):
    def __init__ (self, sc_dict):
        self.typename = sc_dict['type']
        self.funcname = sc_dict['command']
        if self.funcname not in self.scripts:
            raise RuntimeError("Unknown script: %s" % self.funcname)
        self.funccall = self.scripts[self.funcname]
        self.funcparams = sc_dict.get('params', [])
        self._not = sc_dict.get('not', False)
    
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
    
    def setoperator (self, operatorname):
        self.operatorname = operatorname
        self.operator = self.operators[operatorname]
    
    def todict (self):
        return {"type": self.typename, "operator": self.operatorname, 
            "calls": [call.todict() for call in self.calls] }

class MetaCall (object):
    def __init__ (self, call_dict):
        types = {"script":ScriptCall, "cond":ConditionCall}
        typename = call_dict["type"]
        self.callobj = types[typename](call_dict)

class ChartNode (object):
    def __init__ (self, container, node_dict, nodeID):
        self.container = container
        self.typename = node_dict['type']
        self.ID = str(nodeID)
        self.linkIDs = []
        
        for link in node_dict.get('links', []):
            self.addlink(str(link))
        
        self.condition = ConditionCall(node_dict.get('condition', self.container.defaultcond))
        
        self.enterscripts = [ScriptCall(s) for s in node_dict.get('enterscripts', [])]
        self.exitscripts  = [ScriptCall(s) for s in node_dict.get('exitscripts',  [])]
        
        self.randweight  = node_dict.get("randweight",        0)
        self.nodebank    = node_dict.get("nodebank",         -1)
        self.text        = node_dict.get("text",             "")
        self.speaker     = node_dict.get("speaker",          "")
        self.listener     = node_dict.get("listener",        "")
        self.optvars     = node_dict.get("vars",         dict())
        self.comment     = node_dict.get("comment",          "")
        self.persistence = node_dict.get("persistence",      "")
        self.subnodes    = node_dict.get("subnodes",         [])
        self.banktype     = node_dict.get("banktype",   "First")
        self.questionhub = node_dict.get("questionhub",      "")
    
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
    def todict (self):
        node_dict = super().todict()
        if self.subnodes:
            node_dict["subnodes"] = self.subnodes
        if self.banktype != "First":
            node_dict["banktype"] = self.banktype
        return node_dict

class NodesContainer (object):
    types = { 'talk': TalkNode, 'response': ResponseNode, 'bank': BankNode,
        'root': ChartNode }
    def __init__ (self, nodes_dict, filename=""):
        self.defaultcond = {"type":"cond","operator":"and","calls":[]}
        self.defaultcondcall = ConditionCall(self.defaultcond)
        self.filename = path.abspath(filename)
        self.name = nodes_dict['name']
        self.nextID = str(nodes_dict['nextID'])
        self.nodes = dict()
        for nodeID, nodedict in nodes_dict['nodes'].items():
            nodeID = str(nodeID)
            self.newnode(nodedict, nodeID)
        self.defaulttemplates = {
            "bank":    {"type": "bank"},
            "talk":    {"type": "talk"},
            "response":{"type": "response"}
            }
        self.templates = self.defaulttemplates.copy()
        self.templates.update(nodes_dict.get('templates', dict()))
    
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
        if self.filename == "":
            return
        writejson(self, self.filename)
    
    def todict (self):
        nodes_dict = {"name":self.name, "nextID":self.nextID, "nodes":self.nodes}
        if self.templates is not self.defaulttemplates:
            nodes_dict["templates"] = dict()
            for typename, template in self.templates.items():
                if template != self.defaulttemplates[typename]:
                    nodes_dict["templates"][typename] = template
        return nodes_dict

def loadjson (filename):
    with open(filename, 'r') as f:
        return NodesContainer(json.load(f), filename)

def writejson (nodecont, filename):
    with open(filename, 'w') as f:
        json.dump(nodecont, f, indent=3, separators=(',', ': '),
            sort_keys=True, ensure_ascii=False,
            default=lambda o: o.todict() )

def newcontainer ():
    nodes_dict = { "name": "Untitled", "nextID": 1, "nodes": { "0": {"type": "root"} } }
    return NodesContainer(nodes_dict)
