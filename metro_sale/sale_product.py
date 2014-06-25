# -*- encoding: utf-8 -*-
from osv import fields,osv
from openerp.tools.translate import _
#the ID for the purchase requisition and the material request
class sale_product(osv.osv):
    _name = "sale.product"
    _description = "Sale Product"
    _columns = {
        'name': fields.char('ID', size=8, required=True, readonly=True),
        'note': fields.text('Description', required=False),
        'create_uid':  fields.many2one('res.users', 'Creator', readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'active': fields.boolean('Active', help="If unchecked, it will allow you to hide the product without removing it."),
        'source': fields.selection( [('sale', 'Sales'), ('stock', 'Stocking'), ('other', 'Others')],'Source', required=True,),
        'serial_id': fields.many2one('mttl.serials', 'Product Serial'),
        'mto_design_id': fields.many2one('mto.design', 'Configuration'),
        'product_id': fields.many2one('product.product',string='Product'),
        'project_ids': fields.many2many('project.project','project_id_rel','mfg_id','project_id',string='Engineering Project',readonly=True),
        'mrp_order_id': fields.many2one('mrp.production',string='Manufacture Order'),
        'state': fields.selection([
                   ('draft','Draft'),
                   ('confirmed','Confirmed'),
                   ('in_progress','In Progress'),
                   ('done','Complete'),
                   ('cancelled','Cancel')], 'Status'),
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'ID must be unique!'),
    ]
    _defaults = {'state':'draft',
                 'active':True,'name':'/'}
    _order = 'id desc'
    def create(self, cr, uid, data, context=None):       
        if data.get('name','/')=='/':
            data['name'] = self.pool.get('ir.sequence').get(cr, uid, 'sale.product.id') or '/'
                        
        resu = super(sale_product, self).create(cr, uid, data, context)
        return resu    
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
            
        if ('project_ids' in vals and vals['project_ids']) or ('mrp_order_id' in vals and vals['mrp_order_id']):
            vals.update({'state':'in_progress'})
            
        return super(sale_product, self).write(cr, uid, ids, vals, context=context)
    
    def button_confirm(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'confirmed'})
    def button_cancel(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'cancelled'})
    def button_to_draft(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'draft'})  
    def button_create_project(self, cr, uid, ids, context=None):
        for sale_product_id in self.browse(cr, uid, ids, context=context):
            if sale_product_id.project_ids:
                raise osv.except_osv(_('Error'),_("This ID already has project generated!"))
            vals = {'name':('ENG Project for ID %s'%(sale_product_id.name,))}
            project_id = self.pool.get('project.project').create(cr, uid, vals, context=context)
            self.write(cr, uid, sale_product_id.id, {'project_ids':[(4, project_id)]},context=context)
    def button_create_mfg_order(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'draft'})                  

class mttl_serials(osv.osv):
    _inherit = "mttl.serials"
    _columns = {
        'mfg_id_id': fields.many2one('sale.product', 'MFG ID'),
    }                        