# -*- encoding: utf-8 -*-
from osv import fields,osv
from openerp import netsvc
import openerp.addons.decimal_precision as dp
from openerp.addons.metro.utils import set_seq_o2m
class sale_order(osv.osv):
    _inherit="sale.order"
    _name="sale.order"
    
    def _order_line_with_configs(self, cr, uid, ids, field_names, args, context=None):
        res = {}
        for order in self.browse(cr, uid, ids, context=context):
            design_line_ids = [line.id for line in order.order_line if line.mto_design_id]
            res[order.id] = design_line_ids
        return res
    
    _columns={
        'checkbox':fields.boolean("Include Payment Information"),
        'payinfo_id':fields.many2one("sale.payinfo",string="Payment Information"),
        'contact_log_ids': fields.many2many('contact.log', 'oppor_contact_log_rel','oppor_id','log_id',string='Contact Logs', ),
        #used by PDF  
        'order_line_with_config': fields.function(_order_line_with_configs, type='one2many', relation='sale.order.line', fields_id='order_id', string='Lines with Configuration')
    }
    _defaults={'checkbox':True}
    _order = 'id desc'
    
    def default_get(self, cr, uid, fields, context=None):
        vals = super(sale_order, self).default_get(cr, uid, fields, context=context)
        vals['company_id'] = company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        return vals

    def onchange_partner_id(self, cr, uid, ids, part, context=None):
        resu = super(sale_order,self).onchange_partner_id(cr, uid, ids, part, context)
        if not part:
            return resu

        part = self.pool.get('res.partner').browse(cr, uid, part, context=context)
        #if the chosen partner is not a company and has a parent company, use the parent to choose the delivery, the 
        #invoicing addresses and all the fields related to the partner.
        if part.parent_id and not part.is_company:
            part = part.parent_id
        if part.country_id and part.country_id.currency_id:
            pricelist_obj = self.pool.get('product.pricelist')
            pricelist_ids = pricelist_obj.search(cr, uid, [('currency_id', '=', part.country_id.currency_id.id)], context=context)
            if pricelist_ids:
                resu['value']['pricelist_id'] = pricelist_ids[0]  
        return resu
            
    def get_report_name(self, cr, uid, id, rpt_name, context=None):
        state = self.pool.get('sale.order').read(cr, uid, id, ['state'],context=context)['state']
        if state == 'draft' or state == 'sent':
            return "Quote"
        else:
            return "SalesOrder"
        
    def print_quotation(self, cr, uid, ids, context=None):
        '''
        This function prints the sales order and mark it as sent, so that we can see more easily the next step of the workflow
        '''
        assert len(ids) == 1, 'This option should only be used for a single id at a time'
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'sale.order', ids[0], 'quotation_sent', cr)
        datas = {
                 'model': 'sale.order',
                 'ids': ids,
                 'form': self.read(cr, uid, ids[0], context=context),
        }
        return {'type': 'ir.actions.report.xml', 'report_name': 'sale.agreement', 'datas': datas, 'nodestroy': True}    
                       
    def create(self, cr, uid, data, context=None):        
        set_seq_o2m(cr, uid, data.get('order_line'), context=context)
        return super(sale_order, self).create(cr, uid, data, context)
        
    def write(self, cr, uid, ids, vals, context=None):      
        set_seq_o2m(cr, uid, vals.get('order_line'), 'sale_order_line', 'order_id', ids[0], context=context)  
        return super(sale_order, self).write(cr, uid, ids, vals, context=context)
                    
sale_order()

