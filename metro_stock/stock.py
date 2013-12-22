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
import datetime
from openerp import netsvc
from openerp.osv import fields,osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT


class material_request(osv.osv):
    _name = "material.request"
    _inherit = "stock.picking"
    _table = "stock_picking"
    _description = "Material Request"

    _columns = {
        'type': fields.selection([('out', 'Sending Goods'), ('in', 'Getting Goods'), ('internal', 'Internal'), ('mr', 'Material Request')], 'Shipping Type', required=True, select=True, help="Shipping type specify, goods coming in or going out."),                
        'move_lines': fields.one2many('material.request.line', 'picking_id', 'Request Products', states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}),
        'mr_dept_id': fields.many2one('hr.department', 'Department', states={'done':[('readonly', True)], 'cancel':[('readonly',True)]}),
        
    }
    _defaults = {
        'type': 'mr',
        'move_type': 'one',
    }

    def check_access_rights(self, cr, uid, operation, raise_exception=True):
        #override in order to redirect the check of acces rights on the stock.picking object
        return self.pool.get('stock.picking').check_access_rights(cr, uid, operation, raise_exception=raise_exception)

    def check_access_rule(self, cr, uid, ids, operation, context=None):
        #override in order to redirect the check of acces rules on the stock.picking object
        return self.pool.get('stock.picking').check_access_rule(cr, uid, ids, operation, context=context)

    def _workflow_trigger(self, cr, uid, ids, trigger, context=None):
        #override in order to trigger the workflow of stock.picking at the end of create, write and unlink operation
        #instead of it's own workflow (which is not existing)
        return self.pool.get('stock.picking')._workflow_trigger(cr, uid, ids, trigger, context=context)

    def _workflow_signal(self, cr, uid, ids, signal, context=None):
        #override in order to fire the workflow signal on given stock.picking workflow instance
        #instead of it's own workflow (which is not existing)
        return self.pool.get('stock.picking')._workflow_signal(cr, uid, ids, signal, context=context)
        
    def create(self, cr, uid, vals, context=None):
        if vals.get('name','/')=='/':
            vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'material.request') or '/'
        order =  super(material_request, self).create(cr, uid, vals, context=context)
        return order
    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #deal the 'date' datetime field query
        new_args = []
        for arg in args:
            fld_name = arg[0]
            if fld_name == 'date':
                fld_operator = arg[1]
                fld_val = arg[2]
                fld = self._columns.get(fld_name)
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
        return super(material_request,self).search(cr, user, new_args, offset, limit, order, context, count)  
class material_request_line(osv.osv):
    _name = "material.request.line"
    _inherit = "stock.move"
    _table = "stock_move"
    _description = "Material Request Line"
    _columns = {
        'picking_id': fields.many2one('material.request', 'Reference', select=True,states={'done': [('readonly', True)]}),
        'mr_emp_id': fields.many2one('hr.employee','Employee'),
        'mr_sale_prod_id': fields.char('Sale Product ID',size=8),
        'mr_notes': fields.text('Reason and use'),
        'mr_dept_id': fields.related('picking_id','mr_dept_id',string='Department',type='many2one',relation='hr.department',select=True),
        'mr_date_order': fields.related('picking_id','date',string='Request Date',type='datetime'),
        'pick_type': fields.related('picking_id','type',string='Picking Type',type='char'),
    }
    def onchange_product_id(self, cr, uid, ids, prod_id=False, loc_id=False,
                            loc_dest_id=False, ):
        """ On change of product id, if finds UoM, UoS, quantity and UoS quantity.
        @param prod_id: Changed Product id
        @param loc_id: Source location id
        @param loc_dest_id: Destination location id
        @param partner_id: Address id of partner
        @return: Dictionary of values
        """
        if not prod_id:
            return {}
        user = self.pool.get("res.users").browse(cr,uid,uid)
        ctx = {'lang': user.lang}

        product = self.pool.get('product.product').browse(cr, uid, [prod_id], context=ctx)[0]
        uos_id  = product.uos_id and product.uos_id.id or False
        result = {
            'product_uom': product.uom_id.id,
            'product_uos': uos_id,
            'product_qty': 1.00,
            'product_uos_qty' : self.pool.get('stock.move').onchange_quantity(cr, uid, ids, prod_id, 1.00, product.uom_id.id, uos_id)['value']['product_uos_qty'],
            'prodlot_id' : False,
        }
        if not ids:
            result['name'] = product.partner_ref
        if loc_id:
            result['location_id'] = loc_id
        if loc_dest_id:
            result['location_dest_id'] = loc_dest_id
        return {'value': result}
    def check_access_rights(self, cr, uid, operation, raise_exception=True):
        #override in order to redirect the check of acces rights on the stock.picking object
        return self.pool.get('stock.move').check_access_rights(cr, uid, operation, raise_exception=raise_exception)

    def check_access_rule(self, cr, uid, ids, operation, context=None):
        #override in order to redirect the check of acces rules on the stock.picking object
        return self.pool.get('stock.move').check_access_rule(cr, uid, ids, operation, context=context)

    def _workflow_trigger(self, cr, uid, ids, trigger, context=None):
        #override in order to trigger the workflow of stock.picking at the end of create, write and unlink operation
        #instead of it's own workflow (which is not existing)
        return self.pool.get('stock.move')._workflow_trigger(cr, uid, ids, trigger, context=context)

    def _workflow_signal(self, cr, uid, ids, signal, context=None):
        #override in order to fire the workflow signal on given stock.picking workflow instance
        #instead of it's own workflow (which is not existing)
        return self.pool.get('stock.move')._workflow_signal(cr, uid, ids, signal, context=context)    
    
