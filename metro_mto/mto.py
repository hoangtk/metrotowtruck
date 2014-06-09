# -*- encoding: utf-8 -*-
from osv import fields,osv,orm
import openerp.addons.decimal_precision as dp
from openerp.tools import resolve_attr 
class attribute_set(orm.Model):
    _inherit = "attribute.set"
    _columns = {
        'type': fields.char('Type'),        
        'price_standard': fields.float('Standard Price', digits_compute= dp.get_precision('Product Price')),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True),        
        'weight_standard': fields.float('Standard Weight(kg)', digits_compute=dp.get_precision('Product Unit of Measure')),
        'notes': fields.text('Notes'),
        }
    def _get_currency_id(self, cr, uid, context):
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        return user.company_id.currency_id.id
        
    _defaults = {
        'currency_id': _get_currency_id,
    }  
class attribute_group(orm.Model):
    _inherit = "attribute.group"
    _columns = {
        'type': fields.char('Type'),
        'notes': fields.text('Notes'),
        }
    _sql_constraints = [
        ('name_model_uniq', 'unique (name, model_id, attribute_set_id)', 'The name of the group has to be unique for a given model''s attribute set !'),
    ]

class attribute_attribute(orm.Model):
    _inherit = "attribute.attribute"
    _columns = {
        'type': fields.char('Type'),
        'standard_option_id': fields.many2one('attribute.option', 'Standard Option', domain="[('attribute_id','=',id)]"),     
        'price_standard': fields.float('Standard Price', digits_compute= dp.get_precision('Product Price')),
        'weight_standard': fields.float('Standard Weight(kg)', digits_compute=dp.get_precision('Product Unit of Measure')),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True),
        'm2m_tags': fields.boolean('Many2Many Tags'),
        'notes': fields.text('Notes'),
        }
   
    def _get_currency_id(self, cr, uid, context):
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        return user.company_id.currency_id.id
        
    _defaults = {
        'currency_id': _get_currency_id,
        'm2m_tags': False
    }    
    def onchange_standard_option(self, cr, uid, ids, standard_option_id, context=None):
        vals = {'price_standard': 0, 'weight_standard': 0}
        if standard_option_id and standard_option_id > 0:
            data = self.pool.get('attribute.option').read(cr, uid, [standard_option_id], ['price','weight'],context=context)
            vals.update({'price_standard': data[0]['price'], 'weight_standard': data[0]['weight']})
        return {'value':vals}
    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not len(ids):
            return []
        def _name_get(d):
            name = d.get('name','')
            type = d.get('attribute_type',False)
            if type and type == 'select':
                #get the standard option name
                s_opt_id = d.get('standard_option_id')
                if s_opt_id:
                    name = '%s [%s]' % (name,s_opt_id.name)
            #add the price and weight
            price = d.get('price_standard',0.0)
            weight = d.get('weight_standard',0.0)
            if price > 0:
                name = '%s [$%s]' % (name,price)
            if weight > 0:
                name = '%s [%s]' % (name,weight)
            return (d['id'], name)

        result = []
        for attr in self.browse(cr, user, ids, context=context):
            mydict = {
                      'id': attr.id,
                      'name': attr.name,
                      'attribute_type': attr.attribute_type,
                      'standard_option_id': attr.standard_option_id,
                      'price_standard': attr.price_standard,
                      'weight_standard': attr.weight_standard
                      }
            result.append(_name_get(mydict))
        return result        
   
class attribute_option(orm.Model):
    _inherit = "attribute.option"
    _columns = {
        'price': fields.float('Price', digits_compute= dp.get_precision('Product Price')),
        'weight': fields.float('Weight(kg)', digits_compute=dp.get_precision('Product Unit of Measure')),
    }
    
    _sql_constraints = [
        ('name_attribute_uniq', 'unique (name, attribute_id)', 'The name of the option has to be unique for a given attribute !'),
    ]

    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not len(ids):
            return []

        result = []
        for opt in self.browse(cr, user, ids, context=context):
            name = opt.name
            price_str = ''
            weight_str = ''
            if opt.price and opt.price != 0:
                price_str = '%s%s%s'%((opt.price > 0 and '+' or '-'),opt.attribute_id.currency_id.symbol,abs(opt.price))
            if opt.weight and opt.weight != 0:
                weight_str = '%s%skg'%((opt.weight > 0 and '+' or '-'),abs(opt.weight))
            
            if price_str != '' or weight_str != '':                    
                if weight_str != '':
                    weight_str = '%s%s'%((price_str != '') and "," or "",weight_str)
                name = '%s(%s%s)'%(name,price_str,weight_str)
            result.append((opt.id,name))
        return result     
    def write(self, cr, user, ids, vals, context=None):
        resu = super(attribute_option, self).write(cr, user, ids, vals, context)
        if vals.has_key('price') or vals.has_key('weight'):
            #update the associated attribute stand price and weight
            attr_vals = {}
            if vals.has_key('price'):
                attr_vals.update({'price_standard': vals['price']})
            if vals.has_key('weight'):
                attr_vals.update({'weight_standard': vals['weight']})
            attr_obj = self.pool.get('attribute.attribute')
            for id in ids:
                attr_ids = attr_obj.search(cr, user, [('standard_option_id','=',id)],context=context)
                attr_obj.write(cr, user, attr_ids, attr_vals, context=context)
        return resu

from tools.translate import translate
from lxml import etree