class sale_order_line(osv.osv):
    _inherit = 'sale.order.line'
    _columns = {
        'mto_design_id': fields.many2one('mto.design', 'Configuration'),
        'serial_ids': fields.many2many('mttl.serials', 'sale_serial_rel','line_id','serials_id',string='Serials',),        
        'price_unit': fields.float('Unit Price', required=True, digits_compute= dp.get_precision('Product Price Sale'), readonly=True, states={'draft': [('readonly', False)]}),
        #config changing dummy field
        'config_changed':fields.function(lambda *a,**k:{}, type='boolean',string="Config Changed",),        
    }
        
    def copy_data(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'mto_design_id': None,
            'serial_ids': None,
        })         
        return super(sale_order_line, self).copy_data(cr, uid, id, default, context=context)     
           
    def onchange_config(self, cr, uid, ids, config_id, context=None):
        val= {}
        if config_id:
            config = self.pool.get('mto.design').browse(cr, uid, config_id, context=context)
            val = {'product_id':config.product_id.id,
                   'price_unit':config.list_price,
                   'th_weight':config.weight,
                   'name':'%s(%s)'%(config.product_id.name, config.name),
                   'config_changed':True}    
        return {'value':val}
    
    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0,
            uom=False, qty_uos=0, uos=False, name='', partner_id=False,
            lang=False, update_tax=True, date_order=False, packaging=False,
            fiscal_position=False, flag=False, context=None):

        res=super(sale_order_line, self).product_id_change(cr, uid, ids, pricelist, product, qty,
            uom, qty_uos, uos, name, partner_id,
            lang, update_tax, date_order, packaging=packaging, fiscal_position=fiscal_position, flag=flag, context=context)
        
        if context.get('config_changed'):
            #if the product changing is triggered by the config changing, then do not change the price and weight
            fields_remove = ['price_unit', 'th_weight', 'name']
            for field in fields_remove:
                if res['value'].has_key(field):
                    res['value'].pop(field)
            res['value']['config_changed'] = False
        
        return res
            
    def create(self, cr, uid, vals, context=None):
        new_id = super(sale_order_line, self).create(cr, uid, vals, context)
        #auto copy the common mto design to a new design
        line = self.browse(cr, uid, new_id, context=context)
        if line.mto_design_id and line.mto_design_id.type == 'common':
            config_obj = self.pool.get('mto.design')
            name = '%s-%s-%s'%(line.mto_design_id.name, line.order_id.name, line.sequence)
            config_new_id = config_obj.copy(cr, uid, line.mto_design_id.id, context=context)
            config_obj.write(cr, uid, config_new_id, {'name':name, 'type':'sale'}, context=context)
            self.write(cr, uid, line.id, {'mto_design_id': config_new_id}, context=context)
        return new_id
        
    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        config_old_datas = self.read(cr, uid, ids, ['mto_design_id'], context=context)            
        resu = super(sale_order_line, self).write(cr, uid, ids, vals, context=context)
        #deal the mto_design_id     
        if 'mto_design_id' in vals:
            lines = self.browse(cr, uid, ids, context)
            config_olds = {}
            for config in config_old_datas:
                config_old_id = config['mto_design_id'] and config['mto_design_id'][0] or None
                config_olds[config['id']] = config_old_id
            config_obj = self.pool.get('mto.design')
            for line in lines:
                config_old_id = config_olds[line.id]
                #clear config, #assign new config,  #change config
                if not line.mto_design_id or not config_old_id or line.mto_design_id.id != config_old_id:
                    if config_old_id:
                        #if old config is for sale, then delete it
                        config_old_type = config_obj.read(cr, uid, config_old_id, ['type'], context=context)                        
                        if config_old_type['type'] == 'sale':
                            config_obj.unlink(cr, uid, config_old_id, context=context)
                    #if new config is common, then do copy
                    if line.mto_design_id and line.mto_design_id.type == 'common':                        
                        context['default_type'] = 'sale'
                        config_new_id = config_obj.copy(cr, uid, line.mto_design_id.id, context=context)
                        name = '%s-%s-%s'%(line.mto_design_id.name, line.order_id.name, line.sequence)
                        config_obj.write(cr, uid, config_new_id, {'name':name, 'type':'sale'}, context=context)     
                        self.write(cr, uid, line.id, {'mto_design_id': config_new_id})
                
        return resu
    
    def edit_config(self, cr, uid, ids, context=None):
        if not context.get('config_id'):
            return False
        return self.pool.get('mto.design').open_designment(cr, uid, context.get('config_id'), context=context)           
    
    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not len(ids):
            return []
        result = []
        for line in self.browse(cr, user, ids, context=context):
            result.append((line.id, '%s@%s'%(line.name, line.order_id.name)))
        return result    
    
class mto_design(osv.osv):
    _inherit = "mto.design"
    def _so_line_id(self, cr, uid, ids, field_names, args, context=None):
        res = dict.fromkeys(ids,None)
        for id in ids:
            so_ids = self.pool.get('sale.order.line').search(cr, uid, [('mto_design_id','=',id)])
            if so_ids:
                res[id] = so_ids[0]
        return res
    _columns = {'so_line_id': fields.function(_so_line_id, string='SO Line', type='many2one', relation='sale.order.line', store=True)}
    
class account_invoice(osv.osv):

    _inherit="account.invoice"
    _name="account.invoice"
    _columns={
        'check':fields.boolean("Include Payment Information"),
        'payinfo_id':fields.many2one("sale.payinfo",string="Payment Information"),
        'sale_order_ids': fields.many2many('sale.order', 'sale_order_invoice_rel', 'invoice_id', 'order_id', 'Sale Orders'),
    }
	
    def invoice_print(self, cursor, user, ids, context=None):
        res = super(account_invoice, self).invoice_print(cursor, user, ids, context)
        res['report_name']='account.invoice.metro'
        return res
    
    def get_report_name(self, cr, uid, id, rpt_name, context=None):
        if rpt_name is None or rpt_name != 'account.invoice.metro':
            return 'Invoice'
        inv = self.pool.get('account.invoice').read(cr, uid, id, ['number','origin'],context=context)
        if inv['origin'] and inv['origin'].startswith('SO'):
            #get the '0015' in 'Invoice SAJ/2014/0015'
            idx = inv['number'].find('/')
            inv_number = inv['number'][idx+6:]
            return 'Invoice_%s_%s.pdf'%(inv['origin'], inv_number)
        else:
            return "Invoice"
        
account_invoice()

class sale_payinfo(osv.osv):
    _name = "sale.payinfo"
    _columns = {
        'company_id':fields.many2one('res.company', string='Company', required=True, ondelete='cascade'),
        'name':fields.char('Name', size=64, required=True),
        'content': fields.text('Content', required=True),
    }
    
class res_company(osv.osv):
    _inherit="res.company"
    _name="res.company"
    _columns={
        'info':fields.text("Wire Transfer Information"),
        'sale_payinfo_ids':fields.one2many('sale.payinfo', 'company_id', 'Sale Payment Information')
    }   
        
res_company()
