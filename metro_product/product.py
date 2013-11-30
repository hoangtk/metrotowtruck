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
        'attribute_id': fields.many2one('product.category', 'Person Name', select=True),
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
		'create_uid':  fields.many2one('res.users', 'Creator')
	}
	_defaults = {
		'default_code': generate_seq,
	}
    
	def create(self, cr, uid, vals, context=None):
		if context is None:
			context = {}
		if vals.get('default_code') and vals['default_code']:
			product_id = self.search(cr, uid, [('default_code', '=', vals['default_code'])])
			if product_id:
				raise osv.except_osv(_('Warning !'), _('Reference must be unique!'))
		return super(product_product, self).create(cr, uid, vals, context)
	
	def write(self, cr, uid, ids, vals, context=None):
		if context is None:
			context = {}
		if vals.get('default_code') and vals['default_code']:
			product_id = self.search(cr, uid, [('default_code', '=', vals['default_code'])])
			if product_id:
				raise osv.except_osv(_('Warning !'), _('Reference must be unique!'))
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
product_product()


