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
from dateutil.relativedelta import relativedelta
import time
import datetime
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
        ('wait_receipt', 'Waitting Receipt'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ] 
    
    def _invoiced_rate(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for purchase in self.browse(cursor, user, ids, context=context):
            tot = 0.0
            for invoice in purchase.invoice_ids:
                if invoice.state not in ('draft','cancel'):
                    tot += invoice.amount_total
            if purchase.amount_total:
                res[purchase.id] = tot * 100.0 / purchase.amount_total
            else:
                res[purchase.id] = 0.0
        return res    

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
        'invoiced_rate': fields.function(_invoiced_rate, string='Invoiced', type='float'),
        'amount_paid': fields.function(_pay_info, multi='pay_info', string='Paid Amount', type='float', readonly=True),
        'paid_done': fields.function(_pay_info, multi='pay_info', string='Paid Done', type='boolean', readonly=True),
        'order_line': fields.one2many('purchase.order.line', 'order_id', 'Order Lines', readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'has_freight': fields.boolean('Has Freight', states={'confirmed':[('readonly',True)],'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'amount_freight': fields.float('Freight', states={'confirmed':[('readonly',True)],'approved':[('readonly',True)],'done':[('readonly',True)]}),
        'receipt_number': fields.char('Receipt Number', size=64, help="The reference of this invoice as provided by the partner."),
        'comments': fields.text('Comments'),        
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
            #add the default value of notes
            po_data.update(purchase_order.default_get(cr,uid,['notes'],context=context))
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
                
                line.update({'order_id':new_po_id,'taxes_id':taxes_id})
                
                #set the line description
                name = product.name
                if product.description_purchase:
                    name += '\n' + product.description_purchase
                if line.get('name'):
                    name += '\n' + line.get('name')      
                line.update({'name': name})    
                       
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
        #check the receipt number field
        order = self.browse(cr,uid,ids[0],context=context)
        if order.amount_tax <= 0 or (order.receipt_number and order.receipt_number != ''):
            #only when get the receipt, then upadte status to 'done'
            #update lines to 'done'  
            lines = self._get_lines(cr,uid,ids,['approved'],context=context)
            self.pool.get('purchase.order.line').write(cr, uid, lines, {'state':'done'},context)
            self.write(cr, uid, ids, {'state': 'done'})
        else:
            #update status to 'waiting receipt'
            self.write(cr, uid, ids, {'state': 'wait_receipt'})       
            
    def write(self, cr, user, ids, vals, context=None):
        if vals.get('receipt_number') and vals.get('receipt_number') != '':
            #if the state is 'wait_receipt' then update the state to done when user entered the receipt_number
            order = self.browse(cr,user,ids[0],context=context)
            if order.state == 'wait_receipt':
                vals.update({'state':'done'})
        #if user changed the expected plan date, then update the associated pickings
        if vals.get('minimum_planned_date') and vals.get('minimum_planned_date') != '':
            order = self.browse(cr,user,ids[0],context=context)
            if order.picking_ids:
                pick_ids = []
                for pick in order.picking_ids:
                    if pick.state != 'cancel' and pick.state !='done':
                        pick_ids.append(pick.id)
                self.pool.get('stock.picking.in').write(cr,user,pick_ids,{'min_date':vals.get('minimum_planned_date')})
            
            
        return super(purchase_order,self).write(cr,user,ids,vals,context=context)      
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'receipt_number':None,
        })
        return super(purchase_order, self).copy(cr, uid, id, default, context)        
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
    
    def _get_inv_pay_acc_id(self,cr,uid,order):
        property_obj = self.pool.get('ir.property')
        pay_acc = property_obj.get(cr, uid, 'property_account_payable', 'res.partner', 
                                      res_id = 'res.partner,%d'%order.partner_id.id, context = {'force_company':order.company_id.id})
        if not pay_acc:
            pay_acc = property_obj.get(cr, uid, 'property_account_payable', 'res.partner', context = {'force_company':order.company_id.id})
        if not pay_acc:
            raise osv.except_osv(_('Error!'), 
                _('Define account payable for this company: "%s" (id:%d).') % (order.company_id.name, order.company_id.id))
        return pay_acc.id
                            
    def _get_inv_line_exp_acc_id(self,cr,uid,order,po_line):  
        property_obj = self.pool.get('ir.property')
        acc = None
        if po_line.product_id:
            acc = property_obj.get(cr, uid, 'property_account_expense', 'product.template', 
                              res_id = 'product.template,%d'%po_line.product_id.id, context = {'force_company':order.company_id.id})
            if not acc:
                acc = property_obj.get(cr, uid, 'property_account_expense_categ', 'product.category', 
                                  res_id = 'product.category,%d'%po_line.product_id.categ_id.id, context = {'force_company':order.company_id.id})
        if not acc:
            acc = property_obj.get(cr, uid, 'property_account_expense', 'product.template', 
                              context = {'force_company':order.company_id.id})                                
        if not acc:
            acc = property_obj.get(cr, uid, 'property_account_expense_categ', 'product.category', 
                                   context = {'force_company':order.company_id.id})
        if not acc:
                raise osv.except_osv(_('Error!'),
                        _('Define purchase journal for this company: "%s" (id:%d).') % (order.company_id.name, order.company_id.id))
        return acc.id
                                                        
    def action_invoice_create(self, cr, uid, ids, context=None):
        """Generates invoice for given ids of purchase orders and links that invoice ID to purchase order.
        :param ids: list of ids of purchase orders.
        :return: ID of created invoice.
        :rtype: int
        """
        res = False

        journal_obj = self.pool.get('account.journal')
        inv_obj = self.pool.get('account.invoice')
        inv_line_obj = self.pool.get('account.invoice.line')
        fiscal_obj = self.pool.get('account.fiscal.position')

        for order in self.browse(cr, uid, ids, context=context):
            pay_acc_id = self._get_inv_pay_acc_id(cr,uid,order)                
            journal_ids = journal_obj.search(cr, uid, [('type', '=','purchase'),('company_id', '=', order.company_id.id)], limit=1)
            if not journal_ids:
                raise osv.except_osv(_('Error!'),
                    _('Define purchase journal for this company: "%s" (id:%d).') % (order.company_id.name, order.company_id.id))

            # generate invoice line correspond to PO line and link that to created invoice (inv_id) and PO line
            inv_lines = []
            for po_line in order.order_line:
                acc_id = self._get_inv_line_exp_acc_id(cr,uid,order,po_line)
                fpos = order.fiscal_position or False
                acc_id = fiscal_obj.map_account(cr, uid, fpos, acc_id)

                inv_line_data = self._prepare_inv_line(cr, uid, acc_id, po_line, context=context)
                inv_line_id = inv_line_obj.create(cr, uid, inv_line_data, context=context)
                inv_lines.append(inv_line_id)

                po_line.write({'invoiced':True, 'invoice_lines': [(4, inv_line_id)]}, context=context)

            # get invoice data and create invoice
            inv_data = {
                'name': order.partner_ref or order.name,
                'reference': order.partner_ref or order.name,
                'account_id': pay_acc_id,
                'type': 'in_invoice',
                'partner_id': order.partner_id.id,
                'currency_id': order.pricelist_id.currency_id.id,
                'journal_id': len(journal_ids) and journal_ids[0] or False,
                'invoice_line': [(6, 0, inv_lines)],
                'origin': order.name,
                'fiscal_position': order.fiscal_position.id or False,
                'payment_term': order.payment_term_id.id or False,
                'company_id': order.company_id.id,
            }
            inv_id = inv_obj.create(cr, uid, inv_data, context=context)

            # compute the invoice
            inv_obj.button_compute(cr, uid, [inv_id], context=context, set_total=True)

            # Link this new invoice to related purchase order
            order.write({'invoice_ids': [(4, inv_id)]}, context=context)
            res = inv_id
        return res    
    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #deal the 'date' datetime field query
        new_args = deal_args(self,args)    
        return super(purchase_order,self).search(cr, user, new_args, offset, limit, order, context, count)  
        
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
    def _calc_seller(self, cr, uid, ids, fields, arg, context=None):
        result = {}
        for product in self.browse(cr, uid, ids, context=context):
            main_supplier = self._get_main_product_supplier(cr, uid, product, context=context)
            result[product.id] = {
                'seller_info_id': main_supplier and main_supplier.id or False,
                'seller_delay': main_supplier.delay if main_supplier else 1,
                'seller_qty': main_supplier and main_supplier.qty or 0.0,
                'seller_id': main_supplier and main_supplier.name.id or False
            }
        return result
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
        'has_freight': fields.related('order_id','has_freight',string='Has Freight', type="boolean", readonly=True),
        'amount_freight': fields.related('order_id','amount_freight',string='Freight', type='float', readonly=True),
#        'prod_name_supplier': fields.char('Supplier Product Name', size=128, required=True),
#        'product_code': fields.related('product_id', 'product_code',type='char', string='Supplier Product Code'),
#        'delay' : fields.related('product_id', required=True),
#        
#        
#        'seller_info_id': fields.function(_calc_seller, type='many2one', relation="product.supplierinfo", string="Supplier Info", multi="seller_info"),
#        'seller_delay': fields.function(_calc_seller, type='integer', string='Supplier Lead Time', multi="seller_info", help="This is the average delay in days between the purchase order confirmation and the reception of goods for this product and for the default supplier. It is used by the scheduler to order requests based on reordering delays."),
#        'seller_qty': fields.function(_calc_seller, type='float', string='Supplier Quantity', multi="seller_info", help="This is minimum quantity to purchase from Main Supplier."),
#        'seller_id': fields.function(_calc_seller, type='many2one', relation="res.partner", string='Main Supplier', help="Main Supplier who has highest priority in Supplier List.", multi="seller_info"),
#        
#        'min_date': fields.function(stock_picking_super.get_min_max_date, fnct_inv=_set_minimum_date, multi="min_max_date",
#                 store=True, type='datetime', string='Scheduled Time', select=1, help="Scheduled time for the shipment to be processed"), 
#        'max_date': fields.function(stock_picking_super.get_min_max_date, fnct_inv=_set_maximum_date, multi="min_max_date",
#                 store=True, type='datetime', string='Max. Expected Date', select=2),     
#                        
                
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

    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #deal the 'date' datetime field query
        new_args = deal_args(self,args)
        return super(purchase_order_line,self).search(cr, user, new_args, offset, limit, order, context, count)
    
import time
from openerp.report import report_sxw
from openerp.osv import osv
from openerp import pooler

#redefine the purchase PDF report to new rml
from openerp.addons.purchase.report.order import order
from openerp.report import report_sxw

class metro_pur_order(order):
    def __init__(self, cr, uid, name, context):
        super(order, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({'get_taxes_name':self._get_tax_name})
        self.localcontext.update({'get_boolean_name':self._get_boolean_name})
    #get the taxes name             
    def _get_tax_name(self,taxes_id):
        names = ''
        for tax in taxes_id:
            names += ", " + tax.name
        if names != '': 
            names = names[2:]
        return names      
    def _get_boolean_name(self,bool_val):
#        def _get_source(self, cr, uid, name, types, lang, source=None):
        bool_name = self.pool.get("ir.translation")._get_source(self.cr, self.uid, None, 'code', self.localcontext['lang'], 'bool_' + str(bool_val))
        return bool_name
          
report_sxw.report_sxw('report.purchase.order.metro','purchase.order','addons/metro_purchase/report/purchase_order.rml',parser=metro_pur_order)

from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
def deal_args(obj,args):  
    new_args = []
    for arg in args:
        fld_name = arg[0]
        if fld_name == 'create_date' or fld_name == 'write_date':
            fld_operator = arg[1]
            fld_val = arg[2]
            fld = obj._columns.get(fld_name)
            #['date','=','2013-12-12 16:00:00'] the '16' was generated for the timezone
            if fld._type == 'datetime' and fld_operator == "=" and fld_val.endswith('00:00'):
                time_start = [fld_name,'>=',fld_val]
                time_obj = datetime.datetime.strptime(fld_val,DEFAULT_SERVER_DATETIME_FORMAT)
                time_obj += relativedelta(days=1)
                time_end = [fld_name,'<=',time_obj.strftime(DEFAULT_SERVER_DATETIME_FORMAT)]
                new_args.append(time_start)
                new_args.append(time_end)
            else:
                new_args.append(arg)
        else:
            new_args.append(arg)    
    return new_args