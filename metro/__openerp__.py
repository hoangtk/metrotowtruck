# -*- coding: utf-8 -*-

{
    'name': 'Metro',
    'version': '1.0',
    "sequence": 14,
    'complexity': "easy",
    'description': """
    
        This module contains the common configurations needed by group of 
        Metro Modules.
    
    """,
    'author': 'PY Solutions',
    'website': 'http://www.pysolutions.com',
    'depends': ['base'],
    'init_xml': [],
    'data' : [
       "ir_actions_view.xml",
       "metro_menu.xml",
	   "security/metro.xml",
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    
    #web
    "js": ["static/src/js/metro.js"],
    'qweb' : ["static/src/xml/lang_switch.xml"],
    'css' : ["static/src/css/lang_switch.css",
             "static/src/css/metro.css",],    
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
