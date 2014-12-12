# -*- encoding: utf-8 -*-
from osv import fields,osv
from openerp import netsvc
import openerp.addons.decimal_precision as dp

class sale_order(osv.osv):

    _inherit="sale.order"
    _name="sale.order"
    _columns={
        'checkbox':fields.boolean("Include Payment Information"),
        'payinfo_id':fields.many2one("sale.payinfo",string="Payment Information"),
        'contact_log_ids': fields.many2many('contact.log', 'oppor_contact_log_rel','oppor_id','log_id',string='Contact Logs', )  
    }
    _defaults={'checkbox':True}
    _order = 'id desc'
    
    def default_get(self, cr, uid, fields, context=None):
        vals = super(sale_order, self).default_get(cr, uid, fields, context=context)
        vals['company_id'] = company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        return vals
        
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
sale_order()

class sale_order_line(osv.osv):
    _inherit = 'sale.order.line'
    _columns = {
        'mto_design_id': fields.many2one('mto.design', 'Configuration'),
        'serial_ids': fields.many2many('mttl.serials', 'sale_serial_rel','line_id','serials_id',string='Serials',),        
        'price_unit': fields.float('Unit Price', required=True, digits_compute= dp.get_precision('Product Price Sale'), readonly=True, states={'draft': [('readonly', False)]}),
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
                   'name':'%s(%s)'%(config.product_id.name, config.name)}    
        return {'value':val}        
        
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
