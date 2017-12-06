'''
Copyright (C) 2016 CG Cookie
http://cgcookie.com
hello@cgcookie.com

Created by Jonathan Denning, Jonathan Williamson, and Patrick Moore

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import bgl
import bpy
import re
from ..lib.common_utilities import dprint


class Shader():
    @staticmethod
    def shader_compile(shader):
        '''
        logging and error-checking not quite working :(
        '''
        
        bufLen = bgl.Buffer(bgl.GL_BYTE, 4)
        bufLog = bgl.Buffer(bgl.GL_BYTE, 2000)
        
        bgl.glCompileShader(shader)
        
        bgl.glGetShaderInfoLog(shader, 2000, bufLen, bufLog)
        log = ''.join(chr(v) for v in bufLog.to_list() if v)
        return log
    
    def __init__(self, srcVertex, srcFragment, funcStart=None):
        self.buf_zero = bgl.Buffer(bgl.GL_INT, 1)
        
        self.shaderProg = bgl.glCreateProgram()
        self.shaderVert = bgl.glCreateShader(bgl.GL_VERTEX_SHADER)
        self.shaderFrag = bgl.glCreateShader(bgl.GL_FRAGMENT_SHADER)
        
        bgl.glShaderSource(self.shaderVert, srcVertex)
        bgl.glShaderSource(self.shaderFrag, srcFragment)
        
        dprint('RetopoFlow Shader Info')
        logv = self.shader_compile(self.shaderVert)
        logf = self.shader_compile(self.shaderFrag)
        if len(logv.strip()):
            dprint('  vert log:\n' + '\n'.join(('    '+l) for l in logv.splitlines()))
        if len(logf.strip()):
            dprint('  frag log:\n' + '\n'.join(('    '+l) for l in logf.splitlines()))
        
        bgl.glAttachShader(self.shaderProg, self.shaderVert)
        bgl.glAttachShader(self.shaderProg, self.shaderFrag)
        
        bgl.glLinkProgram(self.shaderProg)
        
        self.shaderVars = {}
        lvars = [l for l in srcVertex.splitlines() if l.startswith('in ')]
        lvars += [l for l in srcVertex.splitlines() if l.startswith('attribute ')]
        lvars += [l for l in srcVertex.splitlines() if l.startswith('uniform ')]
        lvars += [l for l in srcFragment.splitlines() if l.startswith('uniform ')]
        for l in lvars:
            m = re.match('^(?P<qualifier>[^ ]+) +(?P<type>[^ ]+) +(?P<name>[^ ;]+)', l)
            assert m
            m = m.groupdict()
            q,t,n = m['qualifier'],m['type'],m['name']
            locate = bgl.glGetAttribLocation if q in {'in','attribute'} else bgl.glGetUniformLocation
            if n in self.shaderVars: continue
            self.shaderVars[n] = {
                'qualifier': q,
                'type': t,
                'location': locate(self.shaderProg, n),
                }
        
        dprint('  attribs: ' + ', '.join((k + ' (%d)'%self.shaderVars[k]['location']) for k in self.shaderVars if self.shaderVars[k]['qualifier'] in {'in','attribute'}))
        dprint('  uniforms: ' + ', '.join((k + ' (%d)'%self.shaderVars[k]['location']) for k in self.shaderVars if self.shaderVars[k]['qualifier'] in {'uniform'}))
        
        self.funcStart = funcStart
    
    # https://www.opengl.org/sdk/docs/man/html/glVertexAttrib.xhtml
    # https://www.khronos.org/opengles/sdk/docs/man/xhtml/glUniform.xml
    def assign(self, varName, varValue):
        assert varName in self.shaderVars, 'Variable %s not found' % varName
        v = self.shaderVars[varName]
        q,l,t = v['qualifier'],v['location'],v['type']
        if l == -1: return
        #print(varName + '=' + str(varValue))
        if q in {'in','attribute'}:
            if t == 'float':
                bgl.glVertexAttrib1f(l, varValue)
            elif t == 'int':
                bgl.glVertexAttrib1i(l, varValue)
            elif t == 'vec3':
                bgl.glVertexAttrib3f(l, *varValue)
            elif t == 'vec4':
                bgl.glVertexAttrib4f(l, *varValue)
            else:
                assert False, 'Unhandled type %s for attrib %s' % (t, varName)
        elif q in {'uniform'}:
            if t == 'float':
                bgl.glUniform1f(l, varValue)
            elif t == 'bool':
                bgl.glUniform1i(l, 1 if varValue else 0)
            elif t == 'vec3':
                bgl.glUniform3f(l, *varValue)
            elif t == 'vec4':
                bgl.glUniform4f(l, *varValue)
            elif t == 'mat3':
                bgl.glUniformMatrix3fv(l, 9, bgl.GL_FALSE, varValue)
            elif t == 'mat4':
                bgl.glUniformMatrix4fv(l, 16, bgl.GL_FALSE, varValue)
            else:
                assert False, 'Unhandled type %s for uniform %s' % (t, varName)
        else:
            assert False, 'Unhandled qualifier %s for variable %s' % (q, varName)
    
    def enableVertexAttribArray(self, varName):
        assert varName in self.shaderVars, 'Variable %s not found' % varName
        v = self.shaderVars[varName]
        bgl.glEnableVertexAttribArray(v['location'])
    
    def vertexAttribPointer(self, varName, size, gltype, normalized=bgl.GL_FALSE, stride=0, buf=None):
        assert varName in self.shaderVars, 'Variable %s not found' % varName
        v = self.shaderVars[varName]
        buf = buf or self.buf_zero
        bgl.glVertexAttribPointer(v['location'], size, gltype, normalized, stride, buf)
    
    def disableVertexAttribArray(self, varName):
        assert varName in self.shaderVars, 'Variable %s not found' % varName
        v = self.shaderVars[varName]
        bgl.glDisableVertexAttribArray(v['location'])
    
    def useFor(self,funcCallback):
        try:
            bgl.glUseProgram(self.shaderProg)
            if self.funcStart: self.funcStart(self)
            funcCallback(self)
        except Exception as e:
            print('ERROR WITH USING SHADER: ' + str(e))
        finally:
            bgl.glUseProgram(0)
    
    def enable(self):
        try:
            bgl.glUseProgram(self.shaderProg)
            if self.funcStart: self.funcStart(self)
        except Exception as e:
            print('Error with using shader: ' + str(e))
            bgl.glUseProgram(0)
    
    def disable(self):
        bgl.glUseProgram(0)


