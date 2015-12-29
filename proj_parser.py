#!/usr/bin/env python3
#
# Copyright (C) 2015 Justas Lavišius
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
    
    def initscripts (self, relpath, reinit=False):
        if relpath:
            abspath = path.join(self.path, relpath)
            if path.exists(abspath):
                modname, ext = path.splitext(path.basename(abspath))
                scriptdir = path.dirname(abspath)
                sys.path.append(scriptdir)
                scriptmod = importlib.import_module(modname)
                if reinit:
                    scriptmod = importlib.reload(scriptmod)
                return scriptmod.ScriptCalls.scripts
            else:
                raise RuntimeError("Invalid script path: %s" % relpath)
        else:
            return dict()
    
    def reloadscripts (self):
        self.scripts = self.initscripts(self.scriptfile, reinit=True)
    
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

def newproject (filename, save=True, scripts=True):
    name = path.splitext(path.basename(filename))[0]
    proj = FlintProject({"name": name}, filename)
    if scripts:
        scriptpath = path.join(proj.path, "scripts.py")
        newscriptfile(scriptpath)
        proj.scripts = proj.initscripts(proj.relpath(scriptpath))
    if save or scripts:
        proj.savetofile()
    return proj

def newscriptfile (filename):
    with open(filename, 'x') as f:
        f.write(
"""\
class ScriptCalls (object):
    scripts = dict()
    
    def __init__ (self, func):
        self.scripts[func.__name__] = func

# Add function definitions decorated with "@ScriptCalls", like this:
#
#@ScriptCalls
#def exampleScript (arg1: bool, arg2: int):
#    pass
#
#@ScriptCalls
#def exampleCondition (arg: str) -> bool:
#    pass
"""
)
