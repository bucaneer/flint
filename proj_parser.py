import json
import os.path as path
import sys
import importlib
import conv_parser as cp

class FlintProject (object):
    def __init__ (self, projdict, filename=""):
        self.filename = path.abspath(filename)
        self.name = projdict.get("name", "")
        self.path = path.dirname(self.filename)
        self.scriptfile = projdict.get("scripts", "")
        self.scripts = self.initscripts(self.scriptfile)
        self.convs = self.initconvs(projdict.get("convs", []))
        self.tempconvs = []
    
    def initscripts (self, relpath):
        if relpath:
            abspath = path.join(self.path, relpath)
            if path.exists(abspath):
                modname, ext = path.splitext(path.basename(abspath))
                scriptdir = path.dirname(abspath)
                sys.path.append(scriptdir)
                scriptmod = importlib.import_module(modname)
                return scriptmod.ScriptCalls.scripts
            else:
                raise RuntimeError("Invalid script path: %s" % relpath)
        else:
            return dict()
    
    def initconvs (self, convs_list):
        paths = []
        for relpath in convs_list:
            if path.exists(path.abspath(path.join(self.path, relpath))):
                paths.append(relpath)
            else:
                raise RuntimeError("Invalid conversation path: %s" % relpath)
        paths.sort()
        return paths
    
    def checkpath (self, relpath):
        if relpath not in self.convs:
            return None
        abspath = path.abspath(path.join(self.path, relpath))
        if not path.exists(abspath):
            return None
        return abspath
    
    def relpath (self, abspath):
        return path.relpath(abspath, start=self.path)
    
    def registerconv (self, abspath):
        if not path.exists(abspath):
            raise RuntimeError("No such file: %s" % abspath)
        relpath = self.relpath(abspath)
        if relpath in self.convs:
            return # overwriting is OK
        self.convs.append(relpath)
        self.convs.sort()
    
    def savetofile (self):
        if self.filename == "":
            return
        writejson(self, self.filename)
    
    def todict (self):
        return {"scripts": self.scriptfile, "convs": self.convs, "name": self.name}

def loadjson (filename):
    with open(filename, 'r') as f:
        return FlintProject(json.load(f), filename)

def writejson (proj, filename):
    with open(filename, 'w') as f:
        json.dump(proj, f, indent=3, separators=(',', ': '),
            sort_keys=True, ensure_ascii=False,
            default=lambda o: o.todict() )
