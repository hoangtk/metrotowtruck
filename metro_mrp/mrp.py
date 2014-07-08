# -*- encoding: utf-8 -*-
from osv import fields,osv
from openerp.tools.translate import _
from openerp import netsvc
import time
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from lxml import etree
class mrp_bom(osv.osv):
    _inherit = 'mrp.bom'
    def _get_full_name(self, cr, uid, ids, name=None, args=None, context=None):
        if context == None:
            context = {}
        res = {}
        for elmt in self.browse(cr, uid, ids, context=context):
            res[elmt.id] = self._get_one_full_name(elmt)
        return res

    def _get_one_full_name(self, elmt, level=20):
        if level<=0:
            return '...'
        if elmt.bom_id:
            parent_path = self._get_one_full_name(elmt.bom_id, level-1) + " / "
        else:
            parent_path = ''
        return parent_path + elmt.name  
       
    def _check_product(self, cr, uid, ids, context=None):
        """
            Override original one, to allow to have multiple lines with same Part Number
        """
        return True   
    _columns = {
                'is_common': fields.boolean('Common?'),
                'clone_bom_ids': fields.one2many('mrp.bom','common_bom_id','Clone BOMs'),
                'common_bom_id': fields.many2one('mrp.bom','Common BOM',ondelete='cascade'),
                'code': fields.char('Reference', size=16, required=True, readonly=True),
                'complete_name': fields.function(_get_full_name, type='char', string='Full Name'),
                }
    _defaults = {
        'is_common' : False,
    }
    _order = "sequence asc, id desc"
    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Reference must be unique!'),
    ] 
    _constraints = [
        (_check_product, 'BoM line product should not be same as BoM product.', ['product_id']),
        ] 
    '''
    SQL to update current code
    update mrp_bom set code = to_char(id,'0000')
    '''
    def default_get(self, cr, uid, fields_list, context=None):
        values = super(mrp_bom,self).default_get(cr, uid, fields_list, context)
        values.update({'code':self.pool.get('ir.sequence').get(cr, uid, 'mrp.bom')})
        return values
    #add the code return in the name
    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not len(ids):
            return []
        result = []
        for bom in self.browse(cr, user, ids, context=context):
            if bom.id <= 0:
                result.append((bom.id,''))
                continue
            result.append((bom.id,'[%s]%s'%(bom.code,self._get_one_full_name(bom))))
                          
        return result
    #add the code search in the searching
    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        if name:
            ids = self.search(cr, user, [('code','=',name)]+ args, limit=limit, context=context)
            if not ids:
                ids = self.search(cr, user, [('name','=',name)]+ args, limit=limit, context=context)
            if not ids:
                ids = set()
                ids.update(self.search(cr, user, args + [('code',operator,name)], limit=limit, context=context))
                if not limit or len(ids) < limit:
                    # we may underrun the limit because of dupes in the results, that's fine
                    ids.update(self.search(cr, user, args + [('name',operator,name)], limit=(limit and (limit-len(ids)) or False) , context=context))
                ids = list(ids)
        else:
            ids = self.search(cr, user, args, limit=limit, context=context)
        result = self.name_get(cr, user, ids, context=context)
        return result            
    def copy_data(self, cr, uid, id, default=None, context=None):
        res = super(mrp_bom,self).copy_data(cr, uid, id, default=default, context=context)
        if res:
            res.update({'clone_bom_ids':False,'bom_id':False,'code':self.pool.get('ir.sequence').get(cr, uid, 'mrp.bom')})
        return res    
    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids,(int,long)):
            ids = [ids]
        comp_to_master = 'bom_id' in vals and vals['bom_id'] == False
        if comp_to_master:
            #For the component changing to master BOM, the common bom id will be clear automatically.
            vals.update({'common_bom_id':False})                
        if 'is_common' in vals or 'bom_id' in vals:
            for bom in self.browse(cr, uid, ids, context=context):
                #Common BOM with clone BOM can not clear the 'common BOM' flag
                if 'is_common' in vals and vals['is_common'] == False and bom.clone_bom_ids:
                    raise osv.except_osv(_('Error!'), _('BOM "%s" can not be set to non common BOM, since there are clone parts generated!'%(bom.name,)))
                #Component BOM can not be set to common BOM
                if 'is_common' in vals and vals['is_common'] == True and bom.bom_id:
                    raise osv.except_osv(_('Error!'), _('BOM Component "%s" can not be set to common bom!'%(bom.name,)))
                #Common BOM only can be master BOM, it is not allow to change from master BOM to components
                if 'bom_id' in vals and not bom.bom_id and bom.is_common == True:
                    raise osv.except_osv(_('Error!'), _('common BOM "%s" can not have parent BOM!'%(bom.name,)))
                
                '''
                For the component changing to master BOM, 
                if it is a common BOM's component and have clone bom IDs, the raise exception, 
                since this will make difference between parent's BOM's structure with parent clone BOM's structure
                '''
                if comp_to_master and bom.clone_bom_ids:
                    raise osv.except_osv(_('Error!'), _('Component BOM "%s" have clone BOM, can not change to have parent BOM!'%(bom.name,)))
                
        resu = super(mrp_bom,self).write(cr, uid, ids, vals, context=context)
        
        #sync the common BOM's updating to the clone BOMs
        for bom in self.browse(cr, uid, ids):
            if not bom.clone_bom_ids:
                continue
            #For the BOM having clone_bom_ids(the common BOM and all of its components), need to update their clone_boms
            #1.for the simple fields
            fields = ['product_id', 'standard_price', 'routing_id', 'type', 'position', 'product_rounding','product_efficiency']
            clone_upt_vals = {}
            for field in fields:
                if field in vals:
                    clone_upt_vals.update({field:vals[field]})
            if len(clone_upt_vals) > 0:
                for bom in self.browse(cr, uid, ids, context=context):
                    if bom.clone_bom_ids:
                        clone_bom_ids = [clone_bom.id for clone_bom in bom.clone_bom_ids]
                        self.write(cr, uid, clone_bom_ids, clone_upt_vals, context=context)
            #2.for the parent field 'bom_id' changing, it is not allowed once there are by the previous checking code
        return resu
    
    def create(self, cr, uid, vals, context=None):
        new_id = super(mrp_bom,self).create(cr, uid, vals, context=context)
        #if new BOM’s parent BOM have clone BOMs, clone the new component BOM, and add to parent BOM’s clone BOM’s component list
        if 'bom_id' in vals and vals['bom_id'] != False:
            bom_parent = self.browse(cr, uid, vals['bom_id'], context=context)
            if bom_parent.clone_bom_ids:
                #loop to clone the new bom, and add to parent BOM’s clone BOM’s component list
                for clone_bom in bom_parent.clone_bom_ids:   
                    new_bom_clone_id = self.copy(cr, uid, new_id, context=context)     
                    upt_data = {'bom_id':clone_bom.id,'is_common':False,'common_bom_id':new_id}
                    self.write(cr, uid, [new_bom_clone_id], upt_data, context=context)
        return new_id
   
    def unlink(self, cr, uid, ids, context=None):
        for bom in self.browse(cr, uid, ids, context):
            if bom.clone_bom_ids:
                if bom.is_common: 
                    raise osv.except_osv(_('Error!'), _('BOM "%s" having clone BOMs, can not be delete!'%(bom.name,)))
        '''
        for the common BOM's comonent unlink, if there are clone_bom_ids, 
        database will delete all of the clone BOMs with cascade setting of column 'common_bom_id'.
        '''
        return super(mrp_bom,self).unlink(cr, uid, ids, context)
    def fields_get(self, cr, uid, allfields=None, context=None, write_access=True):
        resu = super(mrp_bom,self).fields_get(cr, uid, allfields, context, write_access)
        return resu
    def attachment_tree_view(self, cr, uid, ids, context):
        project_ids = self.pool.get('project.project').search(cr, uid, [('bom_id', 'in', ids)])
        task_ids = self.pool.get('project.task').search(cr, uid, ['|',('bom_id', 'in', ids),('project_id','in',project_ids)])
        domain = [
             '|','|', 
             '&', ('res_model', '=', 'mrp.bom'), ('res_id', 'in', ids),
             '&', ('res_model', '=', 'project.project'), ('res_id', 'in', project_ids),
             '&', ('res_model', '=', 'project.task'), ('res_id', 'in', task_ids)
        ]
        res_id = ids and ids[0] or False
        return {
            'name': _('Attachments'),
            'domain': domain,
            'res_model': 'ir.attachment',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'view_type': 'form',
            'view_id': False,
            'limit': 80,
            'context': "{'default_res_model': '%s','default_res_id': %d}" % (self._name, res_id)
        }    
