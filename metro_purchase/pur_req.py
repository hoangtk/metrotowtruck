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
    _description="Purchase Requisitions"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    def _full_gen_po(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for req in self.browse(cursor, user, ids, context=context):
            full_gen_po = True
            if req.line_ids:
                for req_line in req.line_ids:
                    if not req_line.generated_po:
                        full_gen_po = False
                        break
            res[req.id] = full_gen_po
        return res    
    _columns = {
        'name': fields.char('Requisition#', size=32,required=True),
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse',required=True,readonly=True, states={'draft':[('readonly',False)]}),    
        'user_id': fields.many2one('res.users', 'Requester',required=True,readonly=True, states={'draft':[('readonly',False)]}),        
        'date_request': fields.datetime('Requisition Date',required=True,readonly=True, states={'draft':[('readonly',False)]}),
        'remark': fields.text('Remark'),
        'company_id': fields.many2one('res.company', 'Company', required=True,readonly=True, states={'draft':[('readonly',False)]}),
        'line_ids' : fields.one2many('pur.req.line','req_id','Products to Purchase',readonly=True, states={'draft':[('readonly',False)]}),
        'state': fields.selection([('draft','New'),('confirmed','Confirmed'),('in_purchase','In Purchasing'),('done','Purchase Done'),('cancel','Cancelled')],
            'Status', track_visibility='onchange', required=True, groups='metro_purchase.group_pur_req_requester,metro_purchase.group_pur_req_buyer'),
        'po_ids' : fields.one2many('purchase.order','req_id','Related PO'),      
        'full_gen_po': fields.function(_full_gen_po, string='All products generated PO', type='boolean', help="It indicates that this requsition's all lines generated PO"),      
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
            'po_ids':[],
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
    
    def action_cancel_draft(self, cr, uid, ids, context=None):
        if not len(ids):
            return False
        self.write(cr, uid, ids, {'state':'draft'})
        wf_service = netsvc.LocalService("workflow")
        for p_id in ids:
            # Deleting the existing instance of workflow for requisition
            wf_service.trg_delete(uid, 'pur.req', p_id, cr)
            wf_service.trg_create(uid, 'pur.req', p_id, cr)
        return True
            
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
            res[req_line.id] = generated_po
        return res
    def _po_info(self, cr, uid, ids, field_names=None, arg=False, context=None):
        """ Finds the requisition related PO info.
        @return: Dictionary of values
        """
        if not field_names:
            field_names = []
        if context is None:
            context = {}
        res = {}
        for id in ids:
            res[id] = {}.fromkeys(field_names, 0.0)
        for f in field_names:
            if f == 'generated_po':
                for req_line in self.browse(cr, uid, ids, context=context):
                    generated_po = False
                    if req_line.po_lines_ids:
                        for po_line in req_line.po_lines_ids:
                            if po_line.state != 'cancel':
                                generated_po = True
                                break
                    res[req_line.id][f] = generated_po 
            if f == 'po_info':
                for req_line in self.browse(cr, uid, ids, context=context):
#                    po_str = None
                    po_str = 0
                    if req_line.po_lines_ids:
                        for po_line in req_line.po_lines_ids:
                            if po_line.state != 'cancel':
#                                po_str += ((po_str or '') and ':') + po_line.product_qty + '@' + po_line.order_id.name
                                po_str = po_line.product_qty
                    res[req_line.id][f] = po_str 
        return res    
    _columns = {
        'req_id' : fields.many2one('pur.req','Purchase Requisition', ondelete='cascade'),
        'product_id': fields.many2one('product.product', 'Product' ,required=True),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure'),required=True),
        'product_uom_id': fields.many2one('product.uom', 'Product Unit of Measure',required=True),
        'date_required': fields.date('Date Required',required=True),
        'inv_qty': fields.float('Inventory'),
        'req_emp_id': fields.many2one('hr.employee','Employee'),
        'req_reason': fields.char('Reason and use',size=64),
        'company_id': fields.related('req_id','company_id',type='many2one',relation='res.company',String='Company',store=True,readonly=True),
        'po_lines_ids' : fields.one2many('purchase.order.line','req_line_id','Purchase Order Lines'),
        'generated_po': fields.function(_po_info, multi='po_info', string='PO Generated', type='boolean', help="It indicates that this products has PO generated"),
        'po_info': fields.function(_po_info, multi='po_info',type='float',string='PO Quantity'),   
        'req_ticket_no': fields.char('Requisition Ticket#', size=10)
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

    def copy_data(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'po_lines_ids':[],
        })
        res = super(pur_req_line, self).copy_data(cr, uid, id, default, context)
        return res    
       
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

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