class mto_design(osv.osv):
    _name = "mto.design"
    _inherits = {'product.product': 'product_id'}
    _columns = {
        'design_tmpl_id': fields.many2one('attribute.set', 'Template', domain=[('type','=','design')], required=True),
        'product_id': fields.many2one('product.product', 'Product', required=True, ondelete="restrict", select=True),       
    }    
    def _attr_grp_ids(self, cr, uid, ids, field_names, arg=None, context=None):
        res = {}
        for product in self.browse(cr, uid, ids, context=context):
            product_attr_groups = [ag.id for ag in product.design_tmpl_id.attribute_group_ids]
            res[product.id] = product_attr_groups
        return res
    
    def open_designment(self, cr, uid, ids, context=None):
        ir_model_data_obj = self.pool.get('ir.model.data')
        ir_model_data_id = ir_model_data_obj.search(cr, uid, [['model', '=', 'ir.ui.view'], ['name', '=', 'mto_design_form_view']], context=context)
        if ir_model_data_id:
            res_id = ir_model_data_obj.read(cr, uid, ir_model_data_id, fields=['res_id'])[0]['res_id']
        grp_ids = self._attr_grp_ids(cr, uid, [ids[0]], [], None, context)[ids[0]]
        ctx = {'open_attributes': True, 'attribute_group_ids': grp_ids}

        return {
            'name': 'Designment',
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [res_id],
            'res_model': self._name,
            'context': ctx,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'res_id': ids and ids[0] or False,
        }

    def _fix_size_bug(self, cr, uid, result, context=None):
    #When created a field text dynamicaly, its size is limited to 64 in the view.
    #The bug is fixed but not merged
    #https://code.launchpad.net/~openerp-dev/openerp-web/6.1-opw-579462-cpa/+merge/128003
    #TO remove when the fix will be merged
        for field in result['fields']:
            if result['fields'][field]['type'] == 'text':
                if 'size' in result['fields'][field]: del result['fields'][field]['size']
        return result    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}

        def translate_view(source):
            """Return a translation of type view of source."""
            return translate(
                cr, None, 'view', context.get('lang'), source
            ) or source

        result = super(mto_design, self).fields_view_get(cr, uid, view_id,view_type,context,toolbar=toolbar, submenu=submenu)
        
        if view_type == 'form' and context.get('attribute_group_ids'):
            eview = etree.fromstring(result['arch'])
            #for the usage with existing notebook by name 'attributes_notebook', and the position by 'attributes_placeholder'
            notebook = eview.xpath("//notebook[@string='attributes_notebook']")[0]
            attributes_notebook, toupdate_fields = self.pool.get('attribute.attribute')._build_attributes_notebook(cr, uid, context['attribute_group_ids'], context=context, notebook=notebook, attr_holder_name='attributes_placeholder')
            result['fields'].update(self.fields_get(cr, uid, toupdate_fields, context))
            '''
            #for the usage with new notebook
            attributes_notebook, toupdate_fields = self.pool.get('attribute.attribute')._build_attributes_notebook(cr, uid, context['attribute_group_ids'], context=context)
            result['fields'].update(self.fields_get(cr, uid, toupdate_fields, context))
            placeholder = eview.xpath("//separator[@string='attributes_placeholder']")[0]
            placeholder.getparent().replace(placeholder, attributes_notebook)
            '''
            result['arch'] = etree.tostring(eview, pretty_print=True)
            result = self._fix_size_bug(cr, uid, result, context=context)
        return result    
    def save_and_close_design(self, cr, uid, ids, context=None):
        return {'type': 'ir.actions.act_window_close'}
    
    def onchange_template(self, cr, uid, ids, design_tmpl_id, context=None):
        vals = {'list_price': 0, 'weight': 0}
        if design_tmpl_id and design_tmpl_id > 0:
            data = self.pool.get('attribute.set').read(cr, uid, [design_tmpl_id], ['price_standard','weight_standard'],context=context)
            vals.update({'list_price': data[0]['price_standard'], 'weight': data[0]['weight_standard']})
        return {'value':vals}
                    
    def create(self, cr, uid, data, context=None):        
        attr_set_id = data['design_tmpl_id']
        attr_set = self.pool.get("attribute.set").browse(cr, uid, attr_set_id, context=context)
        #set the selection parameter's standard option as the default value 
        for grp in attr_set.attribute_group_ids:
            for attr in grp.attribute_ids:
                if attr.attribute_type == "select" and attr.standard_option_id:
                    data.update({attr.name:attr.standard_option_id.id})

        resu = super(mto_design, self).create(cr, uid, data, context)
        return resu
    def write(self, cr, uid, ids, vals, context=None):        
        resu = super(mto_design, self).write(cr, uid, ids, vals, context=context)
        self.update_price(cr, uid, ids, context)
        return resu
    def update_price(self, cr, uid, ids, context=None):
        #update the price and weight by  the selected options
        designs = self.browse(cr, uid, ids, context=context)
        for design in designs:
            price_total = 0
            weight_total = 0
            for grp in design.design_tmpl_id.attribute_group_ids:
                for attr in grp.attribute_ids:
                    price = 0
                    weight = 0
                    if attr.attribute_type == "select":
                        price = resolve_attr(design,'%s.price'%(attr.name))
                        weight = resolve_attr(design,'%s.weight'%(attr.name))
                    elif attr.attribute_type == "multiselect":
                        options = resolve_attr(design,attr.name)
                        for opt in options:
                            price = price + resolve_attr(opt,'price')
                            weight = weight + resolve_attr(opt,'weight')
                        print '111'
#                    elif attr.attribute_type == "boolean":
#                        is_selected = resolve_attr(design,attr.name)
#                        if is_selected:
#                            price = attr.price_standard
#                            weight = attr.weight_standard
#                    else:
                    price_total = price_total + price
                    weight_total = weight_total + weight
            price_total = design.design_tmpl_id.price_standard + price_total
            weight_total = design.design_tmpl_id.weight_standard + weight_total
            cr.execute("""update product_template set
                    list_price=%s, weight=%s where id=%s""", (price_total, weight_total, design.product_id.product_tmpl_id.id))
       