'''
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        result = super(mrp_bom,self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if view_type=='form':
            eview = etree.fromstring(result['arch'])
            fields = result['fields'].keys()
            attrs = "{'readonly':[('common_bom_id','!=',False)]}"
            editable_fields = ['quantity','name','reference','sequence','date_start','date_stop']
            for field in fields:
                if field in editable_fields:
                    continue
                elems = eview.xpath("//field[@name='%s']"%(field,))
                if not elems:
                    continue
                elem_fld = elems[0]
                elem_fld.set('attrs',attrs)
            result['arch'] = etree.tostring(eview, pretty_print=True)
                        
        return result        
'''  
class mrp_production(osv.osv):
    _inherit = 'mrp.production'
    _order = 'id desc'
    _columns = {
        'mfg_ids': fields.many2many('sale.product', 'mrp_prod_id_rel','mrp_prod_id','mfg_id',string='MFG IDs',),
        'location_src_id': fields.property(
            'stock.location',
            type='many2one',
            relation='stock.location',
            string="Raw Materials Location",
            view_load=True,
            required=True,
            readonly=True, 
            states={'draft':[('readonly',False)]},
            help="Location where the system will look for components."),
        'location_dest_id': fields.property(
            'stock.location',
            type='many2one',
            relation='stock.location',
            string="Finished Products Location",
            view_load=True,
            required=True,
            readonly=True, 
            states={'draft':[('readonly',False)]},
            help="Location where the system will stock the finished products."),
    }    
#    def _default_stock_location(self, cr, uid, context=None):
#        loc_ids = self.pool.get('stock.location').search(cr, uid, [('usage','=','internal')], context=context)
#        if loc_ids:
#            return loc_ids[0]
#        else:
#            return False
#    _defaults = {
#        'location_src_id': _default_stock_location,
#        'location_dest_id': _default_stock_location
#    }    
               
class product_product(osv.osv):
    _inherit = "product.product"
        
    _columns = {
        'material': fields.char(string=u'Material', size=32, help="The material of the product"),
    }