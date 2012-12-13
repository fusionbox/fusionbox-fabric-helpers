Introduction
============

Fabric helpers used by the development team at Fusionbox_ for server deployment.

Here is a minimal ``fabfile.py``::

    from fabric.api import roles
    
    from fusionbox.fabric import fb_env
    from fusionbox.fabric.django import stage
    
    fb_env.project_name = 'rjandmakay'
    fb_env.project_abbr = 'rjandmakay'
    fb_env.short_name = 'rjandmakay'
    
    stage = roles('dev')(stage)


.. _Fusionbox: http://www.fusionbox.com
