#!/usr/bin/env python

# The MIT License
#
# Copyright (c) 2016-2018
# Wanding Zhou zhouwanding@gmail.com
# 
# Copyright (c) 2014, 2015 The University of Texas MD Anderson Cancer Center
# Wanding Zhou, Tenghui Chen and Ken Chen
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Contact: Wanding Zhou <zhouwanding@gmail.com>
#          Schaudge King <yuanshenran@gmail.com>

import os
import sys
import subprocess
try:
    from setuptools import setup, Extension
    from setuptools.command.install import install
    from setuptools.command.develop import develop
    from distutils.command.build import build
    havesetuptools = True
except ImportError:
    from distutils.core import setup, Extension
    from distutils.command.install import install
    from distutils.command.build import build
    havesetuptools = False

BASEPATH=os.path.dirname(os.path.abspath(__file__))

class TransVarBuild(build):

    def run(self):

        # run original build code
        build.run(self)

class TransVarInstall(install):

    def run(self):

        install.run(self)

cmdclass = {
    'build': TransVarBuild,
    'install': TransVarInstall,
}

if havesetuptools:
    class TransVarDevelop(develop):

        def run(self):
            develop.run(self)

    cmdclass['develop'] = TransVarDevelop

exec(open('varmap/version.py').read())

def main():
    ext_modules = [
        Extension("varmap.tabix",
                  sources = [
                      "external/pytabix/bgzf.c", "external/pytabix/bgzip.c",
                      "external/pytabix/index.c", "external/pytabix/knetfile.c",
                      "external/pytabix/kstring.c", "external/pytabix/tabixmodule.c"
                  ],
                  include_dirs=["external/pytabix"],
                  libraries=["z"],
                  define_macros=[("_FILE_OFFSET_BITS", 64), ("_USE_KNETFILE", 1)],
                  extra_compile_args=["-w"],
              ),
        Extension("varmap.ssw._sswlib",
                  sources = ['external/ssw/ssw.c', 'external/ssw/encode.c'],
                  include_dirs = ['external/ssw'],
                  extra_compile_args = ['-W', '-Wall', '-O2', '-finline-functions', '-fPIC', '-shared', '-Wl,-soname,sswlib'],
              ),
    ]

    install_requires = ['future']
    if sys.version_info[0] < 3:
        install_requires.append('configparser')

    setup(
        name = "varmap",
        version = __version__,
        description = "variant mapper (annotator) for multiple omics level!",
        author = "Schaudge King",
        author_email = "yuanshenran@gmail.com",
        license = "MIT",
        keywords = ["bioinformatics", "genomics"],
        scripts = ['bin/varmap'],
        packages = ['varmap', 'varmap.ssw'],
        ext_modules = ext_modules,
        classifiers = [
            "Programming Language :: Python",
            "Intended Audience :: Developers",
            "Intended Audience :: Science/Research",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
            'Operating System :: POSIX',
            "Programming Language :: C",
            "Topic :: Scientific/Engineering :: Bio-Informatics",
        ],
        cmdclass = cmdclass,
        platforms = "Linux, OSX",
        install_requires=install_requires,
    )

if __name__ == '__main__':
    main()
