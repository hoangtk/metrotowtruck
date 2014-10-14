# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from openerp import SUPERUSER_ID
from openerp.addons.audittrail.audittrail import audittrail_objects_proxy

'''
fix the bug of the exception raising when get name if the method is unlink, since data is not existing after unlink, johnw, 10/14/2014
'''
class audittrail_objects_proxy_patch(audittrail_objects_proxy):
    def process_data(self, cr, uid, pool, res_ids, model, method, old_values=None, new_values=None, field_list=None):
        """
        This function processes and iterates recursively to log the difference between the old
        data (i.e before the method was executed) and the new data and creates audittrail log
        accordingly.

        :param cr: the current row, from the database cursor,
        :param uid: the current user’s ID,
        :param pool: current db's pooler object.
        :param res_ids: Id's of resource to be logged/compared.
        :param model: model object which values are being changed
        :param method: method to log: create, read, unlink, write, actions, workflow actions
        :param old_values: dict of values read before execution of the method
        :param new_values: dict of values read after execution of the method
        :param field_list: optional argument containing the list of fields to log. Currently only
            used when performing a read, it could be usefull later on if we want to log the write
            on specific fields only.
        :return: True
        """
        if field_list is None:
            field_list = []
        # loop on all the given ids
        for res_id in res_ids:
            # compare old and new values and get audittrail log lines accordingly
            lines = self.prepare_audittrail_log_line(cr, uid, pool, model, res_id, method, old_values, new_values, field_list)

            # if at least one modification has been found
            for model_id, resource_id in lines:
                '''
                fix the bug of the exception raising when get name if the method is unlink, since data is not existing after unlink, johnw, 10/14/2014
                '''
                #name = pool.get(model.model).name_get(cr, uid, [resource_id])[0][1]
                #fix begin
                name = ''
                if (model_id, resource_id) in new_values:
                    # the resource is existing then we can get the data
                    name = pool.get(model.model).name_get(cr, uid, [resource_id])[0][1]
                else:
                    #get name from old data
                    #rec_name_column = self._all_columns[self._rec_name].columnv
                    if lines[(model_id, resource_id)]:
                        rec_column_name = pool.get(model.model)._rec_name
                        for line in lines[(model_id, resource_id)]:
                            if line['name'] == rec_column_name:
                                name = line['old_value_text']
                                break
                #fix end
                vals = {
                    'method': method,
                    'object_id': model_id,
                    'user_id': uid,
                    'res_id': resource_id,
                    'name': name,
                }
                if (model_id, resource_id) not in old_values and method not in ('copy', 'read'):
                    # the resource was not existing so we are forcing the method to 'create'
                    # (because it could also come with the value 'write' if we are creating
                    #  new record through a one2many field)
                    vals.update({'method': 'create'})
                if (model_id, resource_id) not in new_values and method not in ('copy', 'read'):
                    # the resource is not existing anymore so we are forcing the method to 'unlink'
                    # (because it could also come with the value 'write' if we are deleting the
                    #  record through a one2many field)
                    vals.update({'method': 'unlink'})
                # create the audittrail log in super admin mode, only if a change has been detected
                if lines[(model_id, resource_id)]:
                    log_id = pool.get('audittrail.log').create(cr, SUPERUSER_ID, vals)
                    model = pool.get('ir.model').browse(cr, uid, model_id)
                    self.create_log_line(cr, SUPERUSER_ID, log_id, model, lines[(model_id, resource_id)])
        return True
audittrail_objects_proxy_patch()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

