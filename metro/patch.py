# -*- coding: utf-8 -*-


#add the object name to the download PDF file name, by johnw, 2013/12/29

import simplejson
import time
import base64
import zlib
from openerp.addons.web.http import httprequest
from openerp.addons.web.controllers.main import content_disposition
from openerp.addons.web.controllers.main import Reports as WebReports

@httprequest
def metro_rpt_index(self, req, action, token):
    action = simplejson.loads(action)

    report_srv = req.session.proxy("report")
    context = dict(req.context)
    context.update(action["context"])

    report_data = {}
    report_ids = context["active_ids"]
    if 'report_type' in action:
        report_data['report_type'] = action['report_type']
    if 'datas' in action:
        if 'ids' in action['datas']:
            report_ids = action['datas'].pop('ids')
        report_data.update(action['datas'])

    report_id = report_srv.report(
        req.session._db, req.session._uid, req.session._password,
        action["report_name"], report_ids,
        report_data, context)

    report_struct = None
    while True:
        report_struct = report_srv.report_get(
            req.session._db, req.session._uid, req.session._password, report_id)
        if report_struct["state"]:
            break

        time.sleep(self.POLLING_DELAY)

    report = base64.b64decode(report_struct['result'])
    if report_struct.get('code') == 'zlib':
        report = zlib.decompress(report)
    report_mimetype = self.TYPES_MAPPING.get(
        report_struct['format'], 'octet-stream')
    file_name = action.get('name', 'report')
    ''' comment by john 02/15/2014, to use new logic to get the file name
    if 'name' not in action:
        reports = req.session.model('ir.actions.report.xml')
        res_id = reports.search([('report_name', '=', action['report_name']),],
                                0, False, False, context)
        if len(res_id) > 0:
            #changed by johnw @02/15/2014, use the 'download_filename' field
            file_name = reports.read(res_id[0], ['name'], context)['name']
        else:
            file_name = action['report_name']
    '''     
    #new logic to get file name from ir_act_report_xml.download_filename
    #begin
    reports = req.session.model('ir.actions.report.xml')
    res_id = reports.search([('report_name', '=', action['report_name']),],
                            0, False, False, context)
    if len(res_id) > 0:
        names = reports.read(res_id[0], ['name','download_filename'], context)
        if names['download_filename']:
            file_name = names['download_filename']
        else:
            file_name = names['name']
    else:
        file_name = action['report_name']
    #end
                          
    #add the object name to the file name, by johnw, 2013/12/29
    try:
        #only print the name when print one record
        if context['active_ids'] and len(context['active_ids']) == 1:
            model_obj = req.session.model(context['active_model'])
            model_rec_name = model_obj.name_get(context['active_ids'],context)[0][1]            
            if model_rec_name:
                #added by john, to call the object report name getting method to get the file name
                try:
                    file_name = model_obj.get_report_name(context['active_ids'][0],action['report_name'],context)  
                except AttributeError, e:
                    pass
                except Exception, e:
                    raise e
                file_name = '%s_%s' % (file_name, model_rec_name)
    except Exception:
        pass
    
    file_name = '%s.%s' % (file_name, report_struct['format'])

    return req.make_response(report,
         headers=[
             ('Content-Disposition', content_disposition(file_name, req)),
             ('Content-Type', report_mimetype),
             ('Content-Length', len(report))],
         cookies={'fileToken': token})
        
WebReports.index = metro_rpt_index
'''
Fix the download file name issue
'''

from openerp.addons.web.controllers.main import Binary as WebBinary

@httprequest
def saveas_ajax(self, req, data, token):
    jdata = simplejson.loads(data)
    model = jdata['model']
    field = jdata['field']
    data = jdata['data']
    id = jdata.get('id', None)
    filename_field = jdata.get('filename_field', None)
    context = jdata.get('context', {})

    Model = req.session.model(model)
    fields = [field]
    if filename_field:
        fields.append(filename_field)
    if data:
        res = { field: data }
        #add the file name getting by johnw, 06/27/2014
        #begin
        if filename_field:
            res_filename = {}
            if id:
                res_filename = Model.read(int(id), [filename_field], context)[0]
            else:
                res_filename = Model.default_get([filename_field], context)  
            if len(res_filename) > 0:
                res.update({filename_field:res_filename[filename_field]})          
        #end
    elif id:
        res = Model.read([int(id)], fields, context)[0]
    else:
        res = Model.default_get(fields, context)
    filecontent = base64.b64decode(res.get(field, ''))
    if not filecontent:
        raise ValueError(_("No content found for field '%s' on '%s:%s'") %
            (field, model, id))
    else:
        filename = '%s_%s' % (model.replace('.', '_'), id)
        if filename_field:
            filename = res.get(filename_field, '') or filename
        return req.make_response(filecontent,
            headers=[('Content-Type', 'application/octet-stream'),
                    ('Content-Disposition', content_disposition(filename, req))],
            cookies={'fileToken': token})
WebBinary.saveas_ajax = saveas_ajax
           
'''
fix the next_number updating issue for the standard sequence
'''
from openerp.addons.base.ir.ir_sequence import ir_sequence
def _sequence_next(self, cr, uid, seq_ids, context=None):
    if not seq_ids:
        return False
    if context is None:
        context = {}
    force_company = context.get('force_company')
    if not force_company:
        force_company = self.pool.get('res.users').browse(cr, uid, uid).company_id.id
    sequences = self.read(cr, uid, seq_ids, ['company_id','implementation','number_next','prefix','suffix','padding'])
    preferred_sequences = [s for s in sequences if s['company_id'] and s['company_id'][0] == force_company ]
    seq = preferred_sequences[0] if preferred_sequences else sequences[0]
    if seq['implementation'] == 'standard':
        cr.execute("SELECT nextval('ir_sequence_%03d')" % seq['id'])
#        seq['number_next'] = cr.fetchone()
    else:
        cr.execute("SELECT number_next FROM ir_sequence WHERE id=%s FOR UPDATE NOWAIT", (seq['id'],))
#        cr.execute("UPDATE ir_sequence SET number_next=number_next+number_increment WHERE id=%s ", (seq['id'],))
    #fixed by johnw, to update the number_next for all sequence type.
    seq['number_next'] = cr.fetchone()    
    cr.execute("UPDATE ir_sequence SET number_next=%s+1 WHERE id=%s ", (seq['number_next'], seq['id'],))
    d = self._interpolation_dict()
    interpolated_prefix = self._interpolate(seq['prefix'], d)
    interpolated_suffix = self._interpolate(seq['suffix'], d)
    return interpolated_prefix + '%%0%sd' % seq['padding'] % seq['number_next'] + interpolated_suffix
    
ir_sequence._next =  _sequence_next
   
from osv import fields,osv,orm    
class ir_action_report_xml(osv.osv):
    _name="ir.actions.report.xml"
    _inherit ="ir.actions.report.xml"
    _columns={
        'download_filename' : fields.char('Download File Name',size=64),
    }