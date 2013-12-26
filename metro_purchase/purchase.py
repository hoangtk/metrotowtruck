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
from openerp.addons.purchase import purchase
class purchase_order(osv.osv):  
    _inherit = "purchase.order"
    def __init__(self, pool, cr):
        super(purchase_order,self).__init__(pool,cr)
    _track = {
        'state': {
            'purchase.mt_rfq_confirmed': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'confirmed',
            'purchase.mt_rfq_approved': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'approved',
            'metro_purchase.mt_rfq_rejected': lambda self, cr, uid, obj, ctx=None: obj['state'] == 'rejected',
        },
    }

    STATE_SELECTION = [
        ('draft', 'Draft PO'),
        ('sent', 'RFQ Sent'),
        ('confirmed', 'Waiting Approval'),
        ('rejected', 'Rejected'),
        ('approved', 'Purchase Order'),
        ('except_picking', 'Shipping Exception'),
        ('except_invoice', 'Invoice Exception'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ] 

    def _pay_info(self, cr, uid, ids, field_names=None, arg=False, context=None):
        """ Finds the payment mount and set the paid flag
        @return: Dictionary of values
        """
        if not field_names:
            field_names = []
        if context is None:
            context = {}
        res = {}
        for id in ids:
            res[id] = {}.fromkeys(field_names, 0.0)

        for purchase in self.browse(cr, uid, ids, context=context):
            tot = 0.0
            paid = 0.0
            inv_paid = 0.0
            for invoice in purchase.invoice_ids:
                if invoice.state not in ('draft','cancel'):
                    inv_paid += (invoice.amount_total - invoice.residual)
            for f in field_names:
                if f == 'amount_paid':
                    res[purchase.id][f] = inv_paid
                if f == 'paid_done':
                    res[purchase.id][f] = (purchase.amount_total == inv_paid)
        return res
        
    _columns = {
        'warehouse_id': fields.many2one('stock.warehouse', 'Destination Warehouse',states={'confirmed':[('readonly',True)],'approved':[('readonly',True)],'done':[('readonly',True)]}),                
        'order_line': fields.one2many('purchase.order.line', 'order_id', 'Order Lines', states={'confirmed':[('readonly',True)],'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'state': fields.selection(STATE_SELECTION, 'Status', readonly=True, help="The status of the purchase order or the quotation request. A quotation is a purchase order in a 'Draft' status. Then the order has to be confirmed by the user, the status switch to 'Confirmed'. Then the supplier must confirm the order to change the status to 'Approved'. When the purchase order is paid and received, the status becomes 'Done'. If a cancel action occurs in the invoice or in the reception of goods, the status becomes in exception.", select=True),
        'reject_msg': fields.text('Rejection Message', track_visibility='onchange'),
        'create_uid':  fields.many2one('res.users', 'Creator', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'inform_type': fields.char('Informer Type', size=10, readonly=True, select=True),
        'is_sent_supplier': fields.boolean('Sent to Supplier', select=True),
        'taxes_id': fields.many2many('account.tax', 'po_tax', 'po_id', 'tax_id', 'Taxes', states={'confirmed':[('readonly',True)],'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'invoiced': fields.function(purchase.purchase_order._invoiced, string='Invoice Received', type='boolean', help="It indicates that an invoice is open"),
        'amount_paid': fields.function(_pay_info, multi='pay_info', string='Paid Amount', type='float', readonly=True),
        'paid_done': fields.function(_pay_info, multi='pay_info', string='Paid Done', type='boolean', readonly=True),
                
    }
    _defaults = {
        'is_sent_supplier': False,
    }    
    def new_po(self, cr, uid, pos, context=None):
        """
        Create New RFQ for Supplier
        """
        if context is None:
            context = {}
        purchase_order = self.pool.get('purchase.order')
        purchase_order_line = self.pool.get('purchase.order.line')
        res_partner = self.pool.get('res.partner')
        fiscal_position = self.pool.get('account.fiscal.position')
        warehouse_obj = self.pool.get('stock.warehouse')
        product_obj = self.pool.get('product.product')
        pricelist_obj = self.pool.get('product.pricelist')
        for po_data in pos:
            assert po_data['partner_id'], 'Supplier should be specified'
            assert po_data['warehouse_id'], 'Warehouse should be specified'            
            supplier = res_partner.browse(cr, uid, po_data['partner_id'], context=context)
            warehouse = warehouse_obj.browse(cr, uid, po_data['warehouse_id'], context=context)
            
            if not po_data.has_key('location_id'):
                po_data['location_id'] = warehouse.lot_input_id.id
            if not po_data.has_key('pricelist_id'):
                supplier_pricelist = supplier.property_product_pricelist_purchase or False
                po_data['pricelist_id'] = supplier_pricelist.id
            if not po_data.has_key('fiscal_position'):
                po_data['fiscal_position'] = supplier.property_account_position and supplier.property_account_position.id or False
            if not po_data.has_key('company_id'):
                company_id = self.pool.get('res.company')._company_default_get(cr, uid, 'purchase.order', context=context)
                po_data['company_id'] = company_id
            new_po_id = purchase_order.create(cr, uid, po_data)
            #assign the new po id to po data, then the caller call get the new po's info
            po_data['new_po_id'] = new_po_id
            pricelist_id = po_data['pricelist_id'];
            for line in po_data['lines']:
                product = product_obj.browse(cr,uid, line['product_id'], context=context)
                #taxes
                taxes_ids = product.supplier_taxes_id
                taxes = fiscal_position.map_tax(cr, uid, supplier.property_account_position, taxes_ids)
                taxes_id = (6, 0, taxes)
                
                line.update({'order_id':new_po_id,'name':product.partner_ref,'taxes_id':taxes_id})
                #unit price
                if not line.has_key('price_unit'):
                    price_unit = seller_price = pricelist_obj.price_get(cr, uid, [pricelist_id], product.id, line['product_qty'], False, {'uom': line['product_uom']})[pricelist_id]
                    line['price_unit'] = price_unit
                new_po_line_id = purchase_order_line.create(cr,uid,line,context=context)
                line['new_po_line_id'] = new_po_line_id
                
        return pos
    def _get_lines(self,cr,uid,ids,states=None,context=None):
        todo = []
        for po in self.browse(cr, uid, ids, context=context):
            if not po.order_line:
                continue
            for line in po.order_line:
                if states == None or line.state in states:
                    todo.append(line.id)
        return todo
        
    def wkf_confirm_order(self, cr, uid, ids, context=None):
        todo = []
        for po in self.browse(cr, uid, ids, context=context):
            if not po.order_line:
                raise osv.except_osv(_('Error!'),_('You cannot confirm a purchase order without any purchase order line.'))
            for line in po.order_line:
                if line.state=='draft' or line.state=='rejected':
                    todo.append(line.id)        
        self.pool.get('purchase.order.line').write(cr, uid, todo, {'state':'confirmed'},context)
        for id in ids:
            self.write(cr, uid, [id], {'state' : 'confirmed', 'validator' : uid, 'inform_type':'1'})
        return True    
    
    def wkf_approve_order(self, cr, uid, ids, context=None):                    
#        lines = self._get_lines(cr,uid,ids,['confirmed','rejected'],context=context)
        lines = []
        for po in self.browse(cr, uid, ids, context=context):
            for line in po.order_line:
                if line.state=='rejected':
                    raise osv.except_osv(_('Error!'),_('You cannot approve a purchase order with rejected purchase order lines.'))
                if line.state=='confirmed':
                    lines.append(line.id)
        self.pool.get('purchase.order.line').write(cr, uid, lines, {'state':'approved'},context)
        self.write(cr, uid, ids, {'state': 'approved', 'date_approve': fields.date.context_today(self,cr,uid,context=context), 'inform_type':'3'})
        return True
    
    def wkf_done(self, cr, uid, ids, context=None):  
        lines = self._get_lines(cr,uid,ids,['approved'],context=context)
        self.pool.get('purchase.order.line').write(cr, uid, lines, {'state':'done'},context)
        self.write(cr, uid, ids, {'state': 'done'})
        
    def action_reject(self, cr, uid, ids, message, context=None):
#        lines = self._get_lines(cr,uid,ids,['confirmed'],context=context)
        lines = []
        for po in self.browse(cr, uid, ids, context=context):
            for line in po.order_line:
                if line.state=='approved':
                    raise osv.except_osv(_('Error!'),_('You cannot reject a purchase order with approved purchase order lines.'))
                if line.state=='confirmed':
                    lines.append(line.id)
        self.pool.get('purchase.order.line').write(cr, uid, lines, {'state':'rejected'},context)         
        wf_service = netsvc.LocalService("workflow")
        self.write(cr,uid,ids,{'state':'rejected','reject_msg':message, 'inform_type':'2'})

        for (id, name) in self.name_get(cr, uid, ids):
            wf_service.trg_validate(uid, 'purchase.order', id, 'purchase_reject', cr)
        return True
    def action_cancel(self, cr, uid, ids, context=None):
        resu = super(purchase_order,self).action_cancel(cr,uid,ids,context)
        lines = self._get_lines(cr,uid,ids,context=context)
        self.pool.get('purchase.order.line').write(cr, uid, lines, {'state': 'cancel'},context)
        return resu
    def action_cancel_draft(self, cr, uid, ids, context=None):
        resu = super(purchase_order,self).action_cancel_draft(cr,uid,ids,context)
        lines = self._get_lines(cr,uid,ids,context=context)
        self.pool.get('purchase.order.line').write(cr, uid, lines, {'state': 'draft'},context)
        return resu
            
        
class purchase_order_line(osv.osv):  
    _name = "purchase.order.line"
    _inherit = 'purchase.order.line' 

    STATE_SELECTION = [
        ('draft', 'Draft'),
        ('confirmed', 'Waiting Approval'),
        ('rejected', 'Rejected'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ]

    _columns = {
        'po_notes': fields.related('order_id','notes',string='Terms and Conditions',readonly=True,type="text"),
        'payment_term_id': fields.related('order_id','payment_term_id',string='Payment Term',readonly=True,type="many2one", relation="account.payment.term"),
        'state': fields.selection(STATE_SELECTION, 'Status', readonly=True),
        'reject_msg': fields.text('Rejection Message', track_visibility='onchange'),
        'create_uid':  fields.many2one('res.users', 'Creator', select=True, readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'image_medium': fields.related('product_id','image_medium',type='binary',String="Medium-sized image"),
        'change_log': fields.one2many('change.log.po.line','res_id','Quantity Changing'),
        'inform_type': fields.char('Informer Type', size=10, readonly=True, select=True),
    }  
    _order = "order_id desc"
    def _is_po_update(self,cr,uid,po,state,context=None):
        po_update = True
        for line in po.order_line:
            if line.state!=state:
                po_update = False
                break
        return po_update

    def action_confirm(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'confirmed'}, context=context)
        self.write(cr, uid, ids, {'inform_type': '1'}, context=context)
        wf_service = netsvc.LocalService("workflow")
        #update po's state
        po_line_obj = self.browse(cr,uid,ids[0],context=context)
        po = po_line_obj.order_id
        is_po_update = self._is_po_update(cr,uid,po,'confirmed',context=context)
        if is_po_update:
            wf_service.trg_validate(uid, 'purchase.order', po.id, 'purchase_confirm', cr)            
            
        return True 
            
    def action_approve(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'approved'}, context=context)
        wf_service = netsvc.LocalService("workflow")
        #update po's state
        po_line_obj = self.browse(cr,uid,ids[0],context=context)
        po = po_line_obj.order_id
        is_po_update = self._is_po_update(cr,uid,po,'approved',context=context)
        if is_po_update:
            wf_service.trg_validate(uid, 'purchase.order', po.id, 'purchase_approve', cr)
        return True   
    
    def action_reject(self, cr, uid, ids, message, context=None):
        self.write(cr, uid, ids, {'state': 'rejected','reject_msg':message}, context=context)
        self.write(cr, uid, ids, {'inform_type': '2'}, context=context)
        wf_service = netsvc.LocalService("workflow")
        #update po's state
        po_line_obj = self.browse(cr,uid,ids[0],context=context)
        po = po_line_obj.order_id
        is_po_update = self._is_po_update(cr,uid,po,'rejected',context=context)
        if is_po_update:
            self.pool.get("purchase.order").action_reject(cr,uid,[po.id],"All lines are rejected",context=context)
        return True     
    
    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        id = ids[0]
        po_line = self.browse(cr,uid,id,context=context)
        value_old = po_line.product_qty
        resu = super(purchase_order_line,self).write(cr, uid, ids, vals, context=context)
        #only when orders confirmed, then record the quantity changing log
        if po_line.state != 'draft':
            field_name = 'product_qty';
            if vals.has_key(field_name):
                log_obj = self.pool.get('change.log.po.line')
                log_vals = {'res_id':id,'filed_name':field_name,'value_old':value_old,'value_new':vals[field_name]}
                log_obj.create(cr,uid,log_vals,context=context)
        return resu;
    def unlink(self, cr, uid, ids, context=None):
        #only the draft,canceled can be deleted
        lines = self.browse(cr,uid,ids,context=context)
        for line in lines:
            if line.state != 'draft' and line.state != 'cancel' and line.state != 'rejected':
                raise osv.except_osv(_('Error'), _('Only the lines with draft, canceled and rejected can be deleted!'))            
        return super(purchase_order_line,self).unlink(cr,uid,ids,context=context)
    
    def onchange_product_id(self, cr, uid, ids, pricelist_id, product_id, qty, uom_id,
            partner_id, date_order=False, fiscal_position_id=False, date_planned=False,
            name=False, price_unit=False, context=None):
        """
        onchange handler of product_id.
        """
        res = super(purchase_order_line,self).onchange_product_id(cr, uid, ids, pricelist_id, product_id, qty, uom_id,
                                partner_id, date_order, fiscal_position_id, date_planned,name, price_unit, context)
        if not product_id or context is None or res['value'].get('taxes_id') or not context.get('po_taxes_id')[0][2]: 
            return res

        # - determine taxes_id when purchase_header has taxes_id and produt has not own taxes setting
        account_fiscal_position = self.pool.get('account.fiscal.position')
        account_tax = self.pool.get('account.tax')
        taxes = account_tax.browse(cr, uid, context['po_taxes_id'][0][2])
        fpos = fiscal_position_id and account_fiscal_position.browse(cr, uid, fiscal_position_id, context=context) or False
        taxes_ids = account_fiscal_position.map_tax(cr, uid, fpos, taxes)
        res['value'].update({'taxes_id': taxes_ids})

        return res
    
class product_template(osv.Model):
    _inherit = 'product.template'
    _columns = {
        'name': fields.char('Name', size=128, required=True, translate=False, select=True),
    }