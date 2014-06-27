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
from openerp.addons.stock.product import product_product as stock_product
import openerp.addons.decimal_precision as dp
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
	
	def _get_move_products(self, cr, uid, ids, context=None):
		res = set()
		move_obj = self.pool.get("stock.move")
		for move in move_obj.browse(cr, uid, ids, context=context):
			res.add(move.product_id.id)
		return res

	def rpc_product_available(self, cr, uid, ids, field_names=None, arg=False, context=None):
		res = self._product_available(cr, uid, ids, field_names, arg, context)
		rpc_res = {}
		#convert the ket of dictory yo string, since the dumps() method in below code only allow the string key in dictory.
		#openerp/service/wsgi_server.py
		#response = xmlrpclib.dumps((result,), methodresponse=1, allow_none=False, encoding=None)
		for id in ids:
			rpc_res['%s'%id] = res[id]
		return rpc_res
	def _product_partner_ref(self, cr, uid, ids, name, arg, context=None):
		res = {}
		if context is None:
			context = {}
		names = self.name_get(cr, uid, ids, context=context)
		for name in names:
			res[name[0]] = name[1]
		return res			
	_columns = {
		'attribute_line' : fields.one2many('product.attribute.line', 'product_id','Attributes'),
		'cn_name': fields.char(string=u'Chinese Name', size=128, track_visibility='onchange'),
		'create_uid':  fields.many2one('res.users', 'Creator', readonly=True),
		'create_date': fields.datetime('Creation Date', readonly=True, select=True),
		'safe_qty': fields.float('Minimal Inventory'),
		'safe_warn': fields.boolean('Warn Inventory'),
		'loc_pos_code': fields.char('Storage Position Code',size=16),
		'is_print_barcode': fields.boolean('Print barcode label'),
		'mfg_standard': fields.char(string=u'Manufacture Standard', size=32, help="The manufacture standard name, like GB/T5782-86"),
		'default_code' : fields.char('Internal Reference', size=64, select=True, required=True),
		'partner_ref' : fields.function(_product_partner_ref, type='char', string='Customer ref'),
        'part_no_external': fields.char(string=u'External Part#', size=32, help="The external part#, may be from engineering, purchase..."),
		'qty_available': fields.function(stock_product._product_available, multi='qty_available',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Quantity On Hand',
			help="Current quantity of products.\n"
				 "In a context with a single Stock Location, this includes "
				 "goods stored at this Location, or any of its children.\n"
				 "In a context with a single Warehouse, this includes "
				 "goods stored in the Stock Location of this Warehouse, or any "
				 "of its children.\n"
				 "In a context with a single Shop, this includes goods "
				 "stored in the Stock Location of the Warehouse of this Shop, "
				 "or any of its children.\n"
				 "Otherwise, this includes goods stored in any Stock Location "
				 "with 'internal' type.",
                 store = {'stock.move': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10),
						'material.request.line': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10)}
				 ),
		'virtual_available': fields.function(stock_product._product_available, multi='qty_available',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Forecasted Quantity',
			help="Forecast quantity (computed as Quantity On Hand "
				 "- Outgoing + Incoming)\n"
				 "In a context with a single Stock Location, this includes "
				 "goods stored in this location, or any of its children.\n"
				 "In a context with a single Warehouse, this includes "
				 "goods stored in the Stock Location of this Warehouse, or any "
				 "of its children.\n"
				 "In a context with a single Shop, this includes goods "
				 "stored in the Stock Location of the Warehouse of this Shop, "
				 "or any of its children.\n"
				 "Otherwise, this includes goods stored in any Stock Location "
				 "with 'internal' type.",
                 store = {'stock.move': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10),
						'material.request.line': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10)}
                 ),
		'incoming_qty': fields.function(stock_product._product_available, multi='qty_available',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Incoming',
			help="Quantity of products that are planned to arrive.\n"
				 "In a context with a single Stock Location, this includes "
				 "goods arriving to this Location, or any of its children.\n"
				 "In a context with a single Warehouse, this includes "
				 "goods arriving to the Stock Location of this Warehouse, or "
				 "any of its children.\n"
				 "In a context with a single Shop, this includes goods "
				 "arriving to the Stock Location of the Warehouse of this "
				 "Shop, or any of its children.\n"
				 "Otherwise, this includes goods arriving to any Stock "
				 "Location with 'internal' type.",
                 store = {'stock.move': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10),
						'material.request.line': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10)}
                 ),
		'outgoing_qty': fields.function(stock_product._product_available, multi='qty_available',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Outgoing',
			help="Quantity of products that are planned to leave.\n"
				 "In a context with a single Stock Location, this includes "
				 "goods leaving this Location, or any of its children.\n"
				 "In a context with a single Warehouse, this includes "
				 "goods leaving the Stock Location of this Warehouse, or "
				 "any of its children.\n"
				 "In a context with a single Shop, this includes goods "
				 "leaving the Stock Location of the Warehouse of this "
				 "Shop, or any of its children.\n"
				 "Otherwise, this includes goods leaving any Stock "
				 "Location with 'internal' type.",
                 store = {'stock.move': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10),
						'material.request.line': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10)}
                 ),		
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
			if d.get('mfg_standard'):
				name = name + '[%s]' % (d['mfg_standard'],)
				
			return (d['id'], name)

		partner_id = context.get('partner_id', False)

		result = []
		for product in self.browse(cr, user, ids, context=context):
			if product.id <= 0:
				result.append((product.id,''))
				continue
			sellers = filter(lambda x: x.name.id == partner_id, product.seller_ids)
			if sellers:
				for s in sellers:
					mydict = {
							  'id': product.id,
							  'name': s.product_name or product.name,
							  'cn_name': product.cn_name,
							  'default_code': s.product_code or product.default_code,
							  'variants': product.variants,
							  'mfg_standard': product.mfg_standard
							  }
					result.append(_name_get(mydict))
			else:
				mydict = {
						  'id': product.id,
						  'name': product.name,
						  'cn_name': product.cn_name,
						  'default_code': product.default_code,
						  'variants': product.variants,
						  'mfg_standard': product.mfg_standard
						  }
				result.append(_name_get(mydict))
		return result	
	
	def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
		#deal the 'date' datetime field query
		new_args = deal_args(self,args)
		for arg in new_args:
			#add the category improving
			if arg[0] == 'categ_id' and arg[1] == '=' and isinstance(arg[2], (int,long)):
				idx = new_args.index(arg)
				new_args.remove(arg)
				new_args.insert(idx, [arg[0],'child_of',arg[2]])

			#add the multi part# query
			if arg[0] == 'default_code' and arg[1] == 'in' and isinstance(arg[2], type(u'aaa')):
				part_nos = []
				for part_no in arg[2].split(','):
					part_nos.append(part_no.strip())
				idx = new_args.index(arg)
				new_args.remove(arg)
				new_args.insert(idx, [arg[0],arg[1],part_nos])
							
		#get the search result		
		ids = super(product_product,self).search(cr, user, new_args, offset, limit, order, context, count)

		#add the available restriction
		if context and context.get('inv_warn_restrict'):
			ids = super(product_product,self).search(cr, user, new_args, offset, None, order, context, count)
			qtys = self.read(cr,user,ids,['qty_available','safe_qty'],context=context)
