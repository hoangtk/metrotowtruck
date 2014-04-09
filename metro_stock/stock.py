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
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT


class material_request(osv.osv):
    _name = "material.request"
    _inherit = "stock.picking"
    _table = "stock_picking"
    _description = "Material Request"
    _order = "name desc"    
    _columns = {
        'type': fields.selection([('out', 'Sending Goods'), ('in', 'Getting Goods'), ('internal', 'Internal'), ('mr', 'Material Request'), ('mrr', 'Material Return')], 
                                 'Request Type', required=True, select=True, readonly=True, states={'creating':[('readonly',False)]}),
        'move_lines': fields.one2many('material.request.line', 'picking_id', 'Request Products', states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}),
        'mr_dept_id': fields.many2one('hr.department', 'Department', states={'done':[('readonly', True)], 'cancel':[('readonly',True)]}),
        'create_uid': fields.many2one('res.users', 'Creator',readonly=True),        
    }
    _defaults = {
        'type': 'mr',
        'state': 'creating',
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Order Reference must be unique!'),
    ]

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
        vals['state'] = 'draft'
        if not vals.get('name') or vals.get('name','/')=='/':
            if vals['type'] == 'mrr':
                vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'material.request.return') or '/'
            else:
                vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'material.request') or '/'
                
        order =  super(material_request, self).create(cr, uid, vals, context=context)
        return order

    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #deal the 'date' datetime field query
        new_args = deal_args(self,args)
        return super(material_request,self).search(cr, user, new_args, offset, limit, order, context, count)    
                
class material_request_line(osv.osv):
    _name = "material.request.line"
    _inherit = "stock.move"
    _table = "stock_move"
    _description = "Material Request Line"
    def _amount_line(self, cr, uid, ids, prop, arg, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = line.product_qty * line.price_unit
        return res    
    _columns = {
        'picking_id': fields.many2one('material.request', 'MR#', select=True,states={'done': [('readonly', True)]}),
        'mr_emp_id': fields.many2one('hr.employee','Employee'),
        'mr_sale_prod_id': fields.many2one('sale.product','Sale Product ID', ondelete="restrict"),
        'mr_notes': fields.text('Reason and use'),
        'mr_dept_id': fields.related('picking_id','mr_dept_id',string='Department',type='many2one',relation='hr.department',select=True),
        'mr_date_order': fields.related('picking_id','date',string='Order Date',type='datetime'),
        'pick_type': fields.related('picking_id','type',string='Picking Type',type='char'),
        'create_uid': fields.many2one('res.users', 'Creator',readonly=True),
        'price_subtotal': fields.function(_amount_line, string='Subtotal', digits_compute= dp.get_precision('Account')),
        #make the price's decimal precision as the 'Product Price'
        'price_unit': fields.float('Unit Price', digits_compute= dp.get_precision('Product Price'), help="Technical field used to record the product cost set by the user during a picking confirmation (when average price costing method is used)"),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Price'),
            required=True,states={'done': [('readonly', True)]},
            help="This is the quantity of products from an inventory "
                "point of view. For moves in the state 'done', this is the "
                "quantity of products that were actually moved. For other "
                "moves, this is the quantity of product that is planned to "
                "be moved. Lowering this quantity does not generate a "
                "backorder. Changing this quantity on assigned moves affects "
                "the product reservation, and should be done with care."
        ),                
    }
    _order = 'id'
    def default_get(self, cr, uid, fields_list, context=None):
        resu = super(material_request_line,self).default_get(cr, uid, fields_list, context)
        #material_request.type: mr or mrr
        req_type = context.get('req_type')
        if not req_type:
            req_type = 'mr'
        loc_stock_id = None
        loc_prod_id = None
        #get the default stock location
        cr.execute('select c.id \n'+
                    'from res_users a  \n'+
                    'left join stock_warehouse b on a.company_id = b.company_id  \n'+
                    'left join stock_location c on b.lot_stock_id = c.id \n'
                    'where a.id = %s', (uid,))
        loc_src = cr.fetchone()
        if loc_src:
           loc_stock_id = loc_src[0]           
        #get the default production location
        loc_obj = self.pool.get('stock.location')
        prod_loc_ids = loc_obj.search(cr,uid,[('usage','=','production')],context=context)
        if prod_loc_ids and prod_loc_ids[0]:
            prod_loc = loc_obj.browse(cr,uid,prod_loc_ids[0],context=context)
            loc_prod_id = prod_loc.id
        #set the locations by the request type
        if req_type == 'mr':
           if loc_stock_id:
               resu.update({'location_id':loc_stock_id})
           if loc_prod_id:
               resu.update({'location_dest_id':loc_prod_id})
        if req_type == 'mrr':
           if loc_prod_id:
               resu.update({'location_id':loc_prod_id})
           if loc_stock_id:
               resu.update({'location_dest_id':loc_stock_id})                  
           
        return resu
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
            'product_qty': product.qty_available,
            'product_uos_qty' : self.pool.get('stock.move').onchange_quantity(cr, uid, ids, prod_id, 1.00, product.uom_id.id, uos_id)['value']['product_uos_qty'],
            'prodlot_id' : False,
        }
        if not ids:
            result['name'] = product.partner_ref
        if loc_id:
            result['location_id'] = loc_id
        if loc_dest_id:
            result['location_dest_id'] = loc_dest_id
            
        #update the price_unit the and price_currency_id
        #default is the product's cost price
        price_unit = product.standard_price
        price_currency_id = None
        #get the final purchase price
        move_obj = self.pool.get('stock.move')
        #get the final purchase price
        move_ids = move_obj.search(cr,uid,[('product_id','=',prod_id),('state','=','done'),('type','=','in')],limit=1,order='create_date desc')
        if move_ids:
            move_price = move_obj.read(cr,uid,move_ids[0],['price_unit','price_currency_id'],context=ctx)
            price_unit = move_price['price_unit']
            price_currency_id = move_price['price_currency_id']
        result['price_unit'] = price_unit
        result['price_currency_id'] = price_currency_id
        
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

    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #deal the 'date' datetime field query
        new_args = deal_args(self,args)
        return super(material_request_line,self).search(cr, user, new_args, offset, limit, order, context, count)   
            
