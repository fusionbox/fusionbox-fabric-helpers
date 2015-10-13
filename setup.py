#!/usr/bin/env python
from setuptools import setup, find_packages
import subprocess

__doc__ = """
Fabric helpers.
"""

version = '0.6.0'

setup(
    name='fusionbox-fabric-helpers',
    version=version,
    description='Fabric Helpers',
    author='Fusionbox programmers',
    author_email='programmers@fusionbox.com',
    keywords='fabric helpers',
    long_description=__doc__,
    url='https://github.com/fusionbox/fusionbox-fabric-helpers',
    packages=find_packages(),
    namespace_packages=['fusionbox'],
    license='BSD',
    classifiers=[
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Unix',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Topic :: Software Development',
        'Topic :: Software Development :: Build Tools',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Software Distribution',
        'Topic :: System :: Systems Administration',
    ],
    test_suite='nose.collector',
    tests_require=[
        'nose>=1.2.1',
        'mock>=1.0.1',
        'virtualenv',
    ],
    install_requires=[
        'fabric>=1.4',
        'termcolor>=1.1.0',
        'django-backupdb>=0.4.3',
    ],
    requires=['fabric'],
)