#			list: [{'product_tmpl_id': 10, 'virtual_available': -255.0, 'id': 10}, {'product_tmpl_id': 26, 'virtual_available': 0.0, 'id': 26}, {'product_tmpl_id': 35, 'virtual_available': 600.0, 'id': 35}]
			new_ids = []
			for qty in qtys:
				if qty['qty_available'] < qty['safe_qty']:
					new_ids.append(qty['id'])	
			ids = super(product_product,self).search(cr, user, [('id','in',new_ids)], offset, limit, order, context, count)		
				
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

	def button_approve(self, cr, uid, ids, context=None):
		#state will be changed to 'sellable', purchase_ok=1, sale_ok=1, active=1
		self.write(cr,uid,ids,{'state':'sellable','purchase_ok':1,'sale_ok':1,'active':1},context=context)
	def button_eol(self, cr, uid, ids, context=None):
		#state will be changed to 'end', purchase_ok=0, sale_ok=0
		self.write(cr,uid,ids,{'state':'end','purchase_ok':0,'sale_ok':0},context=context)
	def button_obsolete(self, cr, uid, ids, context=None):
		#state will be changed to 'obsolete', purchase_ok=0, sale_ok=0, active=0
		self.write(cr,uid,ids,{'state':'obsolete','purchase_ok':0,'sale_ok':0,'active':0},context=context)
	def button_draft(self, cr, uid, ids, context=None):
		#state will be changed to 'sellable', purchase_ok=1, sale_ok=1, active=1
		self.write(cr,uid,ids,{'state':'draft','purchase_ok':0,'sale_ok':0,'active':1},context=context)
				
product_product()

#	_sql_constraints = [
#		('name', 'unique (name)', _('Product Name must be unique!'))
#	] 

class product_template(osv.osv):
	_inherit = "product.template"

	_columns = {
        'name': fields.char('Name', size=128, required=True, translate=False, select=True, track_visibility='onchange'),   
		'state': fields.selection([('draft', 'In Development'),
			('sellable','Normal'),
			('end','End of Lifecycle'),
			('obsolete','Obsolete')], 'Status', track_visibility='onchange'), 
		'list_price': fields.float('Sale Price', digits_compute=dp.get_precision('Product Price'), track_visibility='onchange', help="Base price to compute the customer price. Sometimes called the catalog price."),
		'standard_price': fields.float('Cost', digits_compute=dp.get_precision('Product Price'), track_visibility='onchange', help="Cost price of the product used for standard stock valuation in accounting and used as a base price on purchase orders.", groups="base.group_user"),			     
        }

	_defaults = {
        'type' : 'product',
		'purchase_ok':False,
		'sale_ok':False,
		'state':'draft'        
    }