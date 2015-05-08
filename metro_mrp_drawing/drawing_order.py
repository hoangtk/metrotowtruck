# -*- encoding: utf-8 -*-
from osv import fields,osv
from openerp.tools.translate import _
from openerp import netsvc
import time
import datetime
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.report.pyPdf import PdfFileWriter, PdfFileReader
from openerp.addons.metro import utils
import zipfile
import random
import os
from openerp import SUPERUSER_ID
    
class drawing_order(osv.osv):
    _name = "drawing.order"
    _inherit = ['mail.thread']
    _description = "Drawing Order"
    _order = 'id desc'
    _columns = {
        'name': fields.char('Name', size=64, required=True,readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'note': fields.text('Description', required=False),
        'sale_product_ids': fields.many2many('sale.product','drawing_order_id_rel','drawing_order_id','id_id',
                                             string="MFG IDs",readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'order_lines': fields.one2many('drawing.order.line','order_id','Drawing Order Lines',readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'state': fields.selection([('draft','Draft'),('ready','Ready'),('confirmed','Confirmed'),('approved','Approved'),('rejected','Rejected'),('cancel','Cancelled')],
            'Status', track_visibility='onchange', required=True),
        'reject_message': fields.text('Rejection Message', track_visibility='onchange'),
        'create_uid': fields.many2one('res.users','Creator',readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True),   
#        'date_finished': fields.datetime('Finished Date', readonly=True),
        'company_id': fields.many2one('res.company', 'Company', readonly=True),     
        'product_id': fields.related('drawing_order_line','product_id', type='many2one', relation='product.product', string='Product'),
        'main_part_id': fields.many2one('product.product','Main Product',readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'bom_file_name': fields.char('BOM File Name', size=64),
        'bom_file': fields.function(utils.field_get_file, fnct_inv=utils.field_set_file, string="BOM File", type="binary", multi="_get_file",),
    }
    _defaults = {
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'drawing.order', context=c),
        'state': 'draft',
    }
    _order = 'id desc'
    
    def _set_state(self,cr,uid,ids,state,context=None):
        self.write(cr,uid,ids,{'state':state},context=context)
        line_ids = []
        for order in self.browse(cr,uid,ids,context=context):
            for line in order.order_lines:
                if not line.state == 'done':
                    line_ids.append(line.id)
        self.pool.get('drawing.order.line').write(cr,uid,line_ids,{'state':state})

    def _check_done_lines(self,cr,uid,ids,context=None):
#        for wo in self.browse(cr,uid,ids,context=context):
#            for line in wo.wo_cnc_lines:
#                if line.state == 'done':
#                    raise osv.except_osv(_('Invalid Action!'), _('Action was blocked, there are done work order lines!'))
        return True
    
    def _email_notify(self, cr, uid, ids, action_name, group_params, context=None):
        for order in self.browse(cr, uid, ids, context=context):
            for group_param in group_params:
                email_group_id = self.pool.get('ir.config_parameter').get_param(cr, uid, group_param, context=context)
                if email_group_id:                    
                    email_subject = 'Drawing reminder: %s %s'%(order.name,action_name)
                    mfg_id_names = ','.join([mfg_id.name for mfg_id in order.sale_product_ids])
                    #[(id1,name1),(id2,name2),...(idn,namen)]
                    main_part_name = ''
                    if order.main_part_id:
                        main_part_name = self.pool.get('product.product').name_get(cr, uid,  [order.main_part_id.id], context=context)[0][1]
                    email_body = '%s %s %s, MFG IDs:%s'%(order.name,main_part_name, action_name,mfg_id_names)
                    email_from = self.pool.get("res.users").read(cr, uid, uid, ['email'],context=context)['email']
                    utils.email_send_group(cr, uid, email_from, None,email_subject,email_body, email_group_id, context=context)
        
    def action_ready(self, cr, uid, ids, context=None):
        #set the ready state
        self._set_state(cr, uid, ids, 'ready',context)
        #send email to the user group that can confirm
        self._email_notify(cr, uid, ids, 'need your confirmation', ['mrp_cnc_wo_group_confirm'],context)     
        return True
        
    def action_confirm(self, cr, uid, ids, context=None):
        for order in self.browse(cr, uid, ids, context=context):
            #must have cnc lines
            if not order.order_lines:
                raise osv.except_osv(_('Error!'), _('Please add lines for order [%s]%s')%(order.id, order.name))
            for line in order.order_lines:
                if not line.drawing_file_name:
                    raise osv.except_osv(_('Invalid Action!'), _('The line''s "Drawing PDF" file is required!'))
        #set state to done
        self._set_state(cr, uid, ids, 'confirmed',context)
        #send email to the user group that can approve
        self._email_notify(cr, uid, ids, 'need your approval', ['mrp_cnc_wo_group_approve'],context)           
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

    def action_approve(self, cr, uid, ids, context=None):
        #set the cancel state
        self._set_state(cr, uid, ids, 'approved',context)
        #send email to the user group that can CNC done
        self._email_notify(cr, uid, ids, 'was approved', ['mrp_cnc_wo_group_cnc_mgr'],context) 
        return True

    def action_reject_callback(self, cr, uid, ids, message, context=None):
        #set the draft state
        self._set_state(cr, uid, ids, 'rejected',context)
        self.write(cr,uid,ids,{'reject_message':message})
        #send email to the user for the rejection message
        email_from = self.pool.get("res.users").read(cr, uid, uid, ['email'],context=context)['email']
        for order in self.browse(cr, uid, ids, context=context):
            if order.create_uid.email:
                email_content = 'CNC reminder: %s was rejected'%(order.name)
                utils.email_send_group(cr, uid, email_from, order.create_uid.email,email_content,email_content, context = context) 
        return True
                    
    def action_reject(self, cr, uid, ids, context=None):     
        ctx = dict(context)
        ctx.update({'confirm_title':'Confirm rejection message',
                    'src_model':'drawing.order',
                    "model_callback":'action_reject_callback',})
        return self.pool.get('confirm.message').open(cr, uid, ids, ctx)
                
    def unlink(self, cr, uid, ids, context=None):
        orders = self.read(cr, uid, ids, ['state'], context=context)
        for s in orders:
            if s['state'] not in ['draft','cancel']:
                raise osv.except_osv(_('Invalid Action!'), _('Only the orders in draft or cancel state can be delete.'))
        self._check_done_lines(cr,uid,ids,context)
        return super(drawing_order, self).unlink(cr, uid, ids, context=context)
    
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        old_data = self.read(cr,uid,id,['name'],context=context)
        default.update({
            'name': '%s (copy)'%old_data['name'],
            'mfg_task_id': None,
            'sale_product_ids': None,
            'reject_message':None,
        })
        return super(drawing_order, self).copy(cr, uid, id, default, context)    
   
    def print_pdf(self, cr, uid, ids, context):
        order_line_ids = []
        for id in ids:
            order = self.read(cr, uid, id, ['name','order_lines'],context=context)
            if len(ids) == 1:
                context['order_name'] = order['name']
            order_line_ids += order['order_lines']
            
        return self.pool.get('drawing.order.line').print_pdf(cr, uid, order_line_ids, context=context)

class drawing_step(osv.osv):
    _name = "drawing.step"
    _description = "Drawing Step"
    _columns = {
        'name': fields.char('Name', size=32),
        }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Name must be unique!'),
    ]

class drawing_order_line(osv.osv):
    _name = "drawing.order.line"
    _description = "Drawing Order Line"
    _rec_name = "drawing_file_name"
    
    _columns = {
        'order_id': fields.many2one('drawing.order','Drawing Order'),
        'product_id': fields.many2one('product.product','Sub Product'),
        'drawing_file_name': fields.char('Drawing PDF Name', size=64),
        'drawing_file': fields.function(utils.field_get_file, fnct_inv=utils.field_set_file, string="Drawing PDF", type="binary", multi="_get_file",),
        'step_ids': fields.many2many('drawing.step', string='Working Steps'),
        'company_id': fields.related('order_id','company_id',type='many2one',relation='res.company',string='Company'),
        'create_uid': fields.many2one('res.users','Creator',readonly=True),
        'create_date': fields.datetime('Creation Date', readonly=True),        
        'state': fields.selection([('draft','Draft'),('ready','Ready'),('confirmed','Confirmed'),('approved','Approved'),('rejected','Rejected'),('cancel','Cancelled')], 'Status', required=True, readonly=True),
        #order fields to show in the drawing files view
        'sale_product_ids': fields.related('order_id','sale_product_ids',type='many2many',relation='sale.product',rel='drawing_order_id_rel',id1='drawing_order_id',id2='id_id',
                                             string="MFG IDs",readonly=True, states={'draft':[('readonly',False)],'rejected':[('readonly',False)]}),
        'main_part_id': fields.related('order_id','main_part_id',type='many2one',relation='product.product',string='Main Product'),
                
    }
    
    _defaults = {
        'state': 'draft',
    }
   
    def _format_file_name(self, file_name):
        file_reserved_char = ('/','\\','<','>','*','?')
        new_file_name = file_name
        for char in file_reserved_char:
            new_file_name = new_file_name.replace(char, '-')
        return new_file_name
        
    def print_pdf(self, cr, uid, ids, context):
        attachment_obj = self.pool.get('ir.attachment')
        output = PdfFileWriter() 
        page_cnt = 0
        order = self.browse(cr, uid, ids[0], context=context)
        lines = self.browse(cr, uid, ids, context=context)
        for line in lines:
            if line.drawing_file_name and line.drawing_file_name.lower().endswith('.pdf'):                    
                file_ids = attachment_obj.search(
                    cr, uid, [('name', '=', 'drawing_file'),
                              ('res_id', '=', line.id),
                              ('res_model', '=', 'drawing.order.line')])
                if file_ids:
                    attach_file = attachment_obj.file_get(cr, uid, file_ids[0],context=context)
                    input = PdfFileReader(attach_file)
                    for page in input.pages: 
                        output.addPage(page)
                        page_cnt += 1
        if page_cnt > 0:
            full_path_temp = attachment_obj.full_path(cr, uid, 'temp')
#            file_name = self._format_file_name(order.name)
            file_name = "Drawing"
            if context.get('order_name'):
                file_name = '%s-%s'%(file_name, self._format_file_name(context.get('order_name')))
            full_file_name =  '%s/%s.pdf'%(full_path_temp, file_name,)
            outputStream = file(full_file_name, "wb") 
            output.write(outputStream) 
            outputStream.close()
            filedata = open(full_file_name,'rb').read().encode('base64')
            os.remove(full_file_name)
            return self.pool.get('file.down').download_data(cr, uid, "%s.pdf"%(file_name,), filedata, context)
        else:
            raise osv.except_osv(_("Error!"),'No PDF files were found!')
            return False
        
    def unlink(self, cr, uid, ids, context=None):
        #delete the attachments
        for id in ids:
            utils.field_set_file(self, cr, uid, id, 'drawing_file', None, {'unlink':True}, context=None)
        resu = super(drawing_order_line, self).unlink(cr, uid, ids, context=context)
        return resu

    def _check_file_name(self,cr,uid,ids,context=None):
        for record in self.browse(cr, uid, ids, context=context):
            same_file_name_ids = self.search(cr, uid, [('order_id','=',record.order_id.id),('id','!=',record.id),('drawing_file_name','=',record.drawing_file_name)],context=context)
            if same_file_name_ids:
                raise osv.except_osv(_('Error'), _('Dwaring file "%s" is duplicated under same order!')% (record.file_name,))
        return True
    
    _constraints = [
        (_check_file_name,
            'Drawing file name is duplicated under same order!',
            ['file_name'])
        ]

    def copy_data(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        line_data = self.browse(cr,uid,id,context=context)
        default.update({
            'drawing_file':line_data.drawing_file
        })
                
        return super(drawing_order_line, self).copy_data(cr, uid, id, default, context)        