class stock_move(osv.osv):
    _inherit = "stock.move" 
    _columns = {   
        'type': fields.related('picking_id', 'type', type='selection', selection=[('out', 'Sending Goods'), ('in', 'Getting Goods'), ('internal', 'Internal'), ('mr', 'Material Request')], string='Shipping Type'),
    }
#class stock_picking(osv.osv):
#    _inherit = "stock.picking" 
#    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
#        #deal the datetime field query
#        new_args = []
#        for arg in args:
#            fld_name = arg[0]
#            fld_operator = arg[1]
#            fld_val = arg[2]
#            fld = self._columns.get(fld_name)
#            #['date','=','2013-12-12 16:00:00'] the '16' was generated for the timezone
#            if fld._type == 'datetime' and fld_operator == "=" and fld_val.endswith('00:00'):
#                time_start = [fld_name,'>=',fld_val]
#                time_obj = datetime.datetime.strptime(fld_val,DEFAULT_SERVER_DATETIME_FORMAT)
#                time_obj += relativedelta(days=1)
#                time_end = [fld_name,'<=',time_obj.strftime(DEFAULT_SERVER_DATETIME_FORMAT)]
#                new_args.append(time_start)
#                new_args.append(time_end)
#            else:
#                new_args.append(arg)
#        return super(stock_picking,self).search(cr, user, new_args, offset, limit, order, context, count)    
#class stock_partial_picking(stock_partial_picking.stock_partial_picking):
#    
#    def default_get(self, cr, uid, fields, context=None):
#        if context is None: context = {}
#        res = super(stock_partial_picking, self).default_get(cr, uid, fields, context=context)
#        picking_ids = context.get('active_ids', [])
#        active_model = context.get('active_model')
#
#        if not picking_ids or len(picking_ids) != 1:
#            # Partial Picking Processing may only be done for one picking at a time
#            return res
#        assert active_model in ('stock.picking', 'stock.picking.in', 'stock.picking.out', 'material.request'), 'Bad context propagation'
#        picking_id, = picking_ids
#        if 'picking_id' in fields:
#            res.update(picking_id=picking_id)
#        if 'move_ids' in fields:
#            picking = self.pool.get('stock.picking').browse(cr, uid, picking_id, context=context)
#            moves = [self._partial_move_for(cr, uid, m) for m in picking.move_lines if m.state not in ('done','cancel')]
#            res.update(move_ids=moves)
#        if 'date' in fields:
#            res.update(date=time.strftime(DEFAULT_SERVER_DATETIME_FORMAT))
#        return res    