# -*- encoding: utf-8 -*-
from osv import fields,osv
from openerp.tools.translate import _
class work_order_cnc(osv.osv):
    _name = "work.order.cnc"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "CNC Work Order"
    _columns = {
        'name': fields.char('Name', size=64, required=True,readonly=True, states={'draft':[('readonly',False)]}),
        'note': fields.text('Description', required=False),
        'sale_product_ids': fields.many2many('sale.product','cnc_id_rel','cnc_id','id_id',string="IDs",readonly=True, states={'draft':[('readonly',False)]}),
        'wo_cnc_lines': fields.one2many('work.order.cnc.line','order_id','CNC Work Order Lines',readonly=True, states={'draft':[('readonly',False)]}),
        'state': fields.selection([('draft','Draft'),('confirmed','Confirmed'),('in_progress','In Progress'),('done','Done'),('cancel','Cancelled')],
            'Status', track_visibility='onchange', required=True),
        'create_uid': fields.many2one('res.users','Creator',readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True),   
        'company_id': fields.many2one('res.company', 'Company', readonly=True),                      
    }
    _defaults = {
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'work.order.cnc', context=c),
        'state': 'draft',
    }
    def _set_state(self,cr,uid,ids,state,context=None):
        self.write(cr,uid,ids,{'state':state},context=context)
        line_ids = []
        for wo in self.browse(cr,uid,ids,context=context):
            for line in wo.wo_cnc_lines:
                if not line.state == 'done':
                    line_ids.append(line.id)
        self.pool.get('work.order.cnc.line').write(cr,uid,line_ids,{'state':state})

    def _check_done_lines(self,cr,uid,ids,context=None):
        for wo in self.browse(cr,uid,ids,context=context):
            for line in wo.wo_cnc_lines:
                if line.state == 'done':
                    raise osv.except_osv(_('Invalid Action!'), _('Action was blocked, there are done work order lines!'))
        return True
                    
    def action_confirm(self, cr, uid, ids, context=None):
        self._set_state(cr, uid, ids, 'confirmed',context)
        return True
        
    def action_cancel(self, cr, uid, ids, context=None):
        self._check_done_lines(cr,uid,ids,context)
        #set the cancel state
        self._set_state(cr, uid, ids, 'cancel',context)
        return True
    
    def action_draft(self, cr, uid, ids, context=None):
        #set the cancel state
        self._set_state(cr, uid, ids, 'draft',context)
        return True
    
    def action_done(self, cr, uid, ids, context=None):
        #set the cancel state
        self._set_state(cr, uid, ids, 'done',context)
        return True
        
    def unlink(self, cr, uid, ids, context=None):
        orders = self.read(cr, uid, ids, ['state'], context=context)
        for s in orders:
            if s['state'] not in ['draft','cancel']:
                raise osv.except_osv(_('Invalid Action!'), _('Only the orders in draft or cancel state can be delete.'))
        self._check_done_lines(cr,uid,ids,context)
        return super(work_order_cnc, self).unlink(cr, uid, ids, context=context)
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        old_data = self.read(cr,uid,id,['name'],context=context)
        default.update({
            'name': '%s (copy)'%old_data['name'],
        })
        return super(work_order_cnc, self).copy(cr, uid, id, default, context)    
