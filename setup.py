try:
    from pip.req import parse_requirements
except ImportError:
    # The req module has been moved to pip._internal in the 10 release.
    from pip._internal.req import parse_requirements
import lnt
import os
from sys import platform as _platform
import sys
from setuptools import setup, find_packages, Extension

if sys.version_info < (2, 7):
    raise RuntimeError("Python 2.7 or higher required.")

cflags = []

if _platform == "darwin":
    os.environ["CC"] = "xcrun --sdk macosx clang"
    os.environ["CXX"] = "xcrun --sdk macosx clang"
    cflags += ['-stdlib=libc++', '-mmacosx-version-min=10.7']

# setuptools expects to be invoked from within the directory of setup.py, but
# it is nice to allow:
#   python path/to/setup.py install
# to work (for scripts, etc.)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

cPerf = Extension('lnt.testing.profile.cPerf',
                  sources=['lnt/testing/profile/cPerf.cpp'],
                  extra_compile_args=['-std=c++11'] + cflags)

if "--server" in sys.argv:
    sys.argv.remove("--server")
    req_file = "requirements.server.txt"
else:
    req_file = "requirements.client.txt"
try:
    install_reqs = parse_requirements(req_file, session=False)
except TypeError:
    # In old PIP the session flag cannot be passed.
    install_reqs = parse_requirements(req_file)

reqs = [str(ir.req) for ir in install_reqs]

setup(
    name="LNT",
    version=lnt.__version__,

    author=lnt.__author__,
    author_email=lnt.__email__,
    url='http://llvm.org',
    license = 'Apache-2.0 with LLVM exception',

    description="LLVM Nightly Test Infrastructure",
    keywords='web testing performance development llvm',
    long_description="""\
*LNT*
+++++

About
=====

*LNT* is an infrastructure for performance testing. The software itself
consists of two main parts, a web application for accessing and visualizing
performance data, and command line utilities to allow users to generate and
submit test results to the server.

The package was originally written for use in testing LLVM compiler
technologies, but is designed to be usable for the performance testing of any
software.


Documentation
=============

The official *LNT* documentation is available online at:
  http://llvm.org/docs/lnt


Source
======

The *LNT* source is available in the LLVM SVN repository:
http://llvm.org/svn/llvm-project/lnt/trunk
""",

    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache-2.0 with LLVM exception',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Software Development :: Testing',
    ],

    zip_safe=False,

    # Additional resource extensions we use.
    package_data={'lnt.server.ui': ['static/*.ico',
                                    'static/*.js',
                                    'static/*.css',
                                    'static/*.svg',
                                    'static/bootstrap/css/*.css',
                                    'static/bootstrap/js/*.js',
                                    'static/bootstrap/img/*.png',
                                    'static/flot/*.min.js',
                                    'static/d3/*.min.js',
                                    'static/jquery/**/*.min.js',
                                    'templates/*.html',
                                    'templates/reporting/*.html',
                                    'templates/reporting/*.txt'],
                  'lnt.server.db': ['migrations/*.py'],
                  },

    packages=find_packages(),

    test_suite='tests.test_all',

    entry_points={
        'console_scripts': [
            'lnt = lnt.lnttool:main',
        ],
    },
    install_requires=reqs,

    ext_modules=[cPerf],

    python_requires='>=2.7',
)
