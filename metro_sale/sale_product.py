# -*- encoding: utf-8 -*-
from osv import fields,osv
from openerp.tools.translate import _
#the ID for the purchase requisition and the material request
class sale_product(osv.osv):
    _name = "sale.product"
    _description = "Sale Product"
    _columns = {
        'name': fields.char('ID', size=32, required=True),
        'note': fields.char('Description', size=128, required=False),
        'create_uid':  fields.many2one('res.users', 'Creator', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'active': fields.boolean('Active', help="If unchecked, it will allow you to hide the product without removing it."),
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'ID must be unique!'),
    ]
    _defaults = {'active':True}
    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]

        if 'name' in vals.keys():
            stock_moves = self.pool.get('material.request.line').search(cr,uid,[('mr_sale_prod_id','in',ids)],context=context)
            if stock_moves and len(stock_moves) > 0:
                raise osv.except_osv(_('Warning !'), _("You cannot change the ID which contains stock moving!"))
            work_order_cncs = self.pool.get('work.order.cnc').search(cr,uid,[('sale_product_ids','in',ids)],context=context)
            if work_order_cncs and len(work_order_cncs) > 0:
                raise osv.except_osv(_('Warning !'), _("You cannot change the ID which contains CNC work orders!"))    
            
        return super(sale_product, self).write(cr, uid, ids, vals, context=context)