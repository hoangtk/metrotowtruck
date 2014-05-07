# -*- encoding: utf-8 -*-
from osv import fields,osv
from openerp.tools.translate import _
from openerp import netsvc
import time
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
class work_order_cnc(osv.osv):
    _name = "work.order.cnc"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "CNC Work Order"
    def _get_done_info(self, cr, uid, ids, fields, args, context=None):
        result = {}
        for id in ids:
            result[id] = {'can_change_ids':True}
        for order in self.browse(cr,uid,ids,context=context):
            if order.state != 'draft' :
                can_change_ids = False
            else:
                can_change_ids = True
                for line in order.wo_cnc_lines:
                    if line.state == 'done':
                        can_change_ids = False
                        break
            result[order.id].update({'can_change_ids':can_change_ids})
        return result    
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
        'product_id': fields.related('wo_cnc_lines','product_id', type='many2one', relation='product.product', string='Product'),
        'can_change_ids' : fields.function(_get_done_info, type='boolean', string='Can Change IDs', multi="done_info"),
    }
    _defaults = {
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'work.order.cnc', context=c),
        'state': 'draft',
        'can_change_ids': True,
    }
    _order = 'id desc'
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
        'percent_usage_theory': fields.float('Usage Percent in Theory(%)', required=True),
        'percent_usage': fields.float('Usage Percent of Manufacture(%)', required=True),
        'date_finished': fields.date('Finished Date', readonly=True),
        'product_id': fields.many2one('product.product','Product', readonly=True),
        'state': fields.selection([('draft','Draft'),('confirmed','Confirmed'),('done','Done'),('cancel','Cancelled')], 'Status', required=True, readonly=True),
        'company_id': fields.related('order_id','company_id',type='many2one',relation='res.company',string='Company'),
        'mr_id': fields.many2one('material.request','MR#', readonly=True),
        'is_whole_plate': fields.boolean('Whole Plate', readonly=True),
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
        vals = {'state':'done','product_id':context.get('product_id'),'date_finished':context.get('date_finished'),'is_whole_plate':context.get('is_whole_plate')}
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
        #decrease the quantity of whole plate
        if context.get("is_whole_plate"):
            self.pool.get('plate.material').update_plate_whole_qty(cr, uid, context.get('product_id'), -1, context=context)
        return True

    #get the material request price
    def _get_mr_prod_price(self, cr, uid, product, context = None):
        result = {}
        #update the price_unit the and price_currency_id
        #default is the product's cost price
        price_unit = product.standard_price
        price_currency_id = None
        #get the final purchase price
        move_obj = self.pool.get('stock.move')
        #get the final purchase price
        move_ids = move_obj.search(cr,uid,[('product_id','=',product.id),('state','=','done'),('type','=','in')],limit=1,order='create_date desc')
        if move_ids:
            move_price = move_obj.read(cr,uid,move_ids[0],['price_unit','price_currency_id'],context=context)
            price_unit = move_price['price_unit']
            price_currency_id = move_price['price_currency_id']
        result['price_unit'] = price_unit
        result['price_currency_id'] = price_currency_id
        return result
    #generate the material requisition  
    def make_material_requisition(self, cr, uid, wo_cnc_lines, context = None):
        mr_obj = self.pool.get("material.request")
        mr_line_obj = self.pool.get("material.request.line")
        #create material requisition
        mr_name = self.pool.get('ir.sequence').get(cr, uid, 'material.request') or '/'
        mr_name += ' from CNC'
        mr_vals = {'type':'mr','mr_dept_id':context.get('mr_dept_id'),'name':mr_name,'date':fields.datetime.now()}
        mr_id = mr_obj.create(cr, uid, mr_vals, context=context)
        #create material requisition lines
        mr_line_vals = []
        mr_line_ids = []
        cnc_lines = self.pool.get('work.order.cnc.line').browse(cr, uid, wo_cnc_lines, context=context)
        #get the employee id
        mr_emp_id = None
        user = self.pool.get('res.users').browse(cr,uid,uid,context=context)
        if user.employee_ids:
            mr_emp_id = user.employee_ids[0].id
        for ln in cnc_lines:
            ln_volume = (ln.plate_length * ln.plate_width * ln.plate_height * ln.percent_usage/100)
            #the name will be like 'Manganese Plate(T20*2200*11750mm)'
            prod_name = ln.product_id.name
            start_idx = -1
            end_idx = -1
            try:
                start_idx = prod_name.index('(T')
                end_idx = prod_name.index('mm)')
            except Exception, e:
                raise osv.except_osv(_('Calculate Volume Error!'), _('The product name do not satisfy the format, can not get the plate volume!\n%s')%(prod_name,))
            prod_volume = eval(prod_name[start_idx+2:end_idx])

            ln_quantity = ln_volume/prod_volume
            price = self._get_mr_prod_price(cr, uid, ln.product_id)
            #loop ids to generate mr line
            if ln.order_id.sale_product_ids:
                id_cnt = len(ln.order_id.sale_product_ids)
                for sale_id in ln.order_id.sale_product_ids:
                    mr_line_vals = {'picking_id':mr_id,
                                    'name':'CNC_' + ln.file_name,
                                    'product_id':ln.product_id.id,
                                        'product_qty':ln_quantity/id_cnt,
                                        'product_uom':ln.product_id.uom_id.id,
                                        'price_unit':price['price_unit'],
                                        'price_currency_id':price['price_currency_id'],
                                        'mr_emp_id':mr_emp_id,
                                        'mr_sale_prod_id':sale_id.id,
                                        'mr_notes':'CNC Work Order Finished',}
                    mr_line_id = mr_line_obj.create(cr,uid,mr_line_vals,context=context)
                    mr_line_ids.append(mr_line_id)
            else:
                    mr_line_vals = {'picking_id':mr_id,
                                    'name':'CNC_' + ln.file_name,
                                    'product_id':ln.product_id.id,
                                        'product_qty':ln_quantity,
                                        'product_uom':ln.product_id.uom_id.id,
                                        'price_unit':price['price_unit'],
                                        'price_currency_id':price['price_currency_id'],
                                        'mr_emp_id':mr_emp_id,
                                        'mr_notes':'CNC Work Order Finished',}
                    mr_line_id = mr_line_obj.create(cr,uid,mr_line_vals,context=context)
                    mr_line_ids.append(mr_line_id)
                
            self.pool.get('work.order.cnc.line').write(cr,uid,ln.id,{'mr_id':mr_id},context=context)
        
        mr_line_obj.action_confirm(cr, uid, mr_line_ids)
        mr_line_obj.force_assign(cr, uid, mr_line_ids)
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'stock.picking', mr_id, 'button_confirm', cr)
        
        #do auto receiving
        partial_data = {
            'delivery_date' : time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        }
        for mr_line in mr_line_obj.browse(cr, uid, mr_line_ids, context=context):
            partial_data['move%s' % (mr_line.id)] = {
                'product_id': mr_line.product_id.id,
                'product_qty': mr_line.product_qty,
                'product_uom': mr_line.product_uom.id,
                'prodlot_id': mr_line.prodlot_id.id,
            }
        self.pool.get('stock.picking').do_partial(cr, uid, [mr_id], partial_data, context=context)           
            
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
            'mr_id': None,
        })
        return super(work_order_cnc_line, self).copy_data(cr, uid, id, default, context)        