class stock_move(osv.osv):
    _inherit = "stock.move" 
    def _get_rec_info(self, cr, uid, ids, fields, args, context=None):
        result = {}
        for id in ids:
            result[id] = {'return_qty':0,}
        for m in self.browse(cr,uid,ids,context=context):
            return_qty = 0
            if m.state == 'done':
                for rec in m.move_history_ids2:
                    # only take into account 'product return' moves, ignoring any other
                    # kind of upstream moves, such as internal procurements, etc.
                    # a valid return move will be the exact opposite of ours:
                    #     (src location, dest location) <=> (dest location, src location))
                    if rec.state != 'cancel' \
                        and rec.location_dest_id.id == m.location_id.id \
                        and rec.location_id.id == m.location_dest_id.id:
                        return_qty += (rec.product_qty * rec.product_uom.factor)
                    
            result[m.id].update({'return_qty':return_qty,})
        return result    
    _columns = {
        'type': fields.related('picking_id', 'type', type='selection', selection=[('out', 'Sending Goods'), ('in', 'Getting Goods'), ('internal', 'Internal'), ('mr', 'Material Request'), ('mrr', 'Material Return')], string='Shipping Type'),
        'create_uid': fields.many2one('res.users', 'Creator',readonly=True),
        'supplier_prod_name': fields.related('purchase_line_id', 'supplier_prod_name',string='Supplier Product Name',type="char",readonly=True,store=True),
        'return_qty': fields.function(_get_rec_info, type='float', string='Return Quantity', multi="rec_info", digits_compute=dp.get_precision('Product Price')),
        #make the price's decimal precision as the 'Product Price'
        'price_unit': fields.float('Unit Price', digits_compute= dp.get_precision('Product Price'), help="Technical field used to record the product cost set by the user during a picking confirmation (when average price costing method is used)"),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Price'),
            required=True,states={'done': [('readonly', True)]},
            help="This is the quantity of products from an inventory "
                "point of view. For moves in the state 'done', this is the "
                "quantity of products that were actually moved. For other "
                "moves, this is the quantity of product that is planned to "
                "be moved. Lowering this quantity does not generate a "
                "backorder. Changing this quantity on assigned moves affects "
                "the product reservation, and should be done with care."
        ),                
        
    }

    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #deal the 'date' datetime field query
        new_args = deal_args(self,args)
        return super(stock_move,self).search(cr, user, new_args, offset, limit, order, context, count)  

    def action_done(self, cr, uid, ids, context=None):
        super(stock_move,self).action_done(cr, uid, ids, context) 
        move_ids = []
        for move in self.browse(cr, uid, ids, context=context):
            if move.state not in ('done','cancel'):
                move_ids.append(move.id)     
        self.write(cr, uid, ids, {'date': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}, context=context)

