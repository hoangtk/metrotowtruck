# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-TODAY OpenERP S.A. <http://www.openerp.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
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

import re
from osv import fields, osv
import tools
from tools.translate import _
from openerp.addons.metro_purchase.purchase import deal_args
class product_sequence(osv.osv):
	_name = "product.sequence"
	_rec_name = "prefix"
	_columns = {
		'prefix': fields.integer('Prefix', required=True),
		'suffix': fields.char('Suffix', required=True, size=128),
		'separator': fields.char('Separator', size=2, required=True),
		'active': fields.boolean('Active'),
	}
	_defaults = {
        'active': lambda *a: False,
	}

	def create(self, cr, uid, vals, context=None):
		if context is None:
			context = {}
		if vals.get('active') and vals['active']:
			act_rec = self.search(cr, uid, [('active', '=', True)])
			if act_rec:
				raise osv.except_osv(_('Warning !'), _('You should make only one sequence active'))
		return super(product_sequence, self).create(cr, uid, vals, context)
	
	def write(self, cr, uid, ids, vals, context=None):
		if context is None:
			context = {}
		if vals.get('active') and vals['active']:
			act_rec = self.search(cr, uid, [('active', '=', True), ('id', 'not in', ids)])
			if act_rec:
				raise osv.except_osv(_('Warning !'), _('You should make only one sequence active'))
		return super(product_sequence, self).write(cr, uid, ids, vals, context=context)
	
product_sequence()


class product_attribute_category(osv.osv):
    _inherit = "product.category"
    _columns = {    
        'attribute' : fields.many2many('product.attribute', 
            'prod_categ_attribute_rel', 'category_id', 'attribute_id', 
            'Attributes'
        ),
    }
product_attribute_category()

class product_attribute(osv.osv):
	_name = "product.attribute"
	_columns = {
		'name': fields.char('Name', size=512, required=True),
#        'attribute_id': fields.many2one('product.category', 'Person Name', select=True),
        'category_ids' : fields.many2many('product.category', 
            'prod_categ_attribute_rel', 'attribute_id', 'category_id', 
            'Categories'
        ),
	}
product_attribute()

class product_attribute_line(osv.osv):

	_name = "product.attribute.line"
	_columns = {
		'product_id': fields.many2one('product.product', 'Product'),
		'attribute_id': fields.many2one('product.attribute', 'Attribute'),
		'attr_value': fields.char('Value', size=128),
	}
	
	_sql_constraints =[('name_uniq', 'unique(product_id, attribute_id)','You can use an attribute on a Product once !')]
	
product_attribute_line()

class product_product(osv.osv):
	_inherit = "product.product"
	
	def generate_seq(self, cr, uid, context=None):
		prod_seq = self.pool.get('product.sequence')
		seq_id = prod_seq.search(cr, uid, [('active', '=', True)])
		code = False
		if seq_id:
			seq_rec = prod_seq.browse(cr, uid, seq_id[0])
			sequence = seq_rec.prefix
			prod_seq.write(cr, uid, seq_rec.id, {'prefix': sequence + 1})
			code = str(sequence) + str(seq_rec.separator) + str(seq_rec.suffix)
		return code
	
	_columns = {
		'attribute_line' : fields.one2many('product.attribute.line', 'product_id','Attributes'),
		'cn_name': fields.char(string=u'Chinese Name', size=128),
		'create_uid':  fields.many2one('res.users', 'Creator', readonly=True),
		'create_date': fields.datetime('Creation Date', readonly=True, select=True),
		'safe_qty': fields.float('Minimal Inventory'),
		'safe_warn': fields.boolean('Warn Inventory'),
		'loc_pos_code': fields.char('Storage Position Code',size=16),
		'is_print_barcode': fields.boolean('Print barcode label'),
	}
	_defaults = {
		'default_code': generate_seq,
		'safe_warn': True,
	}
