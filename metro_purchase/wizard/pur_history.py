# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
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

from openerp import netsvc
import time

from openerp.osv import osv,fields
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.addons.metro_purchase import purchase 

class pur_history_line(osv.osv_memory):
    _name = "pur.history.line"
    _description = 'Product\'s purchasing history line'
    _columns = {
        'wizard_id' : fields.many2one('pur.history', string="Wizard"),
        'order_id': fields.many2one('purchase.order', 'Order Reference'),
        'order_line_id': fields.many2one('purchase.order.line', 'Order Reference'),
        'date_order':fields.date('Order Date'),
        'partner_id':fields.many2one('res.partner', 'Supplier'),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure')),
        'product_uom': fields.many2one('product.uom', 'Product Unit of Measure'),
        'price_unit': fields.float('Unit Price', digits_compute= dp.get_precision('Product Price')),
        'price_subtotal': fields.float('Subtotal', digits_compute= dp.get_precision('Account')),
        'state':fields.selection(purchase.purchase_order_line.STATE_SELECTION, 'Status', readonly=True),
    }
pur_history_line()

class pur_history(osv.osv_memory):
    _name = "pur.history"
    _description = 'Product\'s purchasing history'
    _columns = {
        'product_id': fields.many2one('product.product', 'Product' ,required=True),
        'line_ids' : fields.one2many('pur.history.line', 'wizard_id', 'PO Lines'),
    }

    def default_get(self, cr, uid, fields, context=None):
        """
         To get default values for the object.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param fields: List of fields for which we want default values
         @param context: A standard dictionary
         @return: A dictionary with default values for all field in ``fields``
        """
        result1 = []
        if context is None:
            context = {}
        res = super(pur_history, self).default_get(cr, uid, fields, context=context)
        product_id = context.get('product_id', False) or False
        po_line_id = context.get('po_line_id')
        po_line_obj = self.pool.get('purchase.order.line')
        if not product_id:
            po_line = po_line_obj.browse(cr,uid,po_line_id,context=context)
            product_id = po_line.product_id.id
            
        po_line_ids = po_line_obj.search(cr, uid, [('product_id', '=', product_id),('id','!=',po_line_id),('state','!=','cancel')], context=context)
        po_lines = po_line_obj.browse(cr, uid, po_line_ids, context=context)
                
        for line in po_lines:
            result1.append({'order_id': line.order_id.id, 'order_line_id': line.id, 'date_order':line.order_id.date_order, 
                            'partner_id':line.partner_id.id, 'product_qty': line.product_qty,'product_uom':line.product_uom.id,
                            'price_unit':line.price_unit, 'price_subtotal':line.price_subtotal, 'state':line.state})
        res.update({'product_id':product_id, 'line_ids': result1})
        return res

pur_history()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