from openerp.addons.stock import stock_picking as stock_picking_super
      
def _set_minimum_date(self, cr, uid, ids, name, value, arg, context=None):
    """ Calculates planned date if it is less than 'value'.
    @param name: Name of field
    @param value: Value of field
    @param arg: User defined argument
    @return: True or False
    """
    if not value:
        return False
    if isinstance(ids, (int, long)):
        ids = [ids]
    for pick in self.browse(cr, uid, ids, context=context):
        sql_str = """update stock_move set
                date_expected='%s'
            where
                picking_id=%s """ % (value, pick.id)
        if pick.min_date:
            sql_str += " and (date_expected='" + pick.min_date + "' or date_expected<'" + value + "')"
        cr.execute(sql_str)
    return True

def _set_maximum_date(self, cr, uid, ids, name, value, arg, context=None):
    """ Calculates planned date if it is greater than 'value'.
    @param name: Name of field
    @param value: Value of field
    @param arg: User defined argument
    @return: True or False
    """
    if not value:
        return False
    if isinstance(ids, (int, long)):
        ids = [ids]
    for pick in self.browse(cr, uid, ids, context=context):
        sql_str = """update stock_move set
                date_expected='%s'
            where
                picking_id=%d """ % (value, pick.id)
        if pick.max_date:
            sql_str += " and (date_expected='" + pick.max_date + "' or date_expected>'" + value + "')"
        cr.execute(sql_str)
    return True   
     