class work_order_cnc_line(osv.osv):
    _name = "work.order.cnc.line"
    _description = "CNC Work Order Lines"
    _columns = {
        'order_id': fields.many2one('work.order.cnc','Ref'),
        'file_name': fields.char('File Name', size=16, required=True),
        'plate_length': fields.integer('Length(mm)', required=True),
        'plate_width': fields.integer('Width(mm)', required=True),
        'plate_height': fields.integer('Height(mm)', required=True),
        'percent_usage': fields.float('Usage Percent(%)', required=True),
        'date_finished': fields.date('Finished Date', readonly=True),
        'product_id': fields.many2one('product.product','Product'),
        'state': fields.selection([('draft','Draft'),('confirmed','Confirmed'),('done','Done'),('cancel','Cancelled')], 'Status', required=True, readonly=True),
        'company_id': fields.related('order_id','company_id',type='many2one',relation='res.company',string='Company')
    }

    _defaults = {
        'state': 'draft',
    }
    def _check_size(self,cr,uid,ids,context=None):
        for record in self.browse(cr, uid, ids, context=context):
            if record.state == 'draft' and (record.plate_length <= 0 or record.plate_width <= 0 or record.plate_height <= 0 or record.percent_usage <= 0):
                raise osv.except_osv(_('Error'), _('The Length/Width/Height/UsagePercent must be larger than zero\n %s.')% (record.file_name,))
        return True
    _constraints = [
        (_check_size,
            'You must assign a serial number for this product.',
            ['plate_length','plate_width','plate_height']),]
                        
    def action_done(self, cr, uid, ids, context=None):
        #set the done data
        vals = {'state':'done','product_id':context.get('product_id'),'date_finished':context.get('date_finished')}
        if not context:
            context = {}
        context.update({'force_write':True})
        self.write(cr, uid, ids, vals ,context=context)
        #auto set the CNC order done once all lines are done
        order_ids = {}
        order_ids_done = []
        for line in self.read(cr,uid,ids,['order_id'],context=context):
            order_id = line['order_id'][0]
            if not order_ids.has_key(order_id):
                order_ids.update({order_id:order_id})
        order_ids = order_ids.keys()
        for order in self.pool.get('work.order.cnc').browse(cr,uid,order_ids,context=context):
            order_done = True
            for line in order.wo_cnc_lines:
                if not line.state == 'done':
                    order_done = False
                    break
            if order_done:
                order_ids_done.append(order.id)
        self.pool.get('work.order.cnc').action_done(cr,uid,order_ids_done,context=context)
        #generate material requisition
        self.make_material_requisition(cr, uid, ids, context)
        return True
    import copy
    def make_material_requisition(self, cr, uid, wo_cnc_lines, context = None):
        mr_obj = self.pool.get("material.requisition")
        mr_name = self.pool.get('ir.sequence').get(cr, uid, 'material.request') or '/'
        mr_name += ' from CNC'
        mr_vals = {'type':'mr','mr_dept_id':context.get('mr_dept_id'),'name':mr_name,'date':fields.datetime.now()}
        
        mr_line_val_template = {
                        'product_id':context.get('product_id'),
#                        'product_qty':,
#                        'price_unit':,
                        'mr_emp_id':uid,
#                        'mr_sale_prod_id':
                        'mr_notes':'CNC Work Order Finished'}
        mr_line_vals = []
        cnc_lines = self.pool.get('work.order.cnc.line').browse(cr, uid, wo_cnc_lines, context=context)
        for ln in cnc_lines:
            ln_volume = (ln.plate_length * ln.plate_width * ln.plate_height * ln.percent_usage)
            prod_volume = (ln.product_id.plate_length * ln.product_id.plate_width * ln.product_id.plate_height)
            ln_weight = (ln_volume/prod_volume) * ln.product_id.density
            #loop ids to generate mr line
            id_cnt = len(ln.order_id.sale_product_ids)
            for id in ln.order_id.sale_product_ids:
                mr_line_vals = mr_line_val_template.copy()
                mr_line_vals.update({'product_qty':ln_weight/id_cnt})

        
        move_vals['line_id'] = [(0, 0, line) for line in move_lines]
        move_obj.create(cr, uid, move_vals, context=context)        
        
            
    def _check_changing(self, cr, uid, ids, context=None):
        lines = self.read(cr, uid, ids, ['state','file_name'], context=context)
        for s in lines:
            if s['state'] not in ['draft','cancel']:
                raise osv.except_osv(_('Invalid Action!'), _('Only the lines in draft or cancel state can be change.\n%s')%(s['file_name'],))
        
    def unlink(self, cr, uid, ids, context=None):
        self._check_changing(cr, uid, ids, context)
        return super(work_order_cnc_line, self).unlink(cr, uid, ids, context=context) 
        
    def write(self, cr, uid, ids, vals, context=None):
        if not context:
            context = {}        
        if not context.get('force_write') \
            and not(len(vals) == 1 and vals.has_key('order_id')) \
            and not(len(vals) == 1 and vals.has_key('state')):
            self._check_changing(cr, uid, ids, context)
        return super(work_order_cnc_line, self).write(cr, uid, ids, vals, context=context)  

    def copy_data(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'date_finished': None,
            'product_id': None,
        })
        return super(work_order_cnc_line, self).copy_data(cr, uid, id, default, context)        