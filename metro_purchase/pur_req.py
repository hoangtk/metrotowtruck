# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
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
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
from openerp import netsvc

from openerp.osv import fields,osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

class pur_req(osv.osv):
    _name = "pur.req"
    _description="Purchase Requisition"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _columns = {
        'name': fields.char('Requisition#', size=32,required=True),
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse',required=True,readonly=True, states={'draft':[('readonly',False)]}),    
        'user_id': fields.many2one('res.users', 'Requester',required=True,readonly=True, states={'draft':[('readonly',False)]}),        
        'date_request': fields.datetime('Requisition Date',required=True,readonly=True, states={'draft':[('readonly',False)]}),
        'remark': fields.text('Remark'),
        'company_id': fields.many2one('res.company', 'Company', required=True,readonly=True, states={'draft':[('readonly',False)]}),
        'line_ids' : fields.one2many('pur.req.line','req_id','Products to Purchase',readonly=True, states={'draft':[('readonly',False)]}),
        'state': fields.selection([('draft','New'),('confirmed','Confirmed'),('in_purchase','In Purchasing'),('done','Purchase Done'),('cancel','Cancelled')],
            'Status', track_visibility='onchange', required=True),
        'po_ids' : fields.one2many('purchase.order','req_id','Related PO'),            
    }
    _defaults = {
        'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'pur.req'),
#        'warehouse_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).id ,
        'user_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).id ,
        'date_request': lambda *args: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'pur.req', context=c),
        'state': 'draft',
    }

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'state':'draft',
            'purchase_ids':[],
            'name': self.pool.get('ir.sequence').get(cr, uid, 'pur.req'),
        })
        return super(pur_req, self).copy(cr, uid, id, default, context)
    
    def wkf_confirm_req(self, cr, uid, ids, context=None):
        for req in self.browse(cr, uid, ids, context=context):
            if not req.line_ids:
                raise osv.except_osv(_('Error!'),_('You cannot confirm a purchase requisition order without any product line.'))
            
        self.write(cr,uid,ids,{'state':'confirmed'})
        return True

    def wkf_cancel_req(self, cr, uid, ids, context=None):
        wf_service = netsvc.LocalService("workflow")
        for req in self.browse(cr, uid, ids, context=context):
            for po in req.po_ids:
                if po.state not in('cancel'):
                    raise osv.except_osv(
                        _('Unable to cancel this purchase requisition.'),
                        _('First cancel all purchase orders related to this purchase order.'))
#            for po in req.po_ids:
#                wf_service.trg_validate(uid, 'purchase.order', po.id, 'purchase_cancel', cr)
    
        self.write(cr,uid,ids,{'state':'cancel'})
        return True  
      
    def unlink(self, cr, uid, ids, context=None):
        pur_reqs = self.read(cr, uid, ids, ['state'], context=context)
        unlink_ids = []
        for s in pur_reqs:
            if s['state'] in ['draft','cancel']:
                unlink_ids.append(s['id'])
            else:
                raise osv.except_osv(_('Invalid Action!'), _('In order to delete a purchase requisition, you must cancel it first.'))

        # automatically sending subflow.delete upon deletion
        wf_service = netsvc.LocalService("workflow")
        for id in unlink_ids:
            wf_service.trg_validate(uid, 'pur.req', id, 'pur_req_cancel', cr)

        return super(pur_req, self).unlink(cr, uid, unlink_ids, context=context)    

    def make_purchase_order(self, cr, uid, ids, partner_id, context=None):
        """
        Create New RFQ for Supplier
        """
        if context is None:
            context = {}
        assert partner_id, 'Supplier should be specified'
        purchase_order = self.pool.get('purchase.order')
        purchase_order_line = self.pool.get('purchase.order.line')
        res_partner = self.pool.get('res.partner')
        fiscal_position = self.pool.get('account.fiscal.position')
        supplier = res_partner.browse(cr, uid, partner_id, context=context)
        supplier_pricelist = supplier.property_product_pricelist_purchase or False
        res = {}
        for requisition in self.browse(cr, uid, ids, context=context):
            if supplier.id in filter(lambda x: x, [rfq.state <> 'cancel' and rfq.partner_id.id or None for rfq in requisition.purchase_ids]):
                 raise osv.except_osv(_('Warning!'), _('You have already one %s purchase order for this partner, you must cancel this purchase order to create a new quotation.') % rfq.state)
            location_id = requisition.warehouse_id.lot_input_id.id
            purchase_id = purchase_order.create(cr, uid, {
                        'origin': requisition.name,
                        'partner_id': supplier.id,
                        'pricelist_id': supplier_pricelist.id,
                        'location_id': location_id,
                        'company_id': requisition.company_id.id,
                        'fiscal_position': supplier.property_account_position and supplier.property_account_position.id or False,
                        'requisition_id':requisition.id,
                        'notes':requisition.description,
                        'warehouse_id':requisition.warehouse_id.id ,
            })
            res[requisition.id] = purchase_id
            for line in requisition.line_ids:
                product = line.product_id
                seller_price, qty, default_uom_po_id, date_planned = self._seller_details(cr, uid, line, supplier, context=context)
                taxes_ids = product.supplier_taxes_id
                taxes = fiscal_position.map_tax(cr, uid, supplier.property_account_position, taxes_ids)
                purchase_order_line.create(cr, uid, {
                    'order_id': purchase_id,
                    'name': product.partner_ref,
                    'product_qty': qty,
                    'product_id': product.id,
                    'product_uom': default_uom_po_id,
                    'price_unit': seller_price,
                    'date_planned': date_planned,
                    'taxes_id': [(6, 0, taxes)],
                }, context=context)
                
        return res    