class stock_picking(osv.osv):
    _inherit = "stock.picking" 
    _columns = {   
        'create_uid': fields.many2one('res.users', 'Creator',readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
    }      
    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #deal the 'date' datetime field query
        new_args = deal_args(self,args)
        return super(stock_picking,self).search(cr, user, new_args, offset, limit, order, context, count)
    _order = 'name desc'  

    def action_done(self, cr, uid, ids, context=None):
        """Changes picking state to done.
        
        This method is called at the end of the workflow by the activity "done".
        @return: True
        """
        po_obj = self.pool.get('purchase.order')
        for pick in self.browse(cr,uid,ids,context):
            if pick.purchase_id:
                #if this is purchase return, then set the related purchase order shipped to False
                if pick.type=='out':
                    po_obj.write(cr,uid,[pick.purchase_id.id],{'shipped':False})
                #if this is related to a PO and need to create invoices after picking, then auto generate the invoie and valid the invoice.
                if pick.type=='in' and pick.invoice_state == '2binvoiced':
                    inv_create_obj = self.pool.get("stock.invoice.onshipping")
                    if not context:
                        context = {}
                    context.update({'active_model':'stock.picking.in','active_ids':[pick.id],'active_id':pick.id})
                    journal_id = inv_create_obj._get_journal(cr,uid,context)
                    inv_create_id = inv_create_obj.create(cr,uid,{'journal_id':journal_id},context)
                    pick_inv_ids = inv_create_obj.create_invoice(cr,uid,[inv_create_id],context)
                    invoice_ids = pick_inv_ids.values()
                    '''
                    remove the auto validate, need the accoutant to validate manually.
                    wf_service = netsvc.LocalService("workflow")
                    for invoice_id in invoice_ids:
                        wf_service.trg_validate(uid, 'account.invoice', invoice_id, 'invoice_open', cr)\
                    '''   

        super(stock_picking,self).action_done(cr,uid,ids,context)
        #fix the time issue to use utc now, by johnw
        self.write(cr, uid, ids, {'date_done': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')})
        return True            

    def action_confirm(self, cr, uid, ids, context=None):
        """ Add the lines aggisnment checking
        """
        resu = super(stock_picking,self).action_confirm(cr, uid, ids, context=context)
        if resu:
            pickings = self.browse(cr, uid, ids, context=context)
            todo = []
            for picking in pickings:
                if picking.type in('mr','mrr'):
                    for r in picking.move_lines:
                        if r.state == 'confirmed':
                            todo.append(r.id)
            if len(todo):
                self.pool.get('stock.move').check_assign(cr, uid, todo, context=context)
        return resu       
class stock_picking_out(osv.osv):
    _inherit = "stock.picking.out"   
    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #deal the 'date' datetime field query
        new_args = deal_args(self,args)
        return super(stock_picking_out,self).search(cr, user, new_args, offset, limit, order, context, count)
    _columns = {   
        'message_ids': fields.one2many('mail.message', 'res_id',
            domain=lambda self: [('model', '=', 'stock.picking')],
            auto_join=True,
            string='Messages',
            help="Messages and communication history"),                   
    }            
    _order = 'name desc'  
            
class stock_picking_in(osv.osv):
    _inherit = "stock.picking.in"
 
    _columns = {   
        'create_uid': fields.many2one('res.users', 'Creator',readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'min_date': fields.function(stock_picking_super.get_min_max_date, fnct_inv=_set_minimum_date, multi="min_max_date",
                 store=True, type='datetime', string='Scheduled Time', select=1, help="Scheduled time for the shipment to be processed"), 
        'max_date': fields.function(stock_picking_super.get_min_max_date, fnct_inv=_set_maximum_date, multi="min_max_date",
                 store=True, type='datetime', string='Max. Expected Date', select=2),
        'message_ids': fields.one2many('mail.message', 'res_id',
            domain=lambda self: [('model', '=', 'stock.picking')],
            auto_join=True,
            string='Messages',
            help="Messages and communication history"),                          
    }     
    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        #deal the 'date' datetime field query
        new_args = deal_args(self,args)
        return super(stock_picking_in,self).search(cr, user, new_args, offset, limit, order, context, count)   
    _order = 'name desc'      

class stock_inventory(osv.osv):
    _inherit = "stock.inventory"
    _columns = {
        'comments': fields.text('Comments', size=64, readonly=False, states={'done': [('readonly', True)]}),
        'create_uid': fields.many2one('res.users', 'Creator',readonly=True),
    }
    def unlink(self, cr, uid, ids, context=None):
        inventories = self.read(cr, uid, ids, ['state'], context=context)
        unlink_ids = []
        for s in inventories:
            if s['state'] in ['draft','cancel']:
                unlink_ids.append(s['id'])
            else:
                raise osv.except_osv(_('Invalid Action!'), _('Only the physical inventory orders with Draft or Cancelled state can be delete!'))

        return super(stock_inventory, self).unlink(cr, uid, unlink_ids, context=context)
    
class stock_inventory_line(osv.osv):
    _inherit = "stock.inventory.line"
    _columns = {   
        'image_medium': fields.related('product_id','image_medium',type='binary',String="Medium-sized image"),
        'state': fields.related('inventory_id','state',type='selection',selection=(('draft', 'Draft'), ('cancel','Cancelled'), ('confirm','Confirmed'), ('done', 'Done')),
                                string='Status',readonly=True),
    }
#stock physical inventroy move
#class stock_inventory_move(osv.osv):
#    _name = "stock.inventory.move"
##    _table = "stock_inventory_move_rel"
#    _table = "stock_move"
#    _columns = {   
#        'inventory_id': fields.many2one('stock.inventory','Inventory Referance'),
#        'inventory_state': fields.related('inventory_id','Inventory State',type='selection',selection=(('draft', 'Draft'), ('cancel','Cancelled'), ('confirm','Confirmed'), ('done', 'Done')),
#                                string='Status',readonly=True),
#        'move_id': fields.many2one('stock.move','Inventory Referance'),
#        'product_id': fields.related('move_id','product_id',type='many2one',relation="product.product",String="Product",readonly=True,),
#        'product_qty': fields.related('move_id','product_qty',type='float',String="Quantity",readonly=True,),
#        'location_id': fields.related('move_id','location_id',type='many2one',relation="stock.location",String="Source Location",readonly=True,),
#        'location_dest_id': fields.related('move_id','location_dest_id',type='many2one',relation="stock.location",String="Destination Location",readonly=True,),
#        'state': fields.related('move_id','state',type='selection',selection=[('draft', 'New'),
#                                   ('cancel', 'Cancelled'),
#                                   ('waiting', 'Waiting Another Move'),
#                                   ('confirmed', 'Waiting Availability'),
#                                   ('assigned', 'Available'),
#                                   ('done', 'Done'),
#                                   ],String="Destination Location",readonly=True,),
#    }
           
def deal_args(obj,args):  
    new_args = []
    for arg in args:
        fld_name = arg[0]
        if fld_name == 'date':
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