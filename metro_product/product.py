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
	def _product_available(self, cr, uid, ids, field_names=None, arg=False, context=None):
		""" Finds the incoming and outgoing quantity of product.
		@return: Dictionary of values
		"""
		if not field_names:
			field_names = []
		if context is None:
			context = {}
		res = {}
		for id in ids:
			res[id] = {}.fromkeys(field_names, 0.0)
		for f in field_names:
			c = context.copy()
			#add the columns display on GUI for user sort and query
			if f in ('qty_available','qty_onhand'):
				c.update({ 'states': ('done',), 'what': ('in', 'out') })
			if f in ('virtual_available','qty_virtual'):
				c.update({ 'states': ('confirmed','waiting','assigned','done'), 'what': ('in', 'out') })
			if f in ('incoming_qty','qty_in'):
				c.update({ 'states': ('confirmed','waiting','assigned'), 'what': ('in',) })
			if f in ('outgoing_qty','qty_out'):
				c.update({ 'states': ('confirmed','waiting','assigned'), 'what': ('out',) })
			if f == 'qty_out_assigned':
				c.update({ 'states': ('assigned'), 'what': ('out',) })				
			stock = self.get_product_available(cr, uid, ids, context=c)
			for id in ids:
				res[id][f] = stock.get(id, 0.0)
		#update qty_out_available
		if 'qty_onhand' in field_names and 'qty_out_assigned' in field_names:
			for id in ids:
				res[id]['qty_out_available'] = res[id]['qty_onhand'] - res[id]['qty_out_assigned']
		
		return res		
	
	_columns = {
		'attribute_line' : fields.one2many('product.attribute.line', 'product_id','Attributes'),
		'cn_name': fields.char(string=u'Chinese Name', size=128, track_visibility='onchange'),
		'create_uid':  fields.many2one('res.users', 'Creator', readonly=True),
		'create_date': fields.datetime('Creation Date', readonly=True, select=True),
		'safe_qty': fields.float('Minimal Inventory'),
		'safe_warn': fields.boolean('Safe Warn'),
		'max_qty': fields.float('Maximal Inventory'),
		'property_prod_loc': fields.property('stock.location', type='many2one', relation='stock.location', string="Location", view_load=True, ),		
		'loc_pos_code': fields.char('Storage Position Code',size=16),
		'is_print_barcode': fields.boolean('Print barcode label'),
		'mfg_standard': fields.char(string=u'Manufacture Standard', size=32, help="The manufacture standard name, like GB/T5782-86"),
		'default_code' : fields.char('Internal Reference', size=64,readonly=True, select=True, required=True),
		'partner_ref' : fields.function(_product_partner_ref, type='char', string='Customer ref'),
        'part_no_external': fields.char(string=u'External Part#', size=32, help="The external part#, may be from engineering, purchase..."),
        'checked': fields.boolean('Checked', help="User can use this flag field to check the products, once you finish checking, once finish the checking and fixed data, then check it, you only need to check the items without this flag"),
        #add the field qty_onhand, qty_virtual, qty_in, qty_out, to store them into database, then user can sort and query them on GUI
        #they are corresponding to the original columns: qty_available, virtual_available, incoming_qty, outgoing_qty
        #replace the xml view with the new columns, and other program also read from the original qty function columns
		'qty_onhand': fields.function(_product_available, multi='qty_available',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Quantity On Hand',
             store = {'stock.move': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10),
					'material.request.line': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10)}
			 ),
		'qty_virtual': fields.function(_product_available, multi='qty_available',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Forecasted Quantity',
             store = {'stock.move': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10),
					'material.request.line': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10)}
             ),
		'qty_in': fields.function(_product_available, multi='qty_available',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Incoming',
             store = {'stock.move': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10),
					'material.request.line': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10)}
             ),
		'qty_out': fields.function(_product_available, multi='qty_available',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Outgoing',
             store = {'stock.move': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10),
					'material.request.line': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10)}
             ),
		'qty_out_assigned': fields.function(_product_available, multi='qty_available',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Outgoing Assigned',
             store = {'stock.move': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10),
					'material.request.line': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10)}
             ),	
		'qty_out_available': fields.function(_product_available, multi='qty_available',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Outgoing Available',
             store = {'stock.move': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10),
					'material.request.line': (_get_move_products, ['product_qty', 'location_id', 'location_dest_id', 'state'], 10)}
             ),	
		'qty_available': fields.function(_product_available, multi='qty_available',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Quantity On Hand(FUNC)',
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
				 "with 'internal' type."),
		'virtual_available': fields.function(_product_available, multi='qty_available',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Forecasted Quantity(FUNC)',
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
				 "with 'internal' type."),
		'incoming_qty': fields.function(_product_available, multi='qty_available',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Incoming(FUNC)',
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
				 "Location with 'internal' type."),
		'outgoing_qty': fields.function(_product_available, multi='qty_available',
			type='float',  digits_compute=dp.get_precision('Product Unit of Measure'),
			string='Outgoing(FUNC)',
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
				 "Location with 'internal' type."),			
	}
	_defaults = {
		'default_code': '/',
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
		
	#auto update order point by the product min/max qty fields
	def _orderpoint_update(self, cr, uid, ids, vals, context=None):
		if 'safe_qty' in vals or 'max_qty' in vals or 'property_prod_loc' in vals:
			wh_obj = self.pool.get('stock.warehouse')
			op_obj = self.pool.get('stock.warehouse.orderpoint')
			
			min_qty = 'safe_qty' in vals and vals['safe_qty'] or -1
			max_qty = 'max_qty' in vals and vals['max_qty'] or 0
			location_id = 'property_prod_loc' in vals and vals['property_prod_loc'] or -1
			upt_op_ids = []
			for prod in self.browse(cr, uid, ids, context=context):
				if location_id <= 0:
					location_id = prod.property_prod_loc
					if location_id:
						location_id = location_id.id
				if not prod.orderpoint_ids:
					#for new order point, must have min qty and loc, otherwise then miss it.
					if min_qty <= 0 or location_id <= 0:
						continue
					wh_ids = wh_obj.search(cr, uid, [('lot_stock_id','=',location_id)],context=context)
					op_vals = {'product_id':prod.id,
							'product_uom':prod.uom_id.id,
							'product_min_qty':min_qty, 
							'product_max_qty':max_qty,
							'warehouse_id':wh_ids and wh_ids[0] or False,
							'location_id':location_id,
							}
					op_obj.create(cr, uid, op_vals, context=context)
				else:
					upt_op_ids.append(prod.orderpoint_ids[0].id)
			#update the order point
			if upt_op_ids:
				upt_vals = {}
				if min_qty > 0:
					upt_vals.update({'product_min_qty':min_qty})
				if max_qty > 0:
					upt_vals.update({'product_max_qty':max_qty})
				if location_id > 0:
					upt_vals.update({'location_id':location_id})
				op_obj.write(cr, uid, upt_op_ids, upt_vals, context=context)
		return True
		
	def create(self, cr, uid, vals, context=None):
		if context is None:
			context = {}
		self._check_write_vals(cr,uid,vals,context=context)
		if vals.get('default_code','/')=='/':
			vals['default_code'] = self.generate_seq(cr, uid, context=context) # generate_seq  需要调用这个方法返回一个code
		new_id = super(product_product, self).create(cr, uid, vals, context)
		self._orderpoint_update(cr, uid, [new_id], vals, context)
		return new_id
	
	def write(self, cr, uid, ids, vals, context=None):
		if context is None:
			context = {}
		self._check_write_vals(cr,uid,vals,ids=ids,context=context)
		resu = super(product_product, self).write(cr, uid, ids, vals, context=context)
		self._orderpoint_update(cr, uid, ids, vals, context)
		return resu
	
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
		'procure_method': fields.property(False, type='selection', view_load=True, string="Procurement Method", required=True, 
			selection = [('make_to_stock','Make to Stock'),('make_to_order','Make to Order')],
			help="Make to Stock: When needed, the product is taken from the stock or we wait for replenishment. \nMake to Order: When needed, the product is purchased or produced.", 
			),
		'supply_method': fields.property(False, type='selection', view_load=True, string="Supply Method", required=True, 
			selection = [('produce','Manufacture'),('buy','Buy')],
			help="Manufacture: When procuring the product, a manufacturing order or a task will be generated, depending on the product type. \nBuy: When procuring the product, a purchase order will be generated.", 
			),								     
        }

	_defaults = {
        'type' : 'product',
		'purchase_ok':False,
		'sale_ok':False,
		'state':'draft'        
    }
	
from openerp.addons.product.product import product_product as product_product_super	
def _get_main_product_supplier_fix(self, cr, uid, product, context=None):
	"""Determines the main (best) product supplier for ``product``,
	returning the corresponding ``supplierinfo`` record, or False
	if none were found. The default strategy is to select the
	supplier with the highest priority (i.e. smallest sequence).

	:param browse_record product: product to supply
	:rtype: product.supplierinfo browse_record or False
	"""
	#johnw, 03/05/2015, Add the active restriction when getting the main product's supplier
	sellers = [(seller_info.sequence, seller_info)
				   for seller_info in product.seller_ids or []
				   if seller_info and isinstance(seller_info.sequence, (int, long)) and seller_info.name.active]
	return sellers and sellers[0][1] or False	

product_product_super._get_main_product_supplier = _get_main_product_supplier_fix