pur_req()    

class pur_req_line(osv.osv):

    _name = "pur.req.line"
    _description="Purchase Requisition Line"
    _rec_name = 'product_id'

    def _generated_po(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for req_line in self.browse(cursor, user, ids, context=context):
            generated_po = False
            if req_line.po_lines_ids:
                for po_line in req_line.po_lines_ids:
                    if po_line.state != 'cancel':
                        generated_po = True
                        break
                invoiced = True
            res[req_line.id] = generated_po
        return res
    
    _columns = {
        'req_id' : fields.many2one('pur.req','Purchase Requisition', ondelete='cascade'),
        'product_id': fields.many2one('product.product', 'Product' ,required=True),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure'),required=True),
        'product_uom_id': fields.many2one('product.uom', 'Product Unit of Measure',required=True),
        'date_required': fields.date('Date Required'),
        'inv_qty': fields.float('Inventory'),
        'req_reason': fields.char('Purchase reason and use',size=64),
        'company_id': fields.related('req_id','company_id',type='many2one',relation='res.company',String='Company',store=True,readonly=True),
        'po_lines_ids' : fields.one2many('purchase.order.line','req_line_id','Purchase Order Lines'),
        'generated_po': fields.function(_generated_po, string='PO Generated', type='boolean', help="It indicates that this products has PO generated"),
    }
    
    
    def onchange_product_id(self, cr, uid, ids, product_id, context=None):
        """ Changes UoM,inv_qty if product_id changes.
        @param product_id: Changed product_id
        @return:  Dictionary of changed values
        """
        value = {'product_uom_id': '', 'inv_qty': ''}
        if product_id:
            prod = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            value = {'product_uom_id': prod.uom_id.id,'product_qty':1.0,'inv_qty':prod.qty_available}
        return {'value': value}

    _defaults = {
        'product_qty': lambda *a: 1.0,
    }
pur_req_line()

class purchase_order(osv.osv):
    _inherit = "purchase.order"
    _columns = {
        'req_id' : fields.many2one('pur.req','Purchase Requisition')
    }

purchase_order()

class purchase_order_line(osv.osv):    
    _inherit = "purchase.order.line"
    _columns = {
                'req_line_id':fields.many2one('pur.req.line', 'Purchase Requisition')}   
    
purchase_order_line()
    
#class product_product(osv.osv):
#    _inherit = 'product.product'
#
#    _columns = {
#        'pur_req': fields.boolean('Purchase Requisition', help="Check this box to generates purchase requisition instead of generating requests for quotation from procurement.")
#    }
#    _defaults = {
#        'pur_req': False
#    }
#
#product_product()
#
#class procurement_order(osv.osv):
#
#    _inherit = 'procurement.order'
#    _columns = {
#        'requisition_id' : fields.many2one('purchase.requisition','Latest Requisition')
#    }
#    def make_po(self, cr, uid, ids, context=None):
#        res = {}
#        requisition_obj = self.pool.get('purchase.requisition')
#        warehouse_obj = self.pool.get('stock.warehouse')
#        procurement = self.browse(cr, uid, ids, context=context)[0]
#        if procurement.product_id.pur_req:
#             warehouse_id = warehouse_obj.search(cr, uid, [('company_id', '=', procurement.company_id.id or company.id)], context=context)
#             res[procurement.id] = requisition_obj.create(cr, uid, 
#                   {
#                    'origin': procurement.origin,
#                    'date_end': procurement.date_planned,
#                    'warehouse_id':warehouse_id and warehouse_id[0] or False,
#                    'company_id':procurement.company_id.id,
#                    'line_ids': [(0,0,{
#                        'product_id': procurement.product_id.id,
#                        'product_uom_id': procurement.product_uom.id,
#                        'product_qty': procurement.product_qty
#
#                   })],
#                })
#             self.write(cr,uid,[procurement.id],{'state': 'running','requisition_id': res[procurement.id]},context=context)
#        else:
#            res = super(procurement_order, self).make_po(cr, uid, ids, context=context)
#        return res

#procurement_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
