#!/usr/bin/python
import sys, getopt
import xmlrpclib
'''
host = raw_input('Enter openerp host name : ')
port = raw_input('Enter openerp host port : ')
dbname = raw_input('Enter database name : ')

if dbname == 'metro_production':
    print('Can not perform operation on this database')
    sys.exit(0)

username = raw_input('Enter user name : ')
pwd = raw_input('Enter password : ')
'''
host = 'localhost'
port = '9069'
dbname = 'metro_develop'
username = 'erpadmin'
pwd = 'develop'

#host = '10.1.1.140'
#port = '80'
#dbname = 'metro_production'
#username = 'erpadmin'
#pwd = 'erp123'

#host = '10.1.1.141'
#port = '80'
#dbname = 'metro_0506'
#username = 'erpadmin'
#pwd = 'develop'

sock_common = xmlrpclib.ServerProxy ('http://%s:%s/xmlrpc/common'%(host,port))
uid = sock_common.login(dbname, username, pwd)
sock = xmlrpclib.ServerProxy('http://%s:%s/xmlrpc/object'%(host,port))
#product_code = ['115596-1','115599-1','115600-1']
product_code = ['115829-1',
'115607-1',
'115609-1',
'115995-1',
'115610-1',
'115613-1',
'115653-1',
'115616-1',
'115635-1',
'115987-1',
'115830-1',
'114627-1',
'115996-1',
'113143-1',
'115712-1',
'113137-1',
'113248-1',
'113256-1',
'113260-1',
'113262-1',
'116117-1',
'116119-1',
'115731-1',
'115754-1',
'116120-1',
'116121-1',
'116131-1',
'116017-1',
'116123-1',
'116124-1',
'116154-1',
'116129-1',
'116126-1',
'115753-1',
]
for code in product_code:
    new_uom_categ_id = sock.execute(dbname, uid, pwd, 'product.uom.categ', 'create', {'name':'MSP_%s'%code})
    uom_data = {
        'name':'BaseUnit',
        'category_id':new_uom_categ_id,
        'factor':1,
        'rounding': 0.0001,
#        'uom_type': 'reference',
#        'active': 1,
    }
    sock.execute(dbname, uid, pwd, 'product.uom', 'create', uom_data)
    print 'Created UOM for %s'%code
print 'done...'