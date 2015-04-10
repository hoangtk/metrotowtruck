# -*- coding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 OpenERP SA (<http://www.openerp.com>)
#    Copyright (C) 2011-2013 Serpent Consulting Services Pvt. Ltd. (<http://www.serpentcs.com>).

#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.     
#
##############################################################################

from openerp.osv import fields, osv
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _

class future_shipment(osv.osv):
    '''
    Define one future shipment order, one shipment have multiple product lines
    '''
    _name="future.shipment"
    _columns = {
        'origin_id':fields.many2one('res.partner', 'Origination', required=True,readonly=True, states={'wait':[('readonly',False)]}),
        'dest_id': fields.many2one('res.partner','Destination', required=True,readonly=True, states={'wait':[('readonly',False)]}),
        'state':fields.selection(
                                 [('wait','Waiting'),('shipped','Shipped'),('cancel','Cancelled')],
                                 'State',required=True
                                 ),
        'line_ids' : fields.one2many('future.shipment.line','shipment_id','Products to future shipping',readonly=True, states={'wait':[('readonly',False)]}),
        'real_ship_id':fields.many2one('shipment.shipment','Final Shipment', readonly=True),
        'new_future_ship_id':fields.many2one('future.shipment','New Future Shipment', readonly=True),
        'multi_images': fields.text("Multi Images"),
        'create_uid':  fields.many2one('res.users', 'Creator', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
    }
    
    _defaults={'state':'wait'}
    
    def unlink(self, cr, uid, ids, context=None):
        for order in self.read(cr, uid, ids, ['state'], context=context):
            if order['state'] == 'shipped':
                raise osv.except_osv(_('Error'), 'Future shipment was shipped, can not be delete!')
        return super(future_shipment,self).unlink(cr, uid, ids, context=context)
    
    def action_cancel(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'cancel', 'real_ship_id':None, 'new_future_ship_id':None}, context=context)
    
future_shipment()

class future_shipment_line(osv.osv):
    '''
    doc
    Model: future.shipment.line
    '''
    _name="future.shipment.line"
    _columns = {
        'shipment_id':fields.many2one('future.shipment','Future Shipment'),
        'product_id':fields.many2one('product.product', 'Product', required=False),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure'),required=True),
        'notes':fields.text('Description'),
        'write_uid':  fields.many2one('res.users', 'Creator', readonly=True),
        'write_date': fields.datetime('Creation Date', readonly=True, select=True),
        } 
future_shipment_line()
