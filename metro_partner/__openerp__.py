{
    'name': 'Metro Partner',
    'version': '1.0',
    'category': 'Metro',
    'description': """
    
        Metro Product Extension:  
        
        Updates the Product module to create automatic part numbers, adds a Chinese name field and a details tab.
        
        (Ported to OpenERP v 7.0 by PY Solutions.)
        
        07/09/2013 - Added Inquiry Tab - By PY Solutions
        
        """,
        
        
    'author': 'PY Solutions',
    'maintainer': 'PY Solutions',
    'website': 'http://www.pysolutions.com',
    'depends': ["metro", "base"],
    'init_xml': [],
    'update_xml': [
	'security/ir.model.access.csv',
	'partner_view.xml',
    ],
    'demo_xml': [],
    'test': [],
    'installable': True,
    'auto_install': False,
    'active': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
