# -*- encoding: utf-8 -*-
from osv import fields,osv
from openerp.tools.translate import _
from openerp import netsvc
import time
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from lxml import etree
class mrp_bom(osv.osv):
    _inherit = 'mrp.bom'
    _columns = {
                'is_common': fields.boolean('Common?'),
                'clone_bom_ids': fields.one2many('mrp.bom','common_bom_id','Clone BOMs'),
                'common_bom_id': fields.many2one('mrp.bom','Common BOM',ondelete='cascade'),
                }
    _defaults = {
        'is_common' : False,
    }    
    def _check_product(self, cr, uid, ids, context=None):
        """
            Override original one, to allow to have multiple lines with same Part Number
        """
        return True 
    _constraints = [
        (_check_product, 'BoM line product should not be same as BoM product.', ['product_id']),
    ] 
    def copy_data(self, cr, uid, id, default=None, context=None):
        res = super(mrp_bom,self).copy_data(cr, uid, id, default=default, context=context)
        if res:
            res.update({'clone_bom_ids':False,'bom_id':False})
        return res    
    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
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
class product_product(osv.osv):
    _inherit = "product.product"
        
    _columns = {
        'material': fields.char(string=u'Material', size=32, help="The material of the product"),
    }