#	_sql_constraints = [
#		('cn_name', 'unique (cn_name)', _('Product Chinese Name must be unique!'))
#	]    
	def _check_write_vals(self,cr,uid,vals,ids=None,context=None):
		if vals.get('default_code') and vals['default_code']:
			vals['default_code'] = vals['default_code'].strip()
			if ids:
				product_id = self.search(cr, uid, [('default_code', '=', vals['default_code']),('id','not in',ids)])
			else:
				product_id = self.search(cr, uid, [('default_code', '=', vals['default_code'])])
			if product_id:
				raise osv.except_osv(_('Error!'), _('Reference must be unique!'))
		if vals.get('cn_name'):
			vals['cn_name'] = vals['cn_name'].strip()
			if ids:
				product_id = self.search(cr, uid, [('cn_name', '=', vals['cn_name']),('id','not in',ids)])
			else:
				product_id = self.search(cr, uid, [('cn_name', '=', vals['cn_name'])])
			if product_id:
				raise osv.except_osv(_('Error!'), _('Product Chinese Name must be unique!'))
		if vals.get('name'):
			vals['name'] = vals['name'].strip()
			if ids:
				product_id = self.search(cr, uid, [('name', '=', vals['name']),('id','not in',ids)])
			else:
				product_id = self.search(cr, uid, [('name', '=', vals['name'])])
			if product_id:
				raise osv.except_osv(_('Error!'), _('Product Name must be unique!'))	
		return True	
	def create(self, cr, uid, vals, context=None):
		if context is None:
			context = {}
		self._check_write_vals(cr,uid,vals,context=context)
		return super(product_product, self).create(cr, uid, vals, context)
	
	def write(self, cr, uid, ids, vals, context=None):
		if context is None:
			context = {}
		self._check_write_vals(cr,uid,vals,ids=ids,context=context)
		return super(product_product, self).write(cr, uid, ids, vals, context=context)
	
	def get_sequence(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		code = self.generate_seq(cr, uid)
		self.write(cr, uid, ids, {'default_code': code})
		return True
	def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
		if not args:
			args = []
		if name:
			ids = self.search(cr, user, [('default_code','=',name)]+ args, limit=limit, context=context)
			if not ids:
				ids = self.search(cr, user, [('ean13','=',name)]+ args, limit=limit, context=context)
			if not ids:
				ids = self.search(cr, user, [('cn_name','=',name)]+ args, limit=limit, context=context)
			if not ids:
				# Do not merge the 2 next lines into one single search, SQL search performance would be abysmal
				# on a database with thousands of matching products, due to the huge merge+unique needed for the
				# OR operator (and given the fact that the 'name' lookup results come from the ir.translation table
				# Performing a quick memory merge of ids in Python will give much better performance
				ids = set()
				ids.update(self.search(cr, user, args + [('default_code',operator,name)], limit=limit, context=context))
				if not limit or len(ids) < limit:
					# we may underrun the limit because of dupes in the results, that's fine
					ids.update(self.search(cr, user, args + [('name',operator,name)], limit=(limit and (limit-len(ids)) or False) , context=context))
				if not limit or len(ids) < limit:
					ids.update(self.search(cr, user, args + [('cn_name',operator,name)], limit=(limit and (limit-len(ids)) or False) , context=context))
				ids = list(ids)
			if not ids:
				ptrn = re.compile('(\[(.*?)\])')
				res = ptrn.search(name)
				if res:
					ids = self.search(cr, user, [('default_code','=', res.group(2))] + args, limit=limit, context=context)
		else:
			ids = self.search(cr, user, args, limit=limit, context=context)
		result = self.name_get(cr, user, ids, context=context)
		return result
	def name_get(self, cr, user, ids, context=None):
		if context is None:
			context = {}
		if isinstance(ids, (int, long)):
			ids = [ids]
		if not len(ids):
			return []
		def _name_get(d):
			name = d.get('name','')
			code = d.get('default_code',False)
			if code:
				name = '[%s] %s' % (code,name)
			cn_name = d.get('cn_name',False)
			if cn_name:
				name = '%s, %s' % (name,cn_name)
			if d.get('variants'):
				name = name + ' - %s' % (d['variants'],)
			return (d['id'], name)

		partner_id = context.get('partner_id', False)

		result = []
		for product in self.browse(cr, user, ids, context=context):
			sellers = filter(lambda x: x.name.id == partner_id, product.seller_ids)
			if sellers:
				for s in sellers:
					mydict = {
							  'id': product.id,
							  'name': s.product_name or product.name,
							  'cn_name': product.cn_name,
							  'default_code': s.product_code or product.default_code,
							  'variants': product.variants
							  }
					result.append(_name_get(mydict))
			else:
				mydict = {
						  'id': product.id,
						  'name': product.name,
						  'cn_name': product.cn_name,
						  'default_code': product.default_code,
						  'variants': product.variants
						  }
				result.append(_name_get(mydict))
		return result	
	
	def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
		#deal the 'date' datetime field query
		new_args = deal_args(self,args)
		#get the search result		
		ids = super(product_product,self).search(cr, user, new_args, offset, limit, order, context, count)
		
#		qty_available
		#add the available restriction
#		if context and context.get('inv_warn_restrict'):
#			ids = super(product_product,self).search(cr, user, new_args, offset, None, order, context, count)
#			qtys = self.read(cr,user,ids,['virtual_available','safe_qty'],context=context)
##			list: [{'product_tmpl_id': 10, 'virtual_available': -255.0, 'id': 10}, {'product_tmpl_id': 26, 'virtual_available': 0.0, 'id': 26}, {'product_tmpl_id': 35, 'virtual_available': 600.0, 'id': 35}]
#			new_ids = []
#			for qty in qtys:
#				if qty['virtual_available'] < qty['safe_qty']:
#					new_ids.append(qty['id'])	
#			ids = super(product_product,self).search(cr, user, [('id','in',new_ids)], offset, limit, order, context, count)		
		#add  the onhand query
#		for arg in args:
#			fld_name = arg[0]
#			if fld_name == 'qty_available':
#				ids = super(product_product,self).search(cr, user, new_args, offset, None, order, context, count)
#				qtys = self.read(cr,user,ids,[fld_name],context=context)
#				new_ids = []
#				for qty in qtys:
#					if eval('%s%s%s'%(qty[fld_name],arg[1],arg[2])):
#						new_ids.append(qty['id'])	
#				ids = super(product_product,self).search(cr, user, [('id','in',new_ids)], offset, limit, order, context, count)	
				
		return ids
	def copy(self, cr, uid, id, default=None, context=None):
		if not default:
			default = {}
		default.update({
			'default_code':self.generate_seq(cr, uid),
			'cn_name':'%s(%s)'%(self.read(cr,uid,id,['cn_name'])['cn_name'],tools.ustr('副本')),
		})
		return super(product_product, self).copy(cr, uid, id, default, context)		
	def print_barcode(self,cr,uid,ids,context=None):
		self.write(cr,uid,ids,{'is_print_barcode':context.get("print_flag")})
		return True
#	def onchange_name(self, cr, uid, ids, value, context):
#		prods = self.search(cr, uid, [('name', 'like', value),('id','not in',ids)])
#		if prods:
#			for prod in prods
#			
#		res = {}
#		res['warning'] = {'title': _('Warning!'), 'message': _('Selected Unit of Measure does not belong to the same category as the product Unit of Measure.')}
#		return res
		
product_product()

#	_sql_constraints = [
#		('name', 'unique (name)', _('Product Name must be unique!'))
#	] 

class product_template(osv.osv):
    _inherit = "product.template"

    _columns = {
        'name': fields.char('Name', size=128, required=True, translate=False, select=True),
        }

    _defaults = {
        'type' : 'product',
    }    