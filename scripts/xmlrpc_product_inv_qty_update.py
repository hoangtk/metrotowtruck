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
#host = 'localhost'
#port = '9069'
#dbname = 'metro_dev_prod_0328'
#username = 'erpadmin'
#pwd = 'develop'

#host = '10.1.1.141'
#port = '80'
#dbname = 'metro_prod_0328'
#username = 'erpadmin'
#pwd = 'develop'

host = '10.1.1.140'
port = '80'
dbname = 'metro_production'
username = 'erpadmin'
pwd = 'erp123'

sock_common = xmlrpclib.ServerProxy ('http://%s:%s/xmlrpc/common'%(host,port))
uid = sock_common.login(dbname, username, pwd)
sock = xmlrpclib.ServerProxy('http://%s:%s/xmlrpc/object'%(host,port))
'''
FIFO module will report error when there no stock in quantity(move in with stock_move.qty_remaining)
This script is to update the stock_move.qty_remaining for the FIFO module having move to match when do stocking out.
My idea is to get the product's qty_available, and then allocate this quantity to the stock_move.qty_remaining of this product, 
the new stock_move will be allocate first, once the qty_available is finished allocated, then this product is finished.
And it will also update the stock_move.price_unit from product.standard_price if move price is empty
'''
ids = sock.execute(dbname, uid, pwd, 'product.product', 'search', [('active','=',True)])
#ids = [1023]
for id in ids:
    #get the product inventory quantity
    prod_ids = sock.execute(dbname, uid, pwd, 'product.product', 'search', [])
    for prod_id in prod_ids:
        qtys = sock.execute(dbname, uid, pwd, 'product.product', 'rpc_product_available', [prod_id], ['qty_available','virtual_available','incoming_qty','outgoing_qty'])
        '''
        qtys['%s'%prod_id], data is as below:
        vals = {'qty_available':qty['qty_available'],'virtual_available':qty['virtual_available'],
                'incoming_qty':qty['incoming_qty'],'outgoing_qty':qty['outgoing_qty']}
        '''
        #failed to update ,since the qty columns are function field, and having store restriction
#        sock.execute(dbname, uid, pwd, 'product.product', 'write', [prod_id], qtys['%s'%prod_id])
#        print 'Updated product:%s'%prod_id
        #print the sql, then execute in psql
        qty = qtys['%s'%prod_id]
        if qty['qty_available'] == 0.0 and qty['virtual_available'] == 0.0 and qty['incoming_qty'] == 0.0 and qty['outgoing_qty'] == 0.0:
#            print qty
            continue
        print "insert into temp_prod_inv_0411 select %s,%s,%s,%s,%s;"%(prod_id,qty['qty_available'],qty['virtual_available'],qty['incoming_qty'],qty['outgoing_qty'])
        
print 